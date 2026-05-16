"""
Resolución de FK contra maestros RIMEC (pilares) sin agregar columnas al Excel.

El Excel sigue trayendo material/color como **código proveedor** (bigint).
Se resuelven a material.id y color.id. Marca / género / estilo / tipo_1 salen de
linea + linea_referencia según línea+referencia.

**Ley fundamental (par línea+referencia):** si el par no existe en catálogo pero
línea y referencia son **códigos numéricos**, se **crean** en pilares (`linea`,
`referencia`, `linea_referencia`).

**Herencia de línea (Regla 1.1):** para una línea nueva `L`, se toma como plantilla
la **línea existente con mayor codigo_proveedor estrictamente menor que L**
(misma importadora). De ahí se copian marca_id, genero_id y grupo_estilo_id.
Si no existe ninguna línea menor, se usa fallback por **bloque de mil**
líneas (misma lógica histórica) y, en último término, «Otros».

**Herencia L+R (Regla 1.2):** al crear `linea_referencia` para ``(L, R)``, se toma
primero la fila LR de la **misma línea L** con **mayor codigo_proveedor de referencia
estrictamente menor que R** (p. ej. falta 1185-200 → heredar de 1185-199 si existe).
Si no hay, se intenta la misma referencia ``R`` en la línea inmediata inferior ``L_prev``,
luego arquetipos LR de ``L_prev``, de ``L``, y del fallback por bloque de mil.

**Material / color (Regla 2.1):** códigos ausentes en pilar se insertan con
descripcion/nombre NULL (no se rechaza la fila); el sentinela RETAIL_OTROS solo
aplica si el insert falla o el código es inválido.

**Orden de alta:** los pares L+R se procesan en orden **ascendente** por línea
luego referencia para que, al dar de alta varias refs en la misma línea, la
``R-1`` exista antes que ``R`` (requisito de herencia inmediata en la misma línea).

**Proveedor de pilares:** si no se pasa `proveedor_id`, se **infieren** con el
`proveedor_importacion` que maximiza pares (línea, ref) del lote presentes en
catálogo — no se usa solo el menor `id`, para no mezclar pilares de otro importador.
"""
from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import ProgrammingError

OTROS_CODIGO = "RETAIL_OTROS"
# Debe coincidir con migrations/033_retail_staging_fk_dims.sql (marca_v2 sin columna codigo).
OTROS_MARCA_DESCP = "Otros (retail staging)"
# Debe coincidir con migrations/033_retail_staging_fk_dims.sql (material/color por proveedor).
SENTINEL_CODIGO_PROVEEDOR = -999001

# Coherencia por rango de **mil** líneas (ej. 1000–1999): plantilla = línea numérica
# del mismo proveedor en ese bloque, más cercana en código a la línea nueva.
RETAIL_LINEA_CONTEXT_BUCKET = 1000


def _canon_codigo_pilar(v: Any) -> str:
    """
    Misma lógica que el Excel normalizado: evita claves 1122.0|828.0 vs 1122|828
    (pandas/SQL devuelven float o text con .0).
    """
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    if isinstance(v, bool):
        return ""
    if isinstance(v, int) and not isinstance(v, bool):
        return str(int(v))
    if isinstance(v, float):
        try:
            fv = float(v)
            if fv == int(fv):
                return str(int(fv))
        except (ValueError, TypeError, OverflowError):
            pass
    s = str(v).strip()
    if s.lower() in ("nan", "none", "<na>", "nat", ""):
        return ""
    try:
        f = float(s.replace(",", "."))
        if f == int(f):
            return str(int(f))
    except (ValueError, TypeError, OverflowError):
        pass
    return s


def _parse_codigo_bigint_non_negative(v: Any) -> int | None:
    """Entero no negativo para codigo_proveedor en linea/referencia; si no aplica → None."""
    s = _canon_codigo_pilar(v)
    if not s or not s.isdigit():
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _linea_context_range(line_num: int, width: int = RETAIL_LINEA_CONTEXT_BUCKET) -> tuple[int, int]:
    lo = (line_num // width) * width
    return lo, lo + width - 1


def _fetch_immediate_lower_linea(
    conn: Connection, proveedor_id: int, line_num: int
) -> dict[str, Any] | None:
    """
    Línea existente con mayor codigo_proveedor estrictamente menor que ``line_num``
    (herencia inmediata inferior). Una sola consulta index-friendly.
    """
    row = conn.execute(
        text(
            """
            SELECT l.id, l.marca_id, l.genero_id, l.grupo_estilo_id
            FROM public.linea l
            WHERE l.proveedor_id = CAST(:p AS bigint)
              AND trim(l.codigo_proveedor::text) ~ '^[0-9]+$'
              AND l.codigo_proveedor < CAST(:n AS bigint)
            ORDER BY l.codigo_proveedor DESC
            LIMIT 1
            """
        ),
        {"p": proveedor_id, "n": line_num},
    ).mappings().fetchone()
    return dict(row) if row else None


def _lr_key(lc: Any, rc: Any) -> str:
    return f"{_canon_codigo_pilar(lc)}|{_canon_codigo_pilar(rc)}"


def _scalar(engine: Engine, sql: str, params: dict[str, Any] | None = None) -> Any:
    with engine.connect() as c:
        return c.execute(text(sql), params or {}).scalar()


def default_proveedor_importacion_id(engine: Engine) -> int:
    """Primer proveedor de importación (fallback si el lote no matchea ningún catálogo)."""
    v = _scalar(
        engine,
        "SELECT id FROM public.proveedor_importacion ORDER BY id ASC LIMIT 1",
    )
    if v is None:
        raise RuntimeError(
            "No hay filas en proveedor_importacion; no se pueden resolver codigos de línea/material."
        )
    return int(v)


def _all_proveedor_importacion_ids(engine: Engine) -> list[int]:
    with engine.connect() as c:
        rows = c.execute(
            text("SELECT id FROM public.proveedor_importacion ORDER BY id ASC")
        ).fetchall()
    return [int(r[0]) for r in rows]


def infer_proveedor_importacion_id(engine: Engine, df: pd.DataFrame) -> int:
    """
    Elige el proveedor cuyo catálogo (linea + referencia) explica más pares únicos
    del lote. Evita usar siempre ORDER BY id LIMIT 1 cuando los pilares viven en otro id.
    """
    provs = _all_proveedor_importacion_ids(engine)
    if not provs:
        raise RuntimeError("proveedor_importacion vacío.")
    sub = df[["linea_code", "referencia_code"]].copy()
    sub["lc"] = sub["linea_code"].map(_canon_codigo_pilar)
    sub["rc"] = sub["referencia_code"].map(_canon_codigo_pilar)
    sub = sub.drop_duplicates(subset=["lc", "rc"], keep="first")
    if sub.empty:
        return provs[0]

    pairs = [{"lc": str(r.lc), "rc": str(r.rc)} for _, r in sub.iterrows()]
    if len(pairs) > 4000:
        pairs = pairs[:4000]
    payload = json.dumps(pairs, ensure_ascii=False)

    best_pid = provs[0]
    best_n = -1
    for pid in provs:
        n = _scalar(
            engine,
            """
            SELECT COUNT(*)::int
            FROM (
                SELECT DISTINCT btrim(x->>'lc') AS lc, btrim(x->>'rc') AS rc
                FROM jsonb_array_elements(CAST(:payload AS jsonb)) AS t(x)
            ) d
            WHERE EXISTS (
                SELECT 1
                FROM (
                    SELECT trim(l.codigo_proveedor::text) AS lc, trim(r.codigo_proveedor::text) AS rc
                    FROM public.linea_referencia lr
                    INNER JOIN public.linea l
                        ON l.id = lr.linea_id AND l.proveedor_id = lr.proveedor_id
                    INNER JOIN public.referencia r
                        ON r.id = lr.referencia_id AND r.proveedor_id = lr.proveedor_id
                    WHERE lr.proveedor_id = CAST(:p AS bigint)
                    UNION
                    SELECT trim(l.codigo_proveedor::text) AS lc, trim(r.codigo_proveedor::text) AS rc
                    FROM public.linea l
                    INNER JOIN public.referencia r
                        ON r.linea_id = l.id AND r.proveedor_id = l.proveedor_id
                    WHERE l.proveedor_id = CAST(:p AS bigint)
                ) c
                WHERE btrim(c.lc) = btrim(d.lc) AND btrim(c.rc) = btrim(d.rc)
            )
            """,
            {"payload": payload, "p": pid},
        )
        n = int(n or 0)
        if n > best_n:
            best_n, best_pid = n, pid

    if best_n <= 0:
        print(
            "[RETAIL-STAGING] infer proveedor: ningún par del lote aparece en catálogo "
            "(linea_referencia ni linea+referencia hijo); se usa proveedor id mínimo.",
            flush=True,
        )
        return default_proveedor_importacion_id(engine)
    return best_pid


def _otros_marca_id(engine: Engine) -> int:
    v = _scalar(
        engine,
        """
        SELECT id_marca FROM public.marca_v2
        WHERE lower(btrim(COALESCE(descp_marca::text, ''))) = lower(btrim(:d))
        LIMIT 1
        """,
        {"d": OTROS_MARCA_DESCP},
    )
    if v is not None:
        return int(v)
    v_like = _scalar(
        engine,
        """
        SELECT id_marca FROM public.marca_v2
        WHERE lower(btrim(COALESCE(descp_marca::text, ''))) LIKE '%otro%'
        ORDER BY id_marca ASC LIMIT 1
        """,
    )
    if v_like is not None:
        return int(v_like)
    v2 = _scalar(engine, "SELECT id_marca FROM public.marca_v2 ORDER BY id_marca ASC LIMIT 1")
    if v2 is None:
        raise RuntimeError("marca_v2 vacía: imposible asignar marca.")
    return int(v2)


def _otros_genero_id(engine: Engine) -> int:
    v = _scalar(
        engine,
        "SELECT id FROM public.genero WHERE codigo = :c AND COALESCE(activo, true) LIMIT 1",
        {"c": OTROS_CODIGO},
    )
    if v is not None:
        return int(v)
    v2 = _scalar(
        engine,
        "SELECT id FROM public.genero WHERE COALESCE(activo, true) ORDER BY id ASC LIMIT 1",
    )
    if v2 is None:
        raise RuntimeError("genero vacío: imposible asignar género.")
    return int(v2)


def _otros_grupo_estilo_id(engine: Engine) -> int:
    v = _scalar(
        engine,
        """
        SELECT id_grupo_estilo FROM public.grupo_estilo_v2
        WHERE lower(btrim(COALESCE(descp_grupo_estilo::text, ''))) LIKE '%otro%'
           OR lower(btrim(COALESCE(descp_grupo_estilo::text, ''))) = 'otros'
        ORDER BY id_grupo_estilo ASC LIMIT 1
        """,
    )
    if v is not None:
        return int(v)
    v2 = _scalar(
        engine,
        "SELECT id_grupo_estilo FROM public.grupo_estilo_v2 ORDER BY id_grupo_estilo ASC LIMIT 1",
    )
    if v2 is None:
        raise RuntimeError("grupo_estilo_v2 vacío: imposible asignar estilo.")
    return int(v2)


def _otros_tipo_1_id(engine: Engine) -> int:
    v = _scalar(
        engine,
        """
        SELECT id_tipo_1 FROM public.tipo_1
        WHERE lower(btrim(COALESCE(descp_tipo_1::text, ''))) LIKE '%otro%'
        ORDER BY id_tipo_1 ASC LIMIT 1
        """,
    )
    if v is not None:
        return int(v)
    try:
        v_cod = _scalar(
            engine,
            """
            SELECT id_tipo_1 FROM public.tipo_1
            WHERE codigo = :c
            ORDER BY id_tipo_1 ASC LIMIT 1
            """,
            {"c": OTROS_CODIGO},
        )
        if v_cod is not None:
            return int(v_cod)
    except ProgrammingError:
        pass
    v2 = _scalar(engine, "SELECT id_tipo_1 FROM public.tipo_1 ORDER BY id_tipo_1 ASC LIMIT 1")
    if v2 is None:
        raise RuntimeError("tipo_1 vacío: imposible asignar tipo_1.")
    return int(v2)


def _otros_material_id(engine: Engine, proveedor_id: int) -> int:
    v = _scalar(
        engine,
        """
        SELECT id FROM public.material
        WHERE proveedor_id = CAST(:p AS bigint) AND codigo_proveedor = CAST(:c AS bigint)
        LIMIT 1
        """,
        {"p": proveedor_id, "c": SENTINEL_CODIGO_PROVEEDOR},
    )
    if v is not None:
        return int(v)
    v2 = _scalar(
        engine,
        "SELECT id FROM public.material WHERE proveedor_id = CAST(:p AS bigint) ORDER BY id ASC LIMIT 1",
        {"p": proveedor_id},
    )
    if v2 is None:
        raise RuntimeError(f"material vacío para proveedor {proveedor_id}.")
    return int(v2)


def _otros_color_id(engine: Engine, proveedor_id: int) -> int:
    v = _scalar(
        engine,
        """
        SELECT id FROM public.color
        WHERE proveedor_id = CAST(:p AS bigint) AND codigo_proveedor = CAST(:c AS bigint)
        LIMIT 1
        """,
        {"p": proveedor_id, "c": SENTINEL_CODIGO_PROVEEDOR},
    )
    if v is not None:
        return int(v)
    v2 = _scalar(
        engine,
        "SELECT id FROM public.color WHERE proveedor_id = CAST(:p AS bigint) ORDER BY id ASC LIMIT 1",
        {"p": proveedor_id},
    )
    if v2 is None:
        raise RuntimeError(f"color vacío para proveedor {proveedor_id}.")
    return int(v2)


def _load_material_maps(engine: Engine, proveedor_id: int) -> tuple[set[int], dict[int, int]]:
    """(ids PK existentes, codigo_proveedor -> id)."""
    q = text(
        "SELECT id, codigo_proveedor FROM public.material WHERE proveedor_id = CAST(:p AS bigint)"
    )
    with engine.connect() as c:
        df = pd.read_sql(q, c, params={"p": proveedor_id})
    if df.empty:
        return set(), {}
    ids = {int(x) for x in df["id"].tolist()}
    mp = {int(row["codigo_proveedor"]): int(row["id"]) for _, row in df.iterrows()}
    return ids, mp


def _load_color_maps(engine: Engine, proveedor_id: int) -> tuple[set[int], dict[int, int]]:
    q = text(
        "SELECT id, codigo_proveedor FROM public.color WHERE proveedor_id = CAST(:p AS bigint)"
    )
    with engine.connect() as c:
        df = pd.read_sql(q, c, params={"p": proveedor_id})
    if df.empty:
        return set(), {}
    ids = {int(x) for x in df["id"].tolist()}
    mp = {int(row["codigo_proveedor"]): int(row["id"]) for _, row in df.iterrows()}
    return ids, mp


def _load_linea_ref_attrs(engine: Engine, proveedor_id: int) -> dict[str, dict[str, Any]]:
    """
    Clave canónica 'linea|ref' → marca_id, genero_id, grupo_estilo_id, tipo_1_id.

    Fuentes:
    1) linea INNER JOIN referencia (referencia.linea_id = línea).
    2) linea_referencia + linea + referencia (par explícito en pilares aunque r.linea_id sea otro).
    Si una clave está en ambas, gana (2) por ser la fila de linea_referencia.
    """
    sql_legacy = text(
        """
        SELECT
            trim(l.codigo_proveedor::text) AS lc,
            trim(r.codigo_proveedor::text) AS rc,
            l.marca_id,
            l.genero_id,
            COALESCE(lr.grupo_estilo_id, l.grupo_estilo_id) AS grupo_estilo_id,
            lr.tipo_1_id AS tipo_1_id
        FROM public.linea l
        JOIN public.referencia r
          ON r.linea_id = l.id AND r.proveedor_id = l.proveedor_id
        LEFT JOIN public.linea_referencia lr
          ON lr.linea_id = l.id
         AND lr.referencia_id = r.id
         AND lr.proveedor_id = l.proveedor_id
        WHERE l.proveedor_id = CAST(:p AS bigint)
        """
    )
    sql_lr = text(
        """
        SELECT
            trim(l.codigo_proveedor::text) AS lc,
            trim(r.codigo_proveedor::text) AS rc,
            l.marca_id,
            l.genero_id,
            COALESCE(lr.grupo_estilo_id, l.grupo_estilo_id) AS grupo_estilo_id,
            lr.tipo_1_id AS tipo_1_id
        FROM public.linea_referencia lr
        INNER JOIN public.linea l
            ON l.id = lr.linea_id AND l.proveedor_id = lr.proveedor_id
        INNER JOIN public.referencia r
            ON r.id = lr.referencia_id AND r.proveedor_id = lr.proveedor_id
        WHERE lr.proveedor_id = CAST(:p AS bigint)
        """
    )
    out: dict[str, dict[str, Any]] = {}
    with engine.connect() as c:
        df_leg = pd.read_sql(sql_legacy, c, params={"p": proveedor_id})
        df_lr = pd.read_sql(sql_lr, c, params={"p": proveedor_id})

    def _row_attrs(row: Any) -> dict[str, Any]:
        return {
            "marca_id": int(row["marca_id"]) if pd.notna(row["marca_id"]) else None,
            "genero_id": int(row["genero_id"]) if pd.notna(row["genero_id"]) else None,
            "grupo_estilo_id": int(row["grupo_estilo_id"]) if pd.notna(row["grupo_estilo_id"]) else None,
            "tipo_1_id": int(row["tipo_1_id"]) if pd.notna(row["tipo_1_id"]) else None,
        }

    for _, row in df_leg.iterrows():
        out[_lr_key(row["lc"], row["rc"])] = _row_attrs(row)
    for _, row in df_lr.iterrows():
        out[_lr_key(row["lc"], row["rc"])] = _row_attrs(row)
    return out


def _load_explicit_linea_referencia_keys(engine: Engine, proveedor_id: int) -> set[str]:
    """Pares que ya tienen fila en ``linea_referencia`` (no basta con referencia hija de linea)."""
    sql = text(
        """
        SELECT
            trim(l.codigo_proveedor::text) AS lc,
            trim(r.codigo_proveedor::text) AS rc
        FROM public.linea_referencia lr
        INNER JOIN public.linea l
            ON l.id = lr.linea_id AND l.proveedor_id = lr.proveedor_id
        INNER JOIN public.referencia r
            ON r.id = lr.referencia_id AND r.proveedor_id = lr.proveedor_id
        WHERE lr.proveedor_id = CAST(:p AS bigint)
        """
    )
    with engine.connect() as c:
        df = pd.read_sql(sql, c, params={"p": proveedor_id})
    if df.empty:
        return set()
    return {_lr_key(row["lc"], row["rc"]) for _, row in df.iterrows()}


def _fetch_template_line_for_range(
    conn: Connection, proveedor_id: int, line_num: int
) -> dict[str, Any] | None:
    lo, hi = _linea_context_range(line_num)
    row = conn.execute(
        text(
            """
            SELECT l.id, l.marca_id, l.genero_id, l.grupo_estilo_id
            FROM public.linea l
            WHERE l.proveedor_id = CAST(:p AS bigint)
              AND trim(l.codigo_proveedor::text) ~ '^[0-9]+$'
              AND l.codigo_proveedor BETWEEN CAST(:lo AS bigint) AND CAST(:hi AS bigint)
            ORDER BY abs(l.codigo_proveedor - CAST(:n AS bigint)), l.id
            LIMIT 1
            """
        ),
        {"p": proveedor_id, "lo": lo, "hi": hi, "n": line_num},
    ).mappings().fetchone()
    if row:
        return dict(row)
    row2 = conn.execute(
        text(
            """
            SELECT l.id, l.marca_id, l.genero_id, l.grupo_estilo_id
            FROM public.linea l
            WHERE l.proveedor_id = CAST(:p AS bigint)
              AND trim(l.codigo_proveedor::text) ~ '^[0-9]+$'
            ORDER BY abs(l.codigo_proveedor - CAST(:n AS bigint)), l.id
            LIMIT 1
            """
        ),
        {"p": proveedor_id, "n": line_num},
    ).mappings().fetchone()
    return dict(row2) if row2 else None


def _fetch_lr_archetype_for_line(
    conn: Connection, proveedor_id: int, template_linea_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        text(
            """
            SELECT lr.grupo_estilo_id, lr.tipo_1_id,
                   lr.descp_grupo_estilo, lr.descp_tipo_1
            FROM public.linea_referencia lr
            WHERE lr.proveedor_id = CAST(:p AS bigint)
              AND lr.linea_id = CAST(:lid AS bigint)
              AND lr.grupo_estilo_id IS NOT NULL
            ORDER BY lr.referencia_id
            LIMIT 1
            """
        ),
        {"p": proveedor_id, "lid": template_linea_id},
    ).mappings().fetchone()
    return dict(row) if row else None


def _fetch_lr_same_line_immediate_lower_ref(
    conn: Connection, proveedor_id: int, linea_id: int, ref_cod: int
) -> dict[str, Any] | None:
    """
    Misma línea ``linea_id``: LR con referencia numérica máxima estrictamente menor
    que ``ref_cod`` (p. ej. para alta 1185-200 usar plantilla 1185-199).
    """
    row = conn.execute(
        text(
            """
            SELECT lr.grupo_estilo_id, lr.tipo_1_id,
                   lr.descp_grupo_estilo, lr.descp_tipo_1
            FROM public.linea_referencia lr
            INNER JOIN public.referencia r
                ON r.id = lr.referencia_id
               AND r.proveedor_id = lr.proveedor_id
            WHERE lr.proveedor_id = CAST(:p AS bigint)
              AND lr.linea_id = CAST(:lid AS bigint)
              AND r.linea_id = CAST(:lid AS bigint)
              AND trim(r.codigo_proveedor::text) ~ '^[0-9]+$'
              AND r.codigo_proveedor < CAST(:rc AS bigint)
            ORDER BY r.codigo_proveedor DESC
            LIMIT 1
            """
        ),
        {"p": proveedor_id, "lid": linea_id, "rc": ref_cod},
    ).mappings().fetchone()
    return dict(row) if row else None


def _fetch_lr_same_ref_on_lower_line(
    conn: Connection, proveedor_id: int, lower_linea_id: int, ref_cod: int
) -> dict[str, Any] | None:
    """LR de la misma referencia ``ref_cod`` en la línea numérica inferior ``lower_linea_id`` (fallback)."""
    row = conn.execute(
        text(
            """
            SELECT lr.grupo_estilo_id, lr.tipo_1_id,
                   lr.descp_grupo_estilo, lr.descp_tipo_1
            FROM public.linea_referencia lr
            INNER JOIN public.referencia r
                ON r.id = lr.referencia_id
               AND r.proveedor_id = lr.proveedor_id
            WHERE lr.proveedor_id = CAST(:p AS bigint)
              AND lr.linea_id = CAST(:lid AS bigint)
              AND r.linea_id = CAST(:lid AS bigint)
              AND r.codigo_proveedor = CAST(:rc AS bigint)
            LIMIT 1
            """
        ),
        {"p": proveedor_id, "lid": lower_linea_id, "rc": ref_cod},
    ).mappings().fetchone()
    return dict(row) if row else None


def _get_linea_id(conn: Connection, proveedor_id: int, cod_linea: int) -> int | None:
    r = conn.execute(
        text(
            """
            SELECT id FROM public.linea
            WHERE proveedor_id = CAST(:p AS bigint) AND codigo_proveedor = CAST(:c AS bigint)
            LIMIT 1
            """
        ),
        {"p": proveedor_id, "c": cod_linea},
    ).fetchone()
    return int(r[0]) if r else None


def _get_referencia_id(conn: Connection, proveedor_id: int, linea_id: int, cod_ref: int) -> int | None:
    r = conn.execute(
        text(
            """
            SELECT id FROM public.referencia
            WHERE proveedor_id = CAST(:p AS bigint)
              AND linea_id = CAST(:l AS bigint)
              AND codigo_proveedor = CAST(:c AS bigint)
            LIMIT 1
            """
        ),
        {"p": proveedor_id, "l": linea_id, "c": cod_ref},
    ).fetchone()
    return int(r[0]) if r else None


def _provision_missing_material_color_codes(engine: Engine, proveedor_id: int, df: pd.DataFrame) -> None:
    """
    Regla 2.1: alta perezosa de material/color por codigo_proveedor con descripcion/nombre NULL
    si el código no está en el pilar (no detiene la importación).
    """
    raw_mats: set[int] = set()
    raw_cols: set[int] = set()
    for _, row in df.iterrows():
        try:
            rm = int(float(row["material_id"]))
        except (TypeError, ValueError):
            continue
        try:
            rc = int(float(row["color_id"]))
        except (TypeError, ValueError):
            continue
        if rm == SENTINEL_CODIGO_PROVEEDOR or rc == SENTINEL_CODIGO_PROVEEDOR:
            continue
        raw_mats.add(rm)
        raw_cols.add(rc)

    mat_ids, mat_by_cod = _load_material_maps(engine, proveedor_id)
    col_ids, col_by_cod = _load_color_maps(engine, proveedor_id)
    mats_miss = sorted(x for x in raw_mats if x not in mat_ids and x not in mat_by_cod)
    cols_miss = sorted(x for x in raw_cols if x not in col_ids and x not in col_by_cod)
    if not mats_miss and not cols_miss:
        return

    with engine.begin() as conn:
        for cod in mats_miss:
            conn.execute(
                text(
                    """
                    INSERT INTO public.material (proveedor_id, codigo_proveedor, descripcion)
                    SELECT CAST(:p AS bigint), CAST(:c AS bigint), NULL
                    WHERE NOT EXISTS (
                        SELECT 1 FROM public.material m
                        WHERE m.proveedor_id = CAST(:p2 AS bigint)
                          AND m.codigo_proveedor = CAST(:c2 AS bigint)
                    )
                    """
                ),
                {"p": proveedor_id, "c": cod, "p2": proveedor_id, "c2": cod},
            )
        for cod in cols_miss:
            conn.execute(
                text(
                    """
                    INSERT INTO public.color (proveedor_id, codigo_proveedor, nombre)
                    SELECT CAST(:p AS bigint), CAST(:c AS bigint), NULL
                    WHERE NOT EXISTS (
                        SELECT 1 FROM public.color c2
                        WHERE c2.proveedor_id = CAST(:p2 AS bigint)
                          AND c2.codigo_proveedor = CAST(:c2 AS bigint)
                    )
                    """
                ),
                {"p": proveedor_id, "c": cod, "p2": proveedor_id, "c2": cod},
            )


def _lr_row_exists(conn: Connection, linea_id: int, referencia_id: int) -> bool:
    r = conn.execute(
        text(
            """
            SELECT 1 FROM public.linea_referencia
            WHERE linea_id = CAST(:l AS bigint) AND referencia_id = CAST(:r AS bigint)
            LIMIT 1
            """
        ),
        {"l": linea_id, "r": referencia_id},
    ).fetchone()
    return r is not None


def provision_missing_linea_referencia_pairs(
    engine: Engine,
    proveedor_id: int,
    missing_keys: set[str],
    *,
    marca_otros_id: int,
    genero_otros_id: int,
    ge_otros_id: int,
    t1_otros_id: int,
) -> int:
    """
    Inserta en pilares pares línea+referencia numéricos ausentes del mapa L+R.

    Herencia 1.1: línea plantilla = mayor codigo_proveedor < L (misma importadora).
    Herencia 1.2: LR = referencia inmediata inferior en la **misma** línea (R-1 en catálogo);
    si no hay, misma R en línea L_prev, arquetipos, bloque de mil.
    Orden: línea ASC, referencia ASC (para que existan 1185-199 antes que 1185-200).
    """
    rows: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for key in missing_keys:
        parts = key.split("|", 1)
        if len(parts) != 2:
            continue
        lc_s, rc_s = parts[0].strip(), parts[1].strip()
        ln = _parse_codigo_bigint_non_negative(lc_s)
        rn = _parse_codigo_bigint_non_negative(rc_s)
        if ln is None or rn is None:
            continue
        t = (ln, rn)
        if t in seen:
            continue
        seen.add(t)
        rows.append(t)
    rows.sort(key=lambda t: (t[0], t[1]))
    if not rows:
        return 0

    with engine.begin() as conn:
        for ln, rn in rows:
            l_prev = _fetch_immediate_lower_linea(conn, proveedor_id, ln)
            tpl_bucket = _fetch_template_line_for_range(conn, proveedor_id, ln)
            tpl_line = l_prev if l_prev is not None else tpl_bucket

            if tpl_line is None:
                m_id = marca_otros_id
                g_id = genero_otros_id
                ge_from_line = None
                ge_for_line = ge_otros_id
            else:
                m_id = int(tpl_line["marca_id"]) if tpl_line["marca_id"] is not None else marca_otros_id
                g_id = int(tpl_line["genero_id"]) if tpl_line["genero_id"] is not None else genero_otros_id
                ge_from_line = int(tpl_line["grupo_estilo_id"]) if tpl_line["grupo_estilo_id"] is not None else None
                ge_for_line = ge_from_line if ge_from_line is not None else ge_otros_id

            linea_id = _get_linea_id(conn, proveedor_id, ln)
            if linea_id is None:
                conn.execute(
                    text(
                        """
                        INSERT INTO public.linea (
                            proveedor_id, codigo_proveedor, descripcion,
                            marca_id, genero_id, grupo_estilo_id
                        ) VALUES (
                            CAST(:p AS bigint), CAST(:cod AS bigint), CAST(:d AS text),
                            CAST(:m AS bigint), CAST(:g AS bigint), CAST(:ge AS bigint)
                        )
                        """
                    ),
                    {
                        "p": proveedor_id,
                        "cod": ln,
                        "d": f"Retail auto línea {ln}"[:2000],
                        "m": m_id,
                        "g": g_id,
                        "ge": ge_for_line,
                    },
                )
                linea_id = _get_linea_id(conn, proveedor_id, ln)
            if linea_id is None:
                continue

            # LR: primero ref. inmediata inferior en la MISMA línea (1185-199 → plantilla para 1185-200).
            arch = _fetch_lr_same_line_immediate_lower_ref(conn, proveedor_id, linea_id, rn)
            if arch is None and l_prev is not None:
                lid_prev = int(l_prev["id"])
                arch = _fetch_lr_same_ref_on_lower_line(conn, proveedor_id, lid_prev, rn)
                if arch is None:
                    arch = _fetch_lr_archetype_for_line(conn, proveedor_id, lid_prev)
            if arch is None:
                arch = _fetch_lr_archetype_for_line(conn, proveedor_id, linea_id)
            if arch is None and tpl_bucket is not None:
                arch = _fetch_lr_archetype_for_line(conn, proveedor_id, int(tpl_bucket["id"]))
            if arch:
                ge_lr = int(arch["grupo_estilo_id"]) if arch["grupo_estilo_id"] is not None else ge_otros_id
                t1_lr = int(arch["tipo_1_id"]) if arch["tipo_1_id"] is not None else t1_otros_id
            else:
                ge_lr = ge_from_line if ge_from_line is not None else ge_otros_id
                t1_lr = t1_otros_id

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
            if ref_id is None:
                continue

            if _lr_row_exists(conn, linea_id, ref_id):
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO public.linea_referencia (
                        linea_id, referencia_id, proveedor_id,
                        grupo_estilo_id, tipo_1_id,
                        descp_grupo_estilo, descp_tipo_1
                    )
                    VALUES (
                        CAST(:lid AS bigint), CAST(:rid AS bigint), CAST(:p AS bigint),
                        CAST(:ge AS bigint), CAST(:t1 AS bigint),
                        (SELECT g.descp_grupo_estilo FROM public.grupo_estilo_v2 g
                         WHERE g.id_grupo_estilo = CAST(:ge AS bigint) LIMIT 1),
                        (SELECT t.descp_tipo_1 FROM public.tipo_1 t
                         WHERE t.id_tipo_1 = CAST(:t1 AS bigint) LIMIT 1)
                    )
                    ON CONFLICT (linea_id, referencia_id) DO NOTHING
                    """
                ),
                {
                    "lid": linea_id,
                    "rid": ref_id,
                    "p": proveedor_id,
                    "ge": ge_lr,
                    "t1": t1_lr,
                },
            )

    return len(rows)


def resolve_retail_fks(
    engine: Engine, df: pd.DataFrame, *, proveedor_id: int | None = None
) -> tuple[pd.DataFrame, list[str]]:
    """
    Enriquece el DataFrame normalizado con FKs de maestros.
    Sobreescribe material_id / color_id con material.id / color.id.
    Agrega marca_id, genero_id, grupo_estilo_id, tipo_1_id.
    """
    warns: list[str] = []
    if proveedor_id is not None:
        pid = proveedor_id
    else:
        pid = infer_proveedor_importacion_id(engine, df)
        fb = default_proveedor_importacion_id(engine)
        print(
            f"[RETAIL-STAGING] proveedor_id para pilares/material-color: {pid}"
            + (f" (fallback mínimo id sería {fb})" if pid != fb else ""),
            flush=True,
        )

    marca_o = _otros_marca_id(engine)
    gen_o = _otros_genero_id(engine)
    ge_o = _otros_grupo_estilo_id(engine)
    t1_o = _otros_tipo_1_id(engine)
    mat_o = _otros_material_id(engine, pid)
    col_o = _otros_color_id(engine, pid)

    mat_ids, mat_by_cod = _load_material_maps(engine, pid)
    col_ids, col_by_cod = _load_color_maps(engine, pid)
    _provision_missing_material_color_codes(engine, pid, df)
    mat_ids, mat_by_cod = _load_material_maps(engine, pid)
    col_ids, col_by_cod = _load_color_maps(engine, pid)
    lr_map = _load_linea_ref_attrs(engine, pid)
    lr_explicit = _load_explicit_linea_referencia_keys(engine, pid)
    print(
        f"[RETAIL-STAGING] mapa catálogo L+R: {len(lr_map)} pares (join catálogo), "
        f"{len(lr_explicit)} con fila linea_referencia (proveedor_id={pid})",
        flush=True,
    )

    # Falta provisionar si NO hay fila en linea_referencia (aunque exista referencia hija de linea).
    missing_lr: set[str] = set()
    for _, row in df.iterrows():
        k = _lr_key(row["linea_code"], row["referencia_code"])
        if k not in lr_explicit:
            missing_lr.add(k)
    if missing_lr:
        n_num = provision_missing_linea_referencia_pairs(
            engine,
            pid,
            missing_lr,
            marca_otros_id=marca_o,
            genero_otros_id=gen_o,
            ge_otros_id=ge_o,
            t1_otros_id=t1_o,
        )
        if n_num > 0:
            print(
                f"[RETAIL-STAGING] pilares: procesados {n_num} pares L+R numéricos "
                "(LR: ref. inmediata inferior misma línea; línea: L_prev numérica; fallbacks).",
                flush=True,
            )
        lr_map = _load_linea_ref_attrs(engine, pid)
        print(
            f"[RETAIL-STAGING] mapa L+R tras alta automática: {len(lr_map)} pares (proveedor_id={pid})",
            flush=True,
        )

    out = df.copy()
    mids: list[int] = []
    cids: list[int] = []
    marca_ids: list[int] = []
    genero_ids: list[int] = []
    ge_ids: list[int] = []
    t1_ids: list[int] = []

    for _, row in out.iterrows():
        key = _lr_key(row["linea_code"], row["referencia_code"])
        attrs = lr_map.get(key)

        if attrs is None:
            warns.append(f"Sin linea+ref en catálogo tras alta automática ({key}); dimensiones → Otros.")
            m_m, m_g, m_ge, m_t1 = marca_o, gen_o, ge_o, t1_o
        else:
            m_m = int(attrs["marca_id"]) if attrs["marca_id"] is not None else marca_o
            m_g = int(attrs["genero_id"]) if attrs["genero_id"] is not None else gen_o
            m_ge = int(attrs["grupo_estilo_id"]) if attrs["grupo_estilo_id"] is not None else ge_o
            m_t1 = int(attrs["tipo_1_id"]) if attrs["tipo_1_id"] is not None else t1_o

        raw_mat = int(float(row["material_id"]))
        if raw_mat in mat_ids:
            mpk = raw_mat
        else:
            mpk = mat_by_cod.get(raw_mat, mat_o)
            if mpk == mat_o and raw_mat not in mat_ids and raw_mat not in mat_by_cod:
                warns.append(f"Material codigo {raw_mat} no encontrado → fallback.")

        raw_col = int(float(row["color_id"]))
        if raw_col in col_ids:
            cpk = raw_col
        else:
            cpk = col_by_cod.get(raw_col, col_o)
            if cpk == col_o and raw_col not in col_ids and raw_col not in col_by_cod:
                warns.append(f"Color codigo {raw_col} no encontrado → fallback.")

        mids.append(mpk)
        cids.append(cpk)
        marca_ids.append(m_m)
        genero_ids.append(m_g)
        ge_ids.append(m_ge)
        t1_ids.append(m_t1)

    out["material_id"] = mids
    out["color_id"] = cids
    out["marca_id"] = marca_ids
    out["genero_id"] = genero_ids
    out["grupo_estilo_id"] = ge_ids
    out["tipo_1_id"] = t1_ids

    uniq_warns = sorted(set(warns))
    if uniq_warns:
        print(
            f"[RETAIL-STAGING] FK resolve: {len(uniq_warns)} avisos (muestra 5): {uniq_warns[:5]}",
            flush=True,
        )

    return out, uniq_warns
