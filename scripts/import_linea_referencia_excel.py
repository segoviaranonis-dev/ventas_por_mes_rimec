"""
Nexus Dictador — RESETEO: el Excel manda. linea_referencia se vacía (TRUNCATE o DELETE) y se repuebla.

Columnas en linea_referencia (tras migración 017): grupo_estilo_id, tipo_1_id (FK INT)
más descp_grupo_estilo / descp_tipo_1 (TEXT, mismo nombre que las maestras).
Ejecutá migrations/017_linea_referencia_descp_grupo_tipo.sql en Supabase antes del import si aún no renombraste columnas.

Columnas opcionales en el Excel (pilar linea — última fila gana por id de línea):
  · linea_descripcion (o descripcion_linea / desc_linea): texto → columna linea.descripcion
  · marca_id (o id_marca), genero_id (o id_genero): enteros → linea.marca_id / linea.genero_id
    Si faltan en el archivo, el UPSERT conserva con COALESCE el valor ya guardado en BD.

  · linea / referencia: IDs del Excel; si no existen se INSERTAN; referencia existente se MUEVE a la
    linea_id del Excel (UPDATE linea_id).
  · Maestros grupo_estilo_v2 y tipo_1: UPSERT por id + descripción.
  · Cada fila del Excel con 4 IDs válidos participa en linea_referencia (última fila gana por par
    único linea_id+referencia_id). No hay contador de «omitidas» por FK: cero omisiones por política.

Nota física: si el Excel repite el mismo par (linea, referencia), en BD solo puede quedar UNA fila
  por el UNIQUE de linea_referencia; se procesan todas las filas del Excel y el último valor gana.

Uso:
  python scripts/import_linea_referencia_excel.py ruta.xlsx
  python scripts/import_linea_referencia_excel.py ruta.xlsx --delete-lr-scope proveedor  # default
  python scripts/import_linea_referencia_excel.py ruta.xlsx --delete-lr-scope all
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

SCRIPT_REVISION = 11

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.lib.import_heartbeat import (  # noqa: E402
    start_import_heartbeat as _start_heartbeat,
    stop_import_heartbeat as _stop_heartbeat,
)


def norm_col(s: str) -> str:
    return "".join(c for c in str(s).strip().lower() if c.isalnum() or c == "_")


def rename_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for c in df.columns:
        n = norm_col(c)
        if n in ("linea", "lnea"):
            mapping[c] = "linea"
        elif n in ("referencia", "ref"):
            mapping[c] = "referencia"
        elif "id_grupo_estilo" in n or n == "idgrupoestilo":
            mapping[c] = "id_grupo_estilo"
        elif "descp_grupo_estilo" in n or n == "descgrupoestilo":
            mapping[c] = "descp_grupo_estilo"
        elif "id_tipo_1" in n or n == "idtipo1":
            mapping[c] = "id_tipo_1"
        elif "descp_tipo_1" in n or n == "desctipo1":
            mapping[c] = "descp_tipo_1"
        elif n in ("marca_id", "id_marca"):
            mapping[c] = "marca_id"
        elif n in ("genero_id", "id_genero"):
            mapping[c] = "genero_id"
        elif n in ("descripcion_linea", "linea_descripcion", "desc_linea", "descripcionlinea"):
            mapping[c] = "linea_descripcion"
    return df.rename(columns=mapping)


def to_int_id(v) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s or s.lower() == "nan":
            return None
    try:
        x = float(v)
        if x != x:
            return None
        return int(x)
    except (TypeError, ValueError):
        return None


def str_desc(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _sql_text_lit(s: str) -> str:
    """Literal SQL string (Postgres) — solo para textos que ya controlamos (Excel/maestros)."""
    t = str(s).replace("'", "''")[:8000]
    return "'" + t + "'"


def _linea_column_exists(conn, col: str) -> bool:
    r = conn.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'linea' AND column_name = :c
            )
            """
        ),
        {"c": col},
    ).scalar()
    return bool(r)


def _upsert_linea_excel(
    conn,
    *,
    proveedor_id: int,
    linea_id: int,
    meta: dict[str, Any],
    has_descripcion: bool,
    has_marca_id: bool,
    has_genero_id: bool,
) -> None:
    """INSERT/UPDATE linea por id Excel; descripcion/marca/género solo si existen columnas en BD."""
    cols = ["id", "proveedor_id", "codigo_proveedor"]
    ph = [":lid", ":pid", ":lid"]
    params: dict[str, Any] = {"lid": int(linea_id), "pid": int(proveedor_id)}
    upd = [
        "proveedor_id = EXCLUDED.proveedor_id",
        "codigo_proveedor = EXCLUDED.codigo_proveedor",
    ]
    if has_descripcion:
        cols.append("descripcion")
        ph.append(":descripcion")
        params["descripcion"] = str(meta.get("descripcion") or f"Línea {linea_id}")[:4000]
        upd.append(
            "descripcion = COALESCE(NULLIF(BTRIM(EXCLUDED.descripcion), ''), linea.descripcion)"
        )
    if has_marca_id:
        cols.append("marca_id")
        ph.append(":marca_id")
        params["marca_id"] = meta.get("marca_id")
        upd.append("marca_id = COALESCE(EXCLUDED.marca_id, linea.marca_id)")
    if has_genero_id:
        cols.append("genero_id")
        ph.append(":genero_id")
        params["genero_id"] = meta.get("genero_id")
        upd.append("genero_id = COALESCE(EXCLUDED.genero_id, linea.genero_id)")
    sql = (
        f"INSERT INTO linea ({', '.join(cols)}) VALUES ({', '.join(ph)}) "
        f"ON CONFLICT (id) DO UPDATE SET {', '.join(upd)}"
    )
    conn.execute(text(sql), params)


def main() -> None:
    import tomllib
    from urllib.parse import quote_plus

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "xlsx",
        nargs="?",
        default=str(Path.home() / "Downloads" / "linea_referencia.xlsx"),
    )
    ap.add_argument("--proveedor-id", type=int, default=654)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--chunk", type=int, default=500, help="Filas por upsert linea_referencia")
    ap.add_argument(
        "--skip-sync-activos",
        action="store_true",
        help="No ejecutar el INSERT masivo desde el CTE activos (pedidos/precios/etc.); solo lo del Excel",
    )
    ap.add_argument(
        "--delete-lr-scope",
        choices=("proveedor", "all"),
        default="proveedor",
        help="proveedor: DELETE linea_referencia WHERE proveedor_id=… | all: borra toda la tabla",
    )
    ap.add_argument(
        "--verify-linea",
        type=int,
        default=2126,
        help="Tras COMMIT, muestra id/codigo/descripcion/marca_id/genero_id de esa línea (0 = omitir)",
    )
    args = ap.parse_args()

    xlsx_path = Path(args.xlsx)
    if not xlsx_path.is_file():
        print(f"ERROR: no existe: {xlsx_path}", file=sys.stderr)
        sys.exit(1)

    print(
        f"\n=== Nexus Dictador | revisión {SCRIPT_REVISION} | Excel manda ===\n"
        f"    script: {Path(__file__).resolve()}\n"
        f"    reloj local inicio: {datetime.now().isoformat(timespec='seconds')}\n",
        flush=True,
    )

    t0 = time.perf_counter()
    _last = [t0]

    def lap(etiqueta: str) -> None:
        now = time.perf_counter()
        desde_anterior = now - _last[0]
        desde_inicio = now - t0
        _last[0] = now
        print(
            f"  [tiempo] {etiqueta}: +{desde_anterior:.2f}s desde el paso anterior | "
            f"{desde_inicio:.2f}s desde el arranque",
            flush=True,
        )

    print("Leyendo secrets.toml (credenciales)…", flush=True)
    with open(ROOT / ".streamlit" / "secrets.toml", "rb") as f:
        cfg = tomllib.load(f)
    print("OK: credenciales cargadas.", flush=True)
    pg = cfg["postgres"]
    user = quote_plus(str(pg["user"]))
    pw = quote_plus(str(pg["password"]))
    print("Creando motor SQLAlchemy (aún no conecta a red)…", flush=True)
    eng = create_engine(
        f"postgresql+psycopg2://{user}:{pw}@{pg['host']}:{pg['port']}/{pg['dbname']}?sslmode=require",
        pool_pre_ping=True,
    )
    print("OK: motor creado.", flush=True)
    lap("motor SQLAlchemy listo")

    print(f"Leyendo Excel: {xlsx_path} …", flush=True)
    df = pd.read_excel(xlsx_path, engine="openpyxl")
    print(f"OK: Excel leído — {len(df)} filas en hoja (antes de filtrar vacíos).", flush=True)
    lap(f"read_excel ({len(df)} filas)")
    df = rename_df_columns(df)
    req = {
        "linea",
        "referencia",
        "id_grupo_estilo",
        "id_tipo_1",
        "descp_grupo_estilo",
        "descp_tipo_1",
    }
    if req - set(df.columns):
        print(f"ERROR columnas obligatorias: {req - set(df.columns)}", file=sys.stderr)
        sys.exit(1)
    print("OK: columnas obligatorias presentes (incl. descripciones para maestros).", flush=True)

    pid = int(args.proveedor_id)
    chunk = max(50, min(2000, int(args.chunk)))

    sql_sync_activos = text(
        """
        WITH activos AS (
            SELECT DISTINCT ref_j.linea_id, ref_j.id AS referencia_id
            FROM pedido_proveedor_detalle ppd
            JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
            JOIN linea l ON l.codigo_proveedor::text = ppd.linea
            JOIN referencia ref_j
              ON ref_j.codigo_proveedor::text = ppd.referencia
             AND ref_j.linea_id = l.id
            WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
              AND COALESCE(ppd.cantidad_pares, 0) > 0
            UNION
            SELECT DISTINCT linea_id, referencia_id FROM precio_lista
            UNION
            SELECT DISTINCT linea_id, referencia_id FROM combinacion
            UNION
            SELECT DISTINCT linea_id, referencia_id FROM stock_bazar
            WHERE linea_id IS NOT NULL AND referencia_id IS NOT NULL
        )
        INSERT INTO linea_referencia (
            linea_id, referencia_id, proveedor_id,
            grupo_estilo_id, tipo_1_id,
            descp_grupo_estilo, descp_tipo_1
        )
        SELECT
            a.linea_id, a.referencia_id, r.proveedor_id,
            :dge, :dt1,
            (SELECT g.descp_grupo_estilo FROM grupo_estilo_v2 g WHERE g.id_grupo_estilo = :dge LIMIT 1),
            (SELECT t.descp_tipo_1 FROM tipo_1 t WHERE t.id_tipo_1 = :dt1 LIMIT 1)
        FROM activos a
        JOIN referencia r ON r.id = a.referencia_id AND r.linea_id = a.linea_id
        WHERE NOT EXISTS (
            SELECT 1 FROM linea_referencia lr
            WHERE lr.linea_id = a.linea_id AND lr.referencia_id = a.referencia_id
        )
        """
    )

    sql_verify = text(
        """
        WITH activos AS (
            SELECT DISTINCT ref_j.linea_id, ref_j.id AS referencia_id
            FROM pedido_proveedor_detalle ppd
            JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
            JOIN linea l ON l.codigo_proveedor::text = ppd.linea
            JOIN referencia ref_j
              ON ref_j.codigo_proveedor::text = ppd.referencia
             AND ref_j.linea_id = l.id
            WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
              AND COALESCE(ppd.cantidad_pares, 0) > 0
            UNION
            SELECT DISTINCT linea_id, referencia_id FROM precio_lista
            UNION
            SELECT DISTINCT linea_id, referencia_id FROM combinacion
            UNION
            SELECT DISTINCT linea_id, referencia_id FROM stock_bazar
            WHERE linea_id IS NOT NULL AND referencia_id IS NOT NULL
        )
        SELECT
            COUNT(*) FILTER (
                WHERE NOT EXISTS (
                    SELECT 1 FROM linea_referencia lr
                    WHERE lr.linea_id = a.linea_id AND lr.referencia_id = a.referencia_id
                )
            ) AS activos_sin_fila_lr,
            COUNT(*) FILTER (
                WHERE EXISTS (
                    SELECT 1 FROM linea_referencia lr
                    WHERE lr.linea_id = a.linea_id AND lr.referencia_id = a.referencia_id
                      AND lr.grupo_estilo_id IS NULL
                )
            ) AS activos_con_lr_sin_estilo
        FROM activos a
        """
    )

    def bulk_upsert_lr(
        conn,
        rows: list[dict],
        size: int,
        set_status: Callable[[str], None] | None,
    ) -> int:
        if not rows:
            print("OK: no hay filas únicas linea_referencia que aplicar.", flush=True)
            return 0
        total_chunks = (len(rows) + size - 1) // size
        n = 0
        for ci, i in enumerate(range(0, len(rows), size), start=1):
            part = rows[i : i + size]
            msg = f"linea_referencia: lote {ci}/{total_chunks} (envío de {len(part)} filas)"
            if set_status:
                set_status(msg)
            print(
                f"→ Procesando lote {ci} de {total_chunks} (linea_referencia; "
                f"acumulado {n}/{len(rows)} filas antes de este envío)…",
                flush=True,
            )
            vals = ",".join(
                "({},{},{},{},{},{},{})".format(
                    int(r["linea_id"]),
                    int(r["referencia_id"]),
                    int(r["proveedor_id"]),
                    int(r["grupo_estilo_id"]),
                    int(r["tipo_1_id"]),
                    _sql_text_lit(str(r.get("descp_grupo_estilo", ""))),
                    _sql_text_lit(str(r.get("descp_tipo_1", ""))),
                )
                for r in part
            )
            conn.execute(
                text(
                    f"""
                    INSERT INTO linea_referencia
                        (linea_id, referencia_id, proveedor_id,
                         grupo_estilo_id, tipo_1_id,
                         descp_grupo_estilo, descp_tipo_1)
                    VALUES {vals}
                    ON CONFLICT (linea_id, referencia_id)
                    DO UPDATE SET
                        grupo_estilo_id     = EXCLUDED.grupo_estilo_id,
                        tipo_1_id           = EXCLUDED.tipo_1_id,
                        proveedor_id        = EXCLUDED.proveedor_id,
                        descp_grupo_estilo  = EXCLUDED.descp_grupo_estilo,
                        descp_tipo_1        = EXCLUDED.descp_tipo_1
                    """
                )
            )
            n += len(part)
            print(f"  OK sub-lote: ahora van {n}/{len(rows)} filas aplicadas en linea_referencia.", flush=True)
        print(f"OK: todos los lotes linea_referencia aplicados ({n} filas).", flush=True)
        return n

    # --- Parse Excel (IDs reales; descripciones para maestros) ---
    excel_rows: list[dict[str, int | str]] = []
    skip_fila_incompleta = 0
    for _, row in df.iterrows():
        lid = to_int_id(row["linea"])
        rid = to_int_id(row["referencia"])
        ge = to_int_id(row["id_grupo_estilo"])
        t1 = to_int_id(row["id_tipo_1"])
        dge = str_desc(row["descp_grupo_estilo"])
        dt1 = str_desc(row["descp_tipo_1"])
        if lid is None or rid is None or ge is None or t1 is None:
            skip_fila_incompleta += 1
            continue
        excel_rows.append(
            {
                "lid": lid,
                "rid": rid,
                "ge": ge,
                "t1": t1,
                "dge": dge if dge else f"Estilo {ge}",
                "dt1": dt1 if dt1 else f"Tipo {t1}",
            }
        )
    ge_cat: dict[int, str] = {}
    t1_cat: dict[int, str] = {}
    for r in excel_rows:
        ge_cat[int(r["ge"])] = str(r["dge"])
        t1_cat[int(r["t1"])] = str(r["dt1"])
    # Pilar linea: última fila del Excel gana por id de línea (descripción, marca, género).
    linea_meta: dict[int, dict[str, Any]] = {}
    for _, row in df.iterrows():
        lid = to_int_id(row["linea"])
        if lid is None:
            continue
        ld = str_desc(row["linea_descripcion"]) if "linea_descripcion" in df.columns else ""
        mid = to_int_id(row["marca_id"]) if "marca_id" in df.columns else None
        gid = to_int_id(row["genero_id"]) if "genero_id" in df.columns else None
        linea_meta[int(lid)] = {
            "descripcion": (ld or f"Línea {lid}")[:4000],
            "marca_id": mid,
            "genero_id": gid,
        }
    if "marca_id" not in df.columns or "genero_id" not in df.columns:
        print(
            "INFO: el Excel no trae columna marca_id y/o genero_id; "
            "en BD se conservan los valores previos de esas columnas cuando el upsert recibe NULL.",
            flush=True,
        )
    if "linea_descripcion" not in df.columns:
        print(
            "INFO: el Excel no trae linea_descripcion; se usará «Línea {id}» salvo que ya exista descripcion en BD.",
            flush=True,
        )
    if skip_fila_incompleta:
        print(
            f"ERROR: {skip_fila_incompleta} filas del Excel sin los 4 IDs enteros "
            "(linea, referencia, id_grupo_estilo, id_tipo_1). Completá el archivo: cero filas incompletas.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        f"OK: Excel parseado — {len(excel_rows)} filas listas (4×INT); "
        f"maestros únicos: grupo_estilo_v2={len(ge_cat)} | tipo_1={len(t1_cat)}.",
        flush=True,
    )
    lap(f"parse en memoria ({len(excel_rows)} filas)")

    if args.dry_run:
        print(
            f"DRY-RUN: se vaciaría linea_referencia ({args.delete_lr_scope}), "
            f"forzaría linea/referencia y aplicaría {len(excel_rows)} filas Excel.",
            flush=True,
        )
        print("OK: dry-run terminado (sin tocar la base).", flush=True)
        eng.dispose()
        return

    print(
        "\nConectando a Supabase… Esto puede tardar 1 minuto; no cierres la terminal.\n"
        "Mientras tanto verás mensajes «sigo vivo» cada 60 s si la red o la BD tardan.\n",
        flush=True,
    )
    status_holder: dict[str, str] = {"msg": "preparando primera conexión"}
    stop_hb, hb_thread = _start_heartbeat(lambda: status_holder["msg"])
    n_lr = 0
    sin_lr = sin_est = -1

    def set_status(m: str) -> None:
        status_holder["msg"] = m

    try:
        with eng.begin() as conn:
            status_holder["msg"] = "vaciando linea_referencia"
            if args.delete_lr_scope == "all":
                try:
                    conn.execute(text("TRUNCATE TABLE linea_referencia RESTART IDENTITY"))
                except Exception:
                    conn.execute(text("DELETE FROM linea_referencia"))
            else:
                conn.execute(
                    text("DELETE FROM linea_referencia WHERE proveedor_id = :pid"),
                    {"pid": pid},
                )
            print("OK: linea_referencia vaciada (repoblado desde Excel).", flush=True)
            lap("purge linea_referencia")

            status_holder["msg"] = "maestros grupo_estilo_v2"
            sql_upsert_ge = text(
                """
                INSERT INTO grupo_estilo_v2 (id_grupo_estilo, descp_grupo_estilo)
                VALUES (:id, :d)
                ON CONFLICT (id_grupo_estilo) DO UPDATE SET
                    descp_grupo_estilo = EXCLUDED.descp_grupo_estilo
                """
            )
            for n_done, (gid, dsc) in enumerate(sorted(ge_cat.items()), start=1):
                conn.execute(sql_upsert_ge, {"id": int(gid), "d": str(dsc)[:2000]})
                if n_done % 400 == 0:
                    print(f"  … grupo_estilo_v2 {n_done}/{len(ge_cat)}", flush=True)
            print(f"OK: grupo_estilo_v2 — {len(ge_cat)} ids.", flush=True)
            lap("UPSERT grupo_estilo_v2")

            status_holder["msg"] = "maestros tipo_1"
            sql_upsert_t1 = text(
                """
                INSERT INTO tipo_1 (id_tipo_1, descp_tipo_1)
                VALUES (:id, :d)
                ON CONFLICT (id_tipo_1) DO UPDATE SET
                    descp_tipo_1 = EXCLUDED.descp_tipo_1
                """
            )
            for n_done, (tid, dsc) in enumerate(sorted(t1_cat.items()), start=1):
                conn.execute(sql_upsert_t1, {"id": int(tid), "d": str(dsc)[:2000]})
                if n_done % 400 == 0:
                    print(f"  … tipo_1 {n_done}/{len(t1_cat)}", flush=True)
            print(f"OK: tipo_1 — {len(t1_cat)} ids.", flush=True)
            lap("UPSERT tipo_1")

            lids = sorted({int(r["lid"]) for r in excel_rows})
            has_ld = _linea_column_exists(conn, "descripcion")
            has_mid = _linea_column_exists(conn, "marca_id")
            has_gid = _linea_column_exists(conn, "genero_id")
            status_holder["msg"] = "forzar líneas (INSERT/UPDATE por id Excel + pilar descripcion/marca/género)"
            # Otra fila puede tener ya (proveedor_id, codigo_proveedor)=(pid, lid) con id distinto →
            # choca con UNIQUE linea_proveedor_id_codigo_key antes del ON CONFLICT (id).
            sql_free_linea_codigo = text(
                """
                UPDATE linea SET codigo_proveedor = 900000000000000::bigint + id
                WHERE proveedor_id = :pid AND codigo_proveedor = :lid AND id <> :lid
                """
            )
            for n_done, lid in enumerate(lids, start=1):
                conn.execute(sql_free_linea_codigo, {"lid": int(lid), "pid": pid})
                meta = linea_meta.get(
                    int(lid),
                    {"descripcion": f"Línea {lid}", "marca_id": None, "genero_id": None},
                )
                _upsert_linea_excel(
                    conn,
                    proveedor_id=pid,
                    linea_id=int(lid),
                    meta=meta,
                    has_descripcion=has_ld,
                    has_marca_id=has_mid,
                    has_genero_id=has_gid,
                )
                if n_done % 500 == 0:
                    print(f"  … linea {n_done}/{len(lids)}", flush=True)
            print(f"OK: linea — {len(lids)} ids alineados al Excel (pilar aplicado según columnas en BD).", flush=True)
            lap("UPSERT linea")

            rid_to_lid: dict[int, int] = {}
            for r in excel_rows:
                rid_to_lid[int(r["rid"])] = int(r["lid"])

            status_holder["msg"] = "forzar referencias (INSERT/UPDATE linea_id Excel)"
            sql_free_ref_triple = text(
                """
                UPDATE referencia SET codigo_proveedor = 800000000000000::bigint + id
                WHERE proveedor_id = :pid AND linea_id = :lid AND codigo_proveedor = :rid AND id <> :rid
                """
            )
            sql_upsert_ref = text(
                """
                INSERT INTO referencia (id, proveedor_id, linea_id, codigo_proveedor)
                VALUES (:rid, :pid, :lid, :rid)
                ON CONFLICT (id) DO UPDATE SET
                    linea_id = EXCLUDED.linea_id,
                    proveedor_id = EXCLUDED.proveedor_id,
                    codigo_proveedor = EXCLUDED.codigo_proveedor
                """
            )
            for n_done, rid in enumerate(sorted(rid_to_lid.keys()), start=1):
                lid = int(rid_to_lid[rid])
                conn.execute(
                    sql_free_ref_triple,
                    {"rid": int(rid), "pid": pid, "lid": lid},
                )
                conn.execute(
                    sql_upsert_ref,
                    {"rid": int(rid), "pid": pid, "lid": lid},
                )
                if n_done % 500 == 0:
                    print(f"  … referencia {n_done}/{len(rid_to_lid)}", flush=True)
            print(f"OK: referencia — {len(rid_to_lid)} ids movidos/creados según Excel.", flush=True)
            lap("UPSERT referencia")

            status_holder["msg"] = "limpieza filas basura codigo 900…/800… (solo huérfanas)"
            sql_del_junk_linea = text(
                """
                DELETE FROM linea l
                WHERE l.proveedor_id = :pid
                  AND l.codigo_proveedor >= 900000000000000::bigint
                  AND NOT EXISTS (SELECT 1 FROM referencia r WHERE r.linea_id = l.id)
                  AND NOT EXISTS (SELECT 1 FROM linea_referencia lr WHERE lr.linea_id = l.id)
                  AND NOT EXISTS (SELECT 1 FROM combinacion c WHERE c.linea_id = l.id)
                  AND NOT EXISTS (SELECT 1 FROM precio_lista pl WHERE pl.linea_id = l.id)
                  AND NOT EXISTS (SELECT 1 FROM stock_bazar sb WHERE sb.linea_id = l.id)
                  AND NOT EXISTS (SELECT 1 FROM precio_evento_linea_excepcion pe WHERE pe.linea_id = l.id)
                  AND l.caso_id IS NULL  -- post-025: caso vive en linea.caso_id (no linea_caso)
                """
            )
            sql_del_junk_ref = text(
                """
                DELETE FROM referencia r
                WHERE r.proveedor_id = :pid
                  AND r.codigo_proveedor >= 800000000000000::bigint
                  AND NOT EXISTS (SELECT 1 FROM linea_referencia lr WHERE lr.referencia_id = r.id)
                  AND NOT EXISTS (SELECT 1 FROM combinacion c WHERE c.referencia_id = r.id)
                  AND NOT EXISTS (SELECT 1 FROM precio_lista pl WHERE pl.referencia_id = r.id)
                  AND NOT EXISTS (SELECT 1 FROM stock_bazar sb WHERE sb.referencia_id = r.id)
                """
            )
            try:
                n_jl = conn.execute(sql_del_junk_linea, {"pid": pid}).rowcount or 0
                n_jr = conn.execute(sql_del_junk_ref, {"pid": pid}).rowcount or 0
                print(
                    f"OK: limpieza códigos basura — linea eliminadas={n_jl} | referencia eliminadas={n_jr} "
                    f"(solo sin FKs en tablas de negocio).",
                    flush=True,
                )
            except Exception as ex:
                print(
                    f"AVISO: no se pudo ejecutar limpieza 900/800 (¿falta alguna tabla?): {ex}",
                    flush=True,
                )
            lap("DELETE junk linea/referencia")

            for tbl in ("linea", "referencia"):
                try:
                    conn.execute(
                        text(
                            f"""
                            SELECT setval(
                                pg_get_serial_sequence('{tbl}', 'id'),
                                GREATEST(1, COALESCE((SELECT MAX(id) FROM {tbl}), 1))
                            )
                            """
                        )
                    )
                except Exception:
                    pass

            lr_map: dict[tuple[int, int], dict] = {}
            for r in excel_rows:
                lid = int(r["lid"])
                rid = int(r["rid"])
                lr_map[(lid, rid)] = {
                    "linea_id": lid,
                    "referencia_id": rid,
                    "proveedor_id": pid,
                    "grupo_estilo_id": int(r["ge"]),
                    "tipo_1_id": int(r["t1"]),
                    "descp_grupo_estilo": str(r["dge"]),
                    "descp_tipo_1": str(r["dt1"]),
                }
            lr_rows = list(lr_map.values())
            n_excel = len(excel_rows)
            n_unique_lr = len(lr_rows)
            print(
                f"OK: armado linea_referencia — {n_excel} filas Excel aplicadas → "
                f"{n_unique_lr} filas únicas (UNIQUE linea_id+referencia_id; última gana).",
                flush=True,
            )
            lap("armado lr_map (cero omisiones por FK)")

            status_holder["msg"] = "aplicando upsert linea_referencia por lotes"
            n_lr = bulk_upsert_lr(conn, lr_rows, chunk, set_status)
            print(f"OK: COMMIT pendiente — upsert linea_referencia {n_lr} filas físicas.", flush=True)
            lap(f"bulk upsert linea_referencia ({n_lr} filas)")

            mx = conn.execute(
                text(
                    """
                    SELECT
                        (SELECT MIN(id_grupo_estilo) FROM grupo_estilo_v2) AS dge,
                        (SELECT MIN(id_tipo_1) FROM tipo_1) AS dt1
                    """
                )
            ).mappings().first()
            dge = mx["dge"]
            dt1 = mx["dt1"]
            if dge is None or dt1 is None:
                raise RuntimeError(
                    "Tras sincronizar maestros, se requiere al menos un id en grupo_estilo_v2 y tipo_1 "
                    "(necesario para sql_sync_activos)."
                )

            if args.skip_sync_activos:
                print("OK: omitido sql_sync_activos (--skip-sync-activos).", flush=True)
            else:
                status_holder["msg"] = "sql_sync_activos (CTE activos → INSERT)"
                print("Sincronizando activos → linea_referencia (puede tardar en Supabase)…", flush=True)
                conn.execute(sql_sync_activos, {"dge": int(dge), "dt1": int(dt1)})
                print("OK: sql_sync_activos terminado.", flush=True)
                lap("sql_sync_activos (CTE → INSERT)")

            status_holder["msg"] = "verificación activos_sin_fila_lr (consulta)"
            v = conn.execute(sql_verify).mappings().first()
            sin_lr = int(v["activos_sin_fila_lr"])
            sin_est = int(v["activos_con_lr_sin_estilo"])
            print("OK: consulta de verificación ejecutada.", flush=True)
            lap("sql_verify (conteos activos)")

        print("OK: transacción confirmada (COMMIT).", flush=True)
        lap("bloque with eng.begin (toda la transacción)")
    finally:
        _stop_heartbeat(stop_hb, hb_thread)
        print("OK: latido en segundo plano detenido.", flush=True)

    print(f"Resumen — linea_referencia upsert filas: {n_lr}")
    print(f"Resumen — activos_sin_fila_lr={sin_lr}  activos_con_lr_sin_estilo={sin_est}")

    if int(args.verify_linea) > 0:
        vid = int(args.verify_linea)
        print(f"\n=== Verificación pilar linea (id o codigo_proveedor = {vid}) ===", flush=True)
        try:
            with eng.connect() as vc:
                has_ld = _linea_column_exists(vc, "descripcion")
                has_mid = _linea_column_exists(vc, "marca_id")
                has_gid = _linea_column_exists(vc, "genero_id")
                parts = ["id", "codigo_proveedor"]
                if has_ld:
                    parts.append("descripcion")
                if has_mid:
                    parts.append("marca_id")
                if has_gid:
                    parts.append("genero_id")
                sel = ", ".join(parts)
                row = vc.execute(
                    text(
                        f"""
                        SELECT {sel}
                        FROM linea
                        WHERE id = :v OR codigo_proveedor = :v
                        ORDER BY CASE WHEN id = :v THEN 0 ELSE 1 END
                        LIMIT 1
                        """
                    ),
                    {"v": vid},
                ).mappings().first()
                if row is None:
                    print(f"  No hay fila en linea con id ni codigo_proveedor = {vid}.", flush=True)
                else:
                    for k in parts:
                        print(f"  {k}: {row.get(k)!r}", flush=True)
        except Exception as ex:
            print(f"  ERROR al consultar linea: {ex}", flush=True)

    print("OK: proceso terminado; cerrando motor SQLAlchemy.", flush=True)
    eng.dispose()
    print("OK: motor cerrado. Hasta la próxima.", flush=True)
    lap("dispose engine")
    total = time.perf_counter() - t0
    print(
        f"\nHecho: Nexus Dictador corrió {total:.2f}s en total. "
        f"Todas las {len(excel_rows)} filas del Excel participaron; linea_referencia recibió "
        f"{n_lr} filas físicas (pares únicos). COMMIT aplicado en Supabase.\n",
        flush=True,
    )


if __name__ == "__main__":
    main()
