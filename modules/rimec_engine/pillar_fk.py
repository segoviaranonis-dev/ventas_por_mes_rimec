"""
Pilares RIMEC desde listado de precios (Excel).

Marca = nombre de hoja → FK en marca_v2.descp_marca → linea.marca_id.
Género / estilo / tipo_1: herencia de catálogo (misma lógica que retail fk_resolve)
y descripciones en linea_referencia alineadas a las maestras vía FK.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from core.database import DBInspector, engine

_T = TypeVar("_T")

# Evita deadlocks cuando Streamlit / dos acciones tocan el mismo pilar a la vez.
_PILAR_ADVISORY_NS = 91_000_000


def _advisory_lock_proveedor_pilar(conn, proveedor_id: int) -> None:
    conn.execute(
        text("SELECT pg_advisory_xact_lock(CAST(:k AS bigint))"),
        {"k": _PILAR_ADVISORY_NS + int(proveedor_id)},
    )


def _es_deadlock(exc: BaseException) -> bool:
    if isinstance(exc, OperationalError):
        orig = getattr(exc, "orig", None)
        if getattr(orig, "pgcode", None) == "40P01":
            return True
        if "deadlock" in str(exc).lower():
            return True
    return False


def run_with_pilar_lock(proveedor_id: int, fn: Callable[..., _T], *args, **kwargs) -> _T:
    """Transacción serializada por proveedor + reintento si PostgreSQL detecta deadlock."""
    last: BaseException | None = None
    for attempt in range(4):
        try:
            with engine.begin() as conn:
                _advisory_lock_proveedor_pilar(conn, proveedor_id)
                return fn(conn, *args, **kwargs)
        except OperationalError as e:
            if not _es_deadlock(e):
                raise
            last = e
            DBInspector.log(
                f"[ENGINE] Deadlock pilar proveedor {proveedor_id}, "
                f"reintento {attempt + 1}/4",
                "WARNING",
            )
            time.sleep(0.15 * (2**attempt))
    if last:
        raise last
    raise RuntimeError("run_with_pilar_lock: agotados los reintentos")
from modules.rimec_engine.ley_genero import (
    resolver_genero_id_por_marca,
)
from modules.balance_tiendas_retail.fk_resolve import (
    _fetch_immediate_lower_linea,
    _fetch_lr_archetype_for_line,
    _fetch_lr_same_line_immediate_lower_ref,
    _fetch_lr_same_ref_on_lower_line,
    _fetch_template_line_for_range,
    _get_linea_id,
    _get_referencia_id,
    _lr_row_exists,
    _otros_genero_id,
    _otros_grupo_estilo_id,
    _otros_tipo_1_id,
    _parse_codigo_bigint_non_negative,
)
from modules.rimec_engine.lr_schema import linea_referencia_tiene_codigos_proveedor


def lookup_marca_id(conn, nombre_hoja: str) -> int | None:
    """Busca id_marca en marca_v2 por descp_marca (nombre de hoja Excel). Sin alta automática."""
    nombre = str(nombre_hoja or "").strip()
    if not nombre:
        return None
    row = conn.execute(
        text(
            """
            SELECT id_marca FROM public.marca_v2
            WHERE upper(btrim(COALESCE(descp_marca::text, ''))) = upper(btrim(:n))
            LIMIT 1
            """
        ),
        {"n": nombre},
    ).fetchone()
    if row:
        return int(row[0])
    row = conn.execute(
        text(
            """
            SELECT id_marca FROM public.marca_v2
            WHERE upper(btrim(COALESCE(descp_marca::text, '')))
                  LIKE '%' || upper(btrim(:n)) || '%'
            ORDER BY length(btrim(descp_marca::text))
            LIMIT 1
            """
        ),
        {"n": nombre},
    ).fetchone()
    return int(row[0]) if row else None


def _proveedor_codigo_negocio(conn, proveedor_id: int) -> str | None:
    """proveedor_importacion.codigo (texto de negocio, además del id)."""
    row = conn.execute(
        text(
            """
            SELECT codigo::text FROM public.proveedor_importacion
            WHERE id = CAST(:p AS bigint)
            LIMIT 1
            """
        ),
        {"p": proveedor_id},
    ).fetchone()
    return str(row[0]).strip() if row and row[0] is not None else None


def _inherit_linea_dims(conn, proveedor_id: int, line_num: int) -> tuple[int | None, int | None]:
    """genero_id, grupo_estilo_id desde línea plantilla inferior o bloque de mil."""
    l_prev = _fetch_immediate_lower_linea(conn, proveedor_id, line_num)
    tpl = l_prev if l_prev else _fetch_template_line_for_range(conn, proveedor_id, line_num)
    if not tpl:
        return None, None
    g = int(tpl["genero_id"]) if tpl.get("genero_id") is not None else None
    ge = int(tpl["grupo_estilo_id"]) if tpl.get("grupo_estilo_id") is not None else None
    return g, ge


def _inherit_lr_dims(
    conn,
    proveedor_id: int,
    linea_id: int,
    line_num: int,
    ref_num: int,
    ge_line: int | None,
) -> tuple[int, int]:
    ge_otros = _otros_grupo_estilo_id(engine)
    t1_otros = _otros_tipo_1_id(engine)
    arch = _fetch_lr_same_line_immediate_lower_ref(conn, proveedor_id, linea_id, ref_num)
    l_prev = _fetch_immediate_lower_linea(conn, proveedor_id, line_num)
    if arch is None and l_prev:
        lid_prev = int(l_prev["id"])
        arch = _fetch_lr_same_ref_on_lower_line(conn, proveedor_id, lid_prev, ref_num)
        if arch is None:
            arch = _fetch_lr_archetype_for_line(conn, proveedor_id, lid_prev)
    if arch is None:
        arch = _fetch_lr_archetype_for_line(conn, proveedor_id, linea_id)
    if arch:
        ge = int(arch["grupo_estilo_id"]) if arch.get("grupo_estilo_id") is not None else ge_line
        t1 = int(arch["tipo_1_id"]) if arch.get("tipo_1_id") is not None else t1_otros
    else:
        ge = ge_line if ge_line is not None else ge_otros
        t1 = t1_otros
    return ge or ge_otros, t1 or t1_otros


def _upsert_linea(
    conn,
    proveedor_id: int,
    line_num: int,
    marca_id: int,
    genero_id: int | None,
    grupo_estilo_id: int | None,
) -> int | None:
    """
    Refactorizado para usar motor compartido con herencia jerárquica (§3.1).
    Si línea nueva sin dimensiones → hereda de plantilla o sentinelas OTROS.
    """
    from core.pilares import upsert_linea

    # Usar motor compartido para upsert idempotente + herencia
    linea_id = upsert_linea(
        conn,
        str(line_num),
        proveedor_id,
        descripcion=f"Listado precios línea {line_num}"[:2000],
        marca_id=marca_id,
        genero_id=genero_id,
        grupo_estilo_id=grupo_estilo_id,
        fuente="listado",
    )
    return linea_id


def _upsert_linea_referencia(
    conn,
    proveedor_id: int,
    linea_id: int,
    ref_id: int,
    linea_codigo: int,
    referencia_codigo: int,
    proveedor_codigo: str | None,
    grupo_estilo_id: int,
    tipo_1_id: int,
) -> None:
    tiene_codigos = linea_referencia_tiene_codigos_proveedor(conn)
    cod_prov = proveedor_codigo or _proveedor_codigo_negocio(conn, proveedor_id)
    params = {
        "p": proveedor_id,
        "ge": grupo_estilo_id,
        "t1": tipo_1_id,
        "lid": linea_id,
        "rid": ref_id,
    }
    if _lr_row_exists(conn, linea_id, ref_id):
        if tiene_codigos:
            conn.execute(
                text(
                    """
                    UPDATE public.linea_referencia
                    SET proveedor_id = CAST(:p AS bigint),
                        codigo_proveedor = :cod_prov,
                        linea_codigo_proveedor = CAST(:lc AS bigint),
                        referencia_codigo_proveedor = CAST(:rc AS bigint),
                        grupo_estilo_id = CAST(:ge AS bigint),
                        tipo_1_id = CAST(:t1 AS bigint),
                        descp_grupo_estilo = (
                            SELECT g.descp_grupo_estilo FROM public.grupo_estilo_v2 g
                            WHERE g.id_grupo_estilo = CAST(:ge AS bigint) LIMIT 1
                        ),
                        descp_tipo_1 = (
                            SELECT t.descp_tipo_1 FROM public.tipo_1 t
                            WHERE t.id_tipo_1 = CAST(:t1 AS bigint) LIMIT 1
                        )
                    WHERE linea_id = CAST(:lid AS bigint)
                      AND referencia_id = CAST(:rid AS bigint)
                    """
                ),
                {
                    **params,
                    "cod_prov": cod_prov,
                    "lc": linea_codigo,
                    "rc": referencia_codigo,
                },
            )
        else:
            conn.execute(
                text(
                    """
                    UPDATE public.linea_referencia
                    SET proveedor_id = CAST(:p AS bigint),
                        grupo_estilo_id = CAST(:ge AS bigint),
                        tipo_1_id = CAST(:t1 AS bigint),
                        descp_grupo_estilo = (
                            SELECT g.descp_grupo_estilo FROM public.grupo_estilo_v2 g
                            WHERE g.id_grupo_estilo = CAST(:ge AS bigint) LIMIT 1
                        ),
                        descp_tipo_1 = (
                            SELECT t.descp_tipo_1 FROM public.tipo_1 t
                            WHERE t.id_tipo_1 = CAST(:t1 AS bigint) LIMIT 1
                        )
                    WHERE linea_id = CAST(:lid AS bigint)
                      AND referencia_id = CAST(:rid AS bigint)
                    """
                ),
                params,
            )
        return
    if tiene_codigos:
        conn.execute(
            text(
                """
                INSERT INTO public.linea_referencia (
                    linea_id, referencia_id, proveedor_id,
                    codigo_proveedor, linea_codigo_proveedor, referencia_codigo_proveedor,
                    grupo_estilo_id, tipo_1_id,
                    descp_grupo_estilo, descp_tipo_1
                ) VALUES (
                    CAST(:lid AS bigint), CAST(:rid AS bigint), CAST(:p AS bigint),
                    :cod_prov, CAST(:lc AS bigint), CAST(:rc AS bigint),
                    CAST(:ge AS bigint), CAST(:t1 AS bigint),
                    (SELECT g.descp_grupo_estilo FROM public.grupo_estilo_v2 g
                     WHERE g.id_grupo_estilo = CAST(:ge AS bigint) LIMIT 1),
                    (SELECT t.descp_tipo_1 FROM public.tipo_1 t
                     WHERE t.id_tipo_1 = CAST(:t1 AS bigint) LIMIT 1)
                )
                """
            ),
            {
                **params,
                "cod_prov": cod_prov,
                "lc": linea_codigo,
                "rc": referencia_codigo,
            },
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO public.linea_referencia (
                    linea_id, referencia_id, proveedor_id,
                    grupo_estilo_id, tipo_1_id,
                    descp_grupo_estilo, descp_tipo_1
                ) VALUES (
                    CAST(:lid AS bigint), CAST(:rid AS bigint), CAST(:p AS bigint),
                    CAST(:ge AS bigint), CAST(:t1 AS bigint),
                    (SELECT g.descp_grupo_estilo FROM public.grupo_estilo_v2 g
                     WHERE g.id_grupo_estilo = CAST(:ge AS bigint) LIMIT 1),
                    (SELECT t.descp_tipo_1 FROM public.tipo_1 t
                     WHERE t.id_tipo_1 = CAST(:t1 AS bigint) LIMIT 1)
                )
                """
            ),
            params,
        )


def provisionar_linea_pilar_clonando_inferior(
    proveedor_id: int,
    line_num: int | str,
    *,
    evento_id: int | None = None,
) -> tuple[bool, str, int]:
    """
    Alta en pilar de una línea numérica clonando la inmediata inferior (Regla 1.1)
    y sus pares linea_referencia (mismas referencias que la plantilla).
    Si hay evento_id, suma referencias de precio_lista para esa línea.
    """
    ln = _parse_codigo_bigint_non_negative(line_num)
    if ln is None:
        return False, f"Código de línea inválido: {line_num}", 0

    def _clonar(conn) -> tuple[bool, str, int]:
        ya = _get_linea_id(conn, proveedor_id, ln)
        tpl = _fetch_immediate_lower_linea(conn, proveedor_id, ln)
        tpl_cod: int | None = None
        if tpl:
            row_cod = conn.execute(
                text(
                    "SELECT codigo_proveedor::bigint FROM public.linea "
                    "WHERE id = CAST(:id AS bigint)"
                ),
                {"id": int(tpl["id"])},
            ).fetchone()
            tpl_cod = int(row_cod[0]) if row_cod else None
        else:
            tpl = _fetch_template_line_for_range(conn, proveedor_id, ln)
            if tpl:
                row_cod = conn.execute(
                    text(
                        "SELECT codigo_proveedor::bigint FROM public.linea "
                        "WHERE id = CAST(:id AS bigint)"
                    ),
                    {"id": int(tpl["id"])},
                ).fetchone()
                tpl_cod = int(row_cod[0]) if row_cod else None

        if not tpl:
            return (
                False,
                f"No hay línea plantilla para heredar (inferior o bloque de mil) antes de {ln}.",
                0,
            )

        marca_id = tpl.get("marca_id")
        if marca_id is None:
            return False, f"La línea plantilla no tiene marca_id (necesaria para alta de {ln}).", 0

        genero_id = int(tpl["genero_id"]) if tpl.get("genero_id") is not None else None
        ge_id = int(tpl["grupo_estilo_id"]) if tpl.get("grupo_estilo_id") is not None else None
        linea_id = _upsert_linea(
            conn, proveedor_id, ln, int(marca_id), genero_id, ge_id
        )
        if not linea_id:
            return False, f"No se pudo crear la línea {ln} en el pilar.", 0

        lid_tpl = int(tpl["id"])
        proveedor_codigo = _proveedor_codigo_negocio(conn, proveedor_id)
        ge_otros = _otros_grupo_estilo_id(engine)
        t1_otros = _otros_tipo_1_id(engine)

        lr_rows = conn.execute(
            text(
                """
                SELECT r.codigo_proveedor::bigint AS rc,
                       lr.grupo_estilo_id, lr.tipo_1_id
                FROM public.linea_referencia lr
                INNER JOIN public.referencia r
                    ON r.id = lr.referencia_id AND r.proveedor_id = lr.proveedor_id
                WHERE lr.linea_id = CAST(:lid AS bigint)
                  AND lr.proveedor_id = CAST(:p AS bigint)
                ORDER BY r.codigo_proveedor
                """
            ),
            {"lid": lid_tpl, "p": proveedor_id},
        ).fetchall()

        lr_map: dict[int, tuple[int, int]] = {}
        ref_nums: set[int] = set()
        for row in lr_rows:
            if row[0] is None:
                continue
            rn = int(row[0])
            ref_nums.add(rn)
            ge_lr = int(row[1]) if row[1] is not None else ge_otros
            t1_lr = int(row[2]) if row[2] is not None else t1_otros
            lr_map[rn] = (ge_lr, t1_lr)

        if evento_id:
            ev_rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT referencia_codigo::bigint AS rc
                    FROM precio_lista
                    WHERE evento_id = CAST(:eid AS bigint)
                      AND linea_codigo = CAST(:ln AS bigint)
                      AND referencia_codigo IS NOT NULL
                    """
                ),
                {"eid": int(evento_id), "ln": int(ln)},
            ).fetchall()
            for row in ev_rows:
                if row[0] is not None:
                    ref_nums.add(int(row[0]))

        n_lr = 0
        for rn in sorted(ref_nums):
            if rn in lr_map:
                ge_lr, t1_lr = lr_map[rn]
            else:
                ge_lr, t1_lr = _inherit_lr_dims(
                    conn, proveedor_id, int(linea_id), ln, rn, ge_id
                )
            ref_id = _get_referencia_id(conn, proveedor_id, int(linea_id), rn)
            if ref_id is None:
                conn.execute(
                    text(
                        """
                        INSERT INTO public.referencia (
                            proveedor_id, linea_id, codigo_proveedor
                        ) VALUES (
                            CAST(:p AS bigint), CAST(:l AS bigint), CAST(:c AS bigint)
                        )
                        """
                    ),
                    {"p": proveedor_id, "l": int(linea_id), "c": rn},
                )
                ref_id = _get_referencia_id(conn, proveedor_id, int(linea_id), rn)
            if not ref_id:
                continue
            _upsert_linea_referencia(
                conn,
                proveedor_id,
                int(linea_id),
                int(ref_id),
                ln,
                rn,
                proveedor_codigo,
                ge_lr,
                t1_lr,
            )
            n_lr += 1

        plantilla_txt = str(tpl_cod) if tpl_cod is not None else "?"
        if ya:
            msg = (
                f"Línea {ln} ya estaba en el pilar; "
                f"se sincronizaron {n_lr} par(es) L+R (plantilla {plantilla_txt})."
            )
        else:
            msg = (
                f"Línea {ln} creada en el pilar desde plantilla {plantilla_txt} "
                f"({n_lr} referencia(s) / linea_referencia)."
            )
        return True, msg, n_lr

    try:
        return run_with_pilar_lock(proveedor_id, _clonar)
    except OperationalError:
        return (
            False,
            "La base de datos está sincronizando el pilar (deadlock). "
            "Esperá unos segundos y volvé a intentar.",
            0,
        )


def provisionar_lineas_faltantes_en_pilar(
    proveedor_id: int,
    codigos: list[str],
    *,
    evento_id: int | None = None,
) -> tuple[list[str], list[str]]:
    """Intenta dar de alta cada código que aún no existe en linea (pilar)."""
    ok: list[str] = []
    errores: list[str] = []
    for cod in sorted(
        set(str(c).strip() for c in codigos if str(c).strip()),
        key=lambda x: (len(x), int(x) if x.isdigit() else x),
    ):
        if not cod.isdigit():
            errores.append(f"{cod}: no es código numérico de línea.")
            continue
        with engine.connect() as conn:
            existe = _get_linea_id(conn, proveedor_id, int(cod)) is not None
        if existe and not evento_id:
            ok.append(cod)
            continue
        success, msg, _ = provisionar_linea_pilar_clonando_inferior(
            proveedor_id, cod, evento_id=evento_id
        )
        if success:
            ok.append(cod)
        else:
            errores.append(msg)
    return ok, errores


def asegurar_pilares_para_listado(
    proveedor_id: int,
    skus_df: pd.DataFrame,
    *,
    evento_id: int | None = None,
) -> dict:
    """
    Antes de validar/calcular un listado: crea en pilar todo SKU del Excel.
    Primero por marca (provisionar_pilares_desde_skus); lo que falte se clona
    desde la línea inferior (Regla 1.1).
    """
    stats = provisionar_pilares_desde_skus(proveedor_id, skus_df)
    lineas_excel: set[str] = set()
    if skus_df is not None and not skus_df.empty:
        for _, row in skus_df.iterrows():
            ln = _parse_codigo_bigint_non_negative(row.get("linea"))
            if ln is not None:
                lineas_excel.add(str(ln))
    faltantes: list[str] = []
    if lineas_excel:
        codes_int = [int(c) for c in lineas_excel]
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT codigo_proveedor::text FROM linea
                    WHERE proveedor_id = :pid AND codigo_proveedor = ANY(:codes)
                    """
                ),
                {"pid": proveedor_id, "codes": codes_int},
            ).fetchall()
        existentes = {str(r[0]) for r in rows}
        faltantes = [c for c in lineas_excel if c not in existentes]
    if faltantes:
        ok, errs = provisionar_lineas_faltantes_en_pilar(
            proveedor_id, faltantes, evento_id=evento_id
        )
        stats["lineas_alta_automatica"] = len(ok)
        if errs:
            stats["lineas_alta_errores"] = errs[:12]
            DBInspector.log(
                f"[ENGINE] Pilares auto-alta: {len(errs)} error(es): {errs[:3]}",
                "WARNING",
            )
        else:
            DBInspector.log(
                f"[ENGINE] Pilares auto-alta: {len(ok)} línea(s) creadas en pilar",
                "SUCCESS",
            )
    return stats


def provisionar_pilares_desde_skus(proveedor_id: int, df_skus: pd.DataFrame) -> dict:
    """
    Por cada par (línea, referencia) del listado:
    - marca_id desde nombre de hoja Excel → marca_v2
    - linea + referencia + linea_referencia con FKs de género, estilo, tipo_1
    """
    stats: dict = {
        "pares": 0,
        "lineas": 0,
        "lr": 0,
        "marcas_ok": 0,
        "marcas_no_encontradas": [],
        "lineas_marca_conflicto": [],
        "ley_genero_rechazadas": [],
        "genero_bd_faltante": [],
        "ley_genero_lineas": 0,
    }
    if df_skus is None or df_skus.empty:
        return stats

    filas: list[tuple[int, int, str]] = []
    visto: set[tuple[int, int]] = set()
    marca_por_linea: dict[int, str] = {}
    for _, row in df_skus.iterrows():
        ln = _parse_codigo_bigint_non_negative(row.get("linea"))
        rn = _parse_codigo_bigint_non_negative(row.get("referencia"))
        marca = str(row.get("marca", "")).strip()
        if ln is None or rn is None or not marca:
            continue
        prev_m = marca_por_linea.get(ln)
        if prev_m and prev_m.upper() != marca.upper():
            if ln not in stats["lineas_marca_conflicto"]:
                stats["lineas_marca_conflicto"].append(ln)
            continue
        marca_por_linea[ln] = marca
        key = (ln, rn)
        if key in visto:
            continue
        visto.add(key)
        filas.append((ln, rn, marca))
    filas.sort(key=lambda t: (t[0], t[1]))
    stats["pares"] = len(filas)
    if not filas:
        return stats

    marcas_cache: dict[str, int | None] = {}
    proveedor_codigo: str | None = None

    def _provisionar_bulk(conn) -> None:
        nonlocal proveedor_codigo, stats
        proveedor_codigo = _proveedor_codigo_negocio(conn, proveedor_id)
        for ln, rn, marca_nombre in filas:
            if marca_nombre not in marcas_cache:
                marcas_cache[marca_nombre] = lookup_marca_id(conn, marca_nombre)
            marca_id = marcas_cache[marca_nombre]
            if marca_id is None:
                if marca_nombre not in stats["marcas_no_encontradas"]:
                    stats["marcas_no_encontradas"].append(marca_nombre)
                continue
            stats["marcas_ok"] += 1

            genero_id = resolver_genero_id_por_marca(conn, marca_nombre)
            if genero_id is None:
                from modules.rimec_engine.ley_genero import genero_codigo_por_marca

                cod = genero_codigo_por_marca(marca_nombre)
                if cod and cod not in stats["genero_bd_faltante"]:
                    stats["genero_bd_faltante"].append(cod)
                elif marca_nombre not in stats["ley_genero_rechazadas"]:
                    stats["ley_genero_rechazadas"].append(marca_nombre)
                continue

            _, ge_inh = _inherit_linea_dims(conn, proveedor_id, ln)
            linea_id = _upsert_linea(conn, proveedor_id, ln, marca_id, genero_id, ge_inh)
            if not linea_id:
                continue
            stats["lineas"] += 1

            ref_id = _get_referencia_id(conn, proveedor_id, linea_id, rn)
            if ref_id is None:
                conn.execute(
                    text(
                        """
                        INSERT INTO public.referencia (proveedor_id, linea_id, codigo_proveedor)
                        VALUES (CAST(:p AS bigint), CAST(:l AS bigint), CAST(:c AS bigint))
                        """
                    ),
                    {"p": proveedor_id, "l": linea_id, "c": rn},
                )
                ref_id = _get_referencia_id(conn, proveedor_id, linea_id, rn)
            if not ref_id:
                continue

            ge_lr, t1_lr = _inherit_lr_dims(conn, proveedor_id, linea_id, ln, rn, ge_inh)
            _upsert_linea_referencia(
                conn, proveedor_id, linea_id, ref_id, ln, rn, proveedor_codigo, ge_lr, t1_lr
            )
            stats["lr"] += 1

        stats["ley_genero_lineas"] = stats["lineas"]

    try:
        run_with_pilar_lock(proveedor_id, _provisionar_bulk)
    except OperationalError as e:
        DBInspector.log(f"[ENGINE] Pilares SKUs deadlock: {e}", "ERROR")
        stats["error_deadlock"] = True
        return stats

    if stats["marcas_no_encontradas"]:
        DBInspector.log(
            f"[ENGINE] Marcas sin FK en marca_v2: {stats['marcas_no_encontradas']}",
            "WARNING",
        )
    else:
        DBInspector.log(
            f"[ENGINE] Pilares: {stats['lineas']} líneas, {stats['lr']} L+R, "
            f"marcas FK {stats['marcas_ok']}/{stats['pares']}, "
            f"ley género {stats['ley_genero_lineas']} líneas",
            "SUCCESS",
        )
    return stats


def provisionar_pilares_desde_evento(evento_id: int) -> dict:
    """Reaplica FKs de pilares desde precio_lista de un evento cerrado."""
    from core.database import get_dataframe

    df = get_dataframe(
        """
        SELECT pe.proveedor_id,
               pl.linea_codigo AS linea,
               pl.referencia_codigo AS referencia,
               pl.marca
        FROM precio_lista pl
        JOIN precio_evento pe ON pe.id = pl.evento_id
        WHERE pl.evento_id = :eid
        """,
        {"eid": evento_id},
    )
    if df is None or df.empty:
        return {"pares": 0, "marcas_no_encontradas": [], "ley_genero_lineas": 0}
    return provisionar_pilares_desde_skus(int(df.iloc[0]["proveedor_id"]), df)
