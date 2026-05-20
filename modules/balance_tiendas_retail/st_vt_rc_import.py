"""
Retail — Excel VTA SM, hoja única «st+vt+RC» → public.registro_st_vt_rc_reposicion.

Sales Report usa registro_ventas_general_v2 (otro Excel). No mezclar.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from modules.balance_tiendas_retail.fk_resolve import resolve_retail_fks
from modules.balance_tiendas_retail.logic import (
    _excel_scalar_to_float,
    _norm_header,
    _series_excel_float,
)

EXCEL_SHEET_RETAIL = "st+vt+RC"
TABLE_RETAIL = "registro_st_vt_rc_reposicion"  # Frontend /retail lee esta tabla (migración 060)

CANON = [
    "origen_holding",
    "tipo_movimiento",
    "fecha_mov",
    "codigo_barras",
    "linea_codigo_proveedor",
    "referencia_codigo_proveedor",
    "excel_material_code",
    "excel_color_code",
    "grada",
    "cantidad",
    "precio_unitario",
    "monto",
    "imagen_nombre",
]


def _cell_str(v: Any) -> str:
    if pd.isna(v):
        return ""
    if isinstance(v, (int, float)):
        try:
            if float(v) == int(float(v)):
                return str(int(float(v)))
        except (ValueError, TypeError):
            pass
    return str(v).strip()


def sheet_es_retail(name: str) -> bool:
    s = re.sub(r"\s+", "", str(name or "").strip().casefold())
    return s == re.sub(r"\s+", "", EXCEL_SHEET_RETAIL.casefold())


def map_header_retail(col: str) -> str | None:
    raw = str(col).strip()
    if not raw or raw.lower().startswith("unnamed"):
        return None
    h = _norm_header(raw)
    hns = h.replace(" ", "")

    exact: dict[str, str] = {
        "cod.barra": "codigo_barras",
        "codbarra": "codigo_barras",
        "line-ref": "line_ref_raw",
        "linea": "linea_codigo_proveedor",
        "línea": "linea_codigo_proveedor",
        "ref": "referencia_codigo_proveedor",
        "referencia": "referencia_codigo_proveedor",
        "mat": "excel_material_code",
        "material": "excel_material_code",
        "color": "excel_color_code",
        "imagen": "imagen_nombre",
        "grada": "grada",
        "calce": "grada",
        "cantidad": "cantidad",
        "p.unit": "precio_unitario",
        "p.total": "monto",
        "monto": "monto",
        "tienda": "origen_holding",
        "tipo": "tipo_movimiento",
        "fecha": "fecha_mov",
    }
    if h in exact or hns in {k.replace(" ", ""): v for k, v in exact.items()}:
        return exact.get(h) or exact.get(hns)
    if re.search(r"cod.*barra", h, re.I):
        return "codigo_barras"
    if re.search(r"line.*ref", h, re.I):
        return "line_ref_raw"
    if h in ("linea", "línea"):
        return "linea_codigo_proveedor"
    if h in ("ref", "referencia"):
        return "referencia_codigo_proveedor"
    if re.search(r"precio.*unit|p\.?\s*unit", h, re.I):
        return "precio_unitario"
    if re.search(r"p\.?\s*total|^total$", h, re.I) and "linea" not in h:
        return "monto"
    return None


def read_excel_retail_sheet(
    file_like,
    *,
    engine: str = "openpyxl",
) -> tuple[pd.DataFrame, str | None, list[dict[str, Any]]]:
    if hasattr(file_like, "seek"):
        try:
            file_like.seek(0)
        except Exception:
            pass
    xl = pd.ExcelFile(file_like, engine=engine)
    meta: list[dict[str, Any]] = []
    target: str | None = None
    for sheet in xl.sheet_names:
        if sheet_es_retail(sheet):
            target = sheet
            break
    for sheet in xl.sheet_names:
        meta.append(
            {
                "hoja": sheet,
                "importada": sheet_es_retail(sheet),
                "motivo": "Retail (st+vt+RC)" if sheet_es_retail(sheet) else "no vinculada",
            }
        )
    if target is None:
        return pd.DataFrame(), None, meta

    df = pd.read_excel(xl, sheet_name=target, engine=engine, dtype=object, keep_default_na=False)
    df = df.replace("", pd.NA).dropna(how="all")
    return df, target, meta


def normalize_retail_dataframe(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []
    if raw is None or raw.empty:
        errors.append(f"La hoja {EXCEL_SHEET_RETAIL} no tiene filas.")
        return raw, errors

    ren: dict[str, str] = {}
    used: set[str] = set()
    for col in raw.columns:
        canon = map_header_retail(str(col))
        if canon and canon not in ("line_ref_raw",) and canon not in used:
            ren[str(col)] = canon
            used.add(canon)
    df = raw.rename(columns=ren)

    for c in CANON:
        if c not in df.columns:
            if c in ("fecha_mov", "codigo_barras", "precio_unitario", "monto", "imagen_nombre"):
                df[c] = None
            elif c in ("origen_holding", "tipo_movimiento"):
                df[c] = ""
            elif c == "grada":
                df[c] = "(sin grada)"
            else:
                df[c] = ""

    if "line_ref_raw" in df.columns:
        for i, raw_lr in enumerate(df["line_ref_raw"]):
            s = _cell_str(raw_lr)
            if not s or "-" not in s:
                continue
            a, b = s.split("-", 1)
            if not str(df.at[i, "linea_codigo_proveedor"]).strip():
                df.at[i, "linea_codigo_proveedor"] = a.strip()
            if not str(df.at[i, "referencia_codigo_proveedor"]).strip():
                df.at[i, "referencia_codigo_proveedor"] = b.strip()
        df = df.drop(columns=["line_ref_raw"], errors="ignore")

    for col in ("linea_codigo_proveedor", "referencia_codigo_proveedor"):
        df[col] = df[col].map(_cell_str)
    for col in ("excel_material_code", "excel_color_code", "codigo_barras", "imagen_nombre"):
        df[col] = df[col].map(lambda v: _cell_str(v) if _cell_str(v) else None)

    df["origen_holding"] = df["origen_holding"].map(_cell_str)
    df["tipo_movimiento"] = df["tipo_movimiento"].map(_cell_str)
    df["grada"] = df["grada"].map(lambda v: _cell_str(v) if _cell_str(v) else "(sin grada)")

    if df["fecha_mov"].notna().any():
        df["fecha_mov"] = pd.to_datetime(df["fecha_mov"], dayfirst=True, errors="coerce").dt.date
    else:
        df["fecha_mov"] = None

    df["cantidad"] = _series_excel_float(df["cantidad"]).fillna(0)
    df["precio_unitario"] = _series_excel_float(df["precio_unitario"])
    df["monto"] = _series_excel_float(df["monto"])

    vacias = df["linea_codigo_proveedor"].eq("") | df["referencia_codigo_proveedor"].eq("")
    if vacias.any():
        errors.append(f"Hay {int(vacias.sum())} filas sin línea o referencia.")

    return df[CANON].copy(), errors


def count_all_rows(engine: Engine) -> int:
    q = text(f"SELECT COUNT(*)::bigint FROM public.{TABLE_RETAIL}")
    with engine.connect() as c:
        return int(c.execute(q).scalar() or 0)


def purge_all_retail(engine: Engine) -> int:
    """Borra todo el contenido de registro_st_vt_rc_reposicion (reemplazo total por import)."""
    q = text(f"DELETE FROM public.{TABLE_RETAIL}")
    with engine.begin() as conn:
        r = conn.execute(q)
        return int(r.rowcount or 0)


def insert_batch(
    engine: Engine,
    df: pd.DataFrame,
    *,
    batch_label: str | None,
    archivo_origen: str | None,
    excel_sheet: str,
    created_by: str | None,
    progress_cb: Callable[[str, float | None], None] | None = None,
    replace_all: bool = True,
) -> tuple[str, int, int]:
    """
  Importa un lote. Si replace_all=True (default), elimina TODOS los registros previos
    en la tabla y deja solo este Excel.
    Returns: (batch_id, filas_borradas, filas_insertadas)
    """
    bid = str(uuid.uuid4())

    def _progress(msg: str, pct: float | None = None) -> None:
        if progress_cb:
            progress_cb(msg, pct)

    n_deleted = 0
    if replace_all:
        _progress("Eliminando registros Retail anteriores…", 0.12)
        n_deleted = purge_all_retail(engine)

    work = df.copy()
    work["material_id"] = pd.to_numeric(work["excel_material_code"], errors="coerce")
    work["color_id"] = pd.to_numeric(work["excel_color_code"], errors="coerce")
    _progress("Pilares (filtros / imágenes)…", 0.25)
    resolved, _ = resolve_retail_fks(engine, work)

    out = df.copy()
    out.insert(0, "batch_id", bid)
    out.insert(1, "batch_label", (batch_label or "").strip() or None)
    # FKs desde resolve_retail_fks
    out["material_id"] = resolved["material_id"]
    out["color_id"] = resolved["color_id"]
    out["marca_id"] = resolved["marca_id"]
    out["genero_id"] = resolved["genero_id"]
    out["grupo_estilo_id"] = resolved["grupo_estilo_id"]
    out["tipo_1_id"] = resolved["tipo_1_id"]
    # linea_id y referencia_id: resolver desde códigos proveedor (backfill en migración 063)
    out["linea_id"] = pd.NA
    out["referencia_id"] = pd.NA
    out["archivo_origen"] = (archivo_origen or "").strip() or None
    out["excel_sheet"] = excel_sheet
    out["created_by"] = (created_by or "").strip() or None

    cols = [
        "batch_id", "batch_label", "fecha_mov", "origen_holding", "tipo_movimiento",
        "codigo_barras", "linea_codigo_proveedor", "referencia_codigo_proveedor",
        "excel_material_code", "excel_color_code",
        "material_id", "color_id", "linea_id", "referencia_id",
        "marca_id", "genero_id", "grupo_estilo_id", "tipo_1_id",
        "grada", "cantidad", "precio_unitario", "monto", "imagen_nombre",
        "archivo_origen", "excel_sheet", "created_by",
    ]

    _progress(f"Grabando {TABLE_RETAIL} ({len(out)} filas)…", 0.7)
    with engine.begin() as conn:
        out[cols].to_sql(
            TABLE_RETAIL, conn, schema="public",
            if_exists="append", index=False, method="multi", chunksize=500,
        )
    n_inserted = len(out)
    _progress("Listo.", 1.0)
    return bid, n_deleted, n_inserted


def list_batches(engine: Engine, limit: int = 30) -> pd.DataFrame:
    q = text(f"""
        SELECT batch_id::text AS batch_id, MAX(batch_label) AS batch_label,
               MAX(archivo_origen) AS archivo_origen,
               MIN(fecha_mov) AS fecha_desde, MAX(fecha_mov) AS fecha_hasta,
               COUNT(*)::bigint AS filas, MAX(created_at) AS created_at
        FROM public.{TABLE_RETAIL}
        GROUP BY batch_id ORDER BY MAX(created_at) DESC LIMIT :lim
    """)
    with engine.connect() as c:
        return pd.read_sql(q, c, params={"lim": limit})


def count_batch_rows(engine: Engine, batch_id: str) -> int:
    q = text(f"SELECT COUNT(*)::bigint FROM public.{TABLE_RETAIL} WHERE batch_id = CAST(:b AS uuid)")
    with engine.connect() as c:
        return int(c.execute(q, {"b": batch_id}).scalar() or 0)


def delete_batch(engine: Engine, batch_id: str) -> int:
    q = text(f"DELETE FROM public.{TABLE_RETAIL} WHERE batch_id = CAST(:b AS uuid)")
    with engine.begin() as conn:
        r = conn.execute(q, {"b": batch_id})
        return int(r.rowcount or 0)


def table_missing(exc: BaseException) -> bool:
    s = str(exc).lower()
    return TABLE_RETAIL in s and ("does not exist" in s or "undefinedtable" in s)


def migration_sql_path() -> Path:
    return Path(__file__).resolve().parents[2] / "migrations" / "060_registro_st_vt_rc_reposicion.sql"
