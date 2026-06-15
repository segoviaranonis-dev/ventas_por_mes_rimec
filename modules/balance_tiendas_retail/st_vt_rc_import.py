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
    map_header_to_canon,
)

EXCEL_SHEET_RETAIL = "st+vt+RC"
TABLE_RETAIL = "registro_st_vt_rc_reposicion"  # Frontend /retail lee esta tabla (migración 060)

# Cabeceras logic.py → nombres CANON de st+vt+RC
_LOGIC_TO_CANON: dict[str, str] = {
    "origen_tienda": "origen_holding",
    "material_id": "excel_material_code",
    "color_id": "excel_color_code",
}

_IMAGEN_LR_RE = re.compile(r"^(\d+)\s*[-_.]\s*(\d+)\s*[-_.]")

# tipo_v2_id en BD · categorías negocio (Excel columna Tipo_v2)
TIPO_V2_CALZADO = 1       # 654 calzados Beira Rio — pilares línea+referencia obligatorios
TIPO_V2_CONFECCIONES = 2  # 638 confecciones Kyly — sin reglas STYLE/L+R; tal cual Excel

# Versión visible en UI — el operador remoto confirma que hizo git pull si coincide.
RETAIL_IMPORT_BUILD = "2026-06-15-b3"

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
    "excel_tipo_v2",
    "tipo_v2_id",
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


def _split_linea_referencia(raw: Any) -> tuple[str, str]:
    """STYLE 1184.100 · LINE-REF 1184-100 · solo línea si no hay separador."""
    s = _cell_str(raw)
    if not s:
        return "", ""
    for sep in (".", "-", "/"):
        if sep in s:
            a, b = s.split(sep, 1)
            return _cell_str(a), _cell_str(b)
    return s, ""


def _fill_linea_referencia_from_pair(df: pd.DataFrame, i: int, linea: str, ref: str) -> None:
    """i = posición iloc (no etiqueta de índice del Excel)."""
    if linea and not str(df.iloc[i]["linea_codigo_proveedor"]).strip():
        df.iloc[i, df.columns.get_loc("linea_codigo_proveedor")] = linea
    if ref and not str(df.iloc[i]["referencia_codigo_proveedor"]).strip():
        df.iloc[i, df.columns.get_loc("referencia_codigo_proveedor")] = ref


def parse_tipo_v2_id(raw: Any) -> int:
    """
    Excel Tipo_v2 → tipo_v2_id BD.
    1 / 654 / calzado / beira → CALZADO
    2 / 638 / confección / kyly → CONFECCIONES
    Vacío → CALZADO (legacy Beira Rio).
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return TIPO_V2_CALZADO
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        n = int(raw)
        if n in (TIPO_V2_CONFECCIONES, 638):
            return TIPO_V2_CONFECCIONES
        if n in (TIPO_V2_CALZADO, 654):
            return TIPO_V2_CALZADO
    s = _cell_str(raw).lower()
    if not s:
        return TIPO_V2_CALZADO
    digits = re.sub(r"\D", "", s)
    if digits in ("654", "1"):
        return TIPO_V2_CALZADO
    if digits in ("638", "2"):
        return TIPO_V2_CONFECCIONES
    if "638" in s or "confec" in s or "kyly" in s:
        return TIPO_V2_CONFECCIONES
    if "654" in s or "calz" in s or "beira" in s:
        return TIPO_V2_CALZADO
    try:
        n = int(float(s.replace(",", ".")))
        if n == TIPO_V2_CONFECCIONES:
            return TIPO_V2_CONFECCIONES
        if n == TIPO_V2_CALZADO:
            return TIPO_V2_CALZADO
    except (ValueError, TypeError):
        pass
    return TIPO_V2_CALZADO


def map_header_retail(col: str) -> str | None:
    raw = str(col).strip()
    if not raw or raw.lower().startswith("unnamed"):
        return None
    h = _norm_header(raw)
    hns = h.replace(" ", "").replace("_", "")

    # Tipo_v2 — categoría producto (654 calzado / 638 confecciones)
    if hns in ("tipov2", "tipo2", "tipov2id", "tipoproducto") or h in ("tipo v2", "tipo_v2", "tipo v2 id"):
        return "excel_tipo_v2"

    # Par línea+referencia combinado (STYLE / LINE-REF)
    if hns in ("lineref", "style", "line-ref", "linerefstyle"):
        return "line_ref_raw"
    if re.search(r"line.*ref", h, re.I) or h == "style":
        return "line_ref_raw"

    canon = map_header_to_canon(raw)
    if canon:
        mapped = _LOGIC_TO_CANON.get(canon, canon)
        if mapped in CANON:
            return mapped

    # Alias cortos no cubiertos por logic (p.unit, cod.barra…)
    exact_extra: dict[str, str] = {
        "cod.barra": "codigo_barras",
        "codbarra": "codigo_barras",
        "p.unit": "precio_unitario",
        "p.total": "monto",
        "calce": "grada",
        "imagen": "imagen_nombre",
        "lin": "linea_codigo_proveedor",
        "ref": "referencia_codigo_proveedor",
        "mat": "excel_material_code",
        "colo": "excel_color_code",
        "color": "excel_color_code",
        "material": "excel_material_code",
    }
    if h in exact_extra or hns in {k.replace(".", ""): v for k, v in exact_extra.items()}:
        return exact_extra.get(h) or exact_extra.get(hns.replace(".", ""))
    if re.search(r"cod.*barra", h, re.I):
        return "codigo_barras"
    return None


def _backfill_linea_ref_desde_imagen(df: pd.DataFrame) -> int:
    """Si LINEA/REF vacíos, intenta parsear nombre imagen tipo 9093-300-31263.jpg."""
    if "imagen_nombre" not in df.columns:
        return 0
    filled = 0
    for i in range(len(df)):
        l = str(df.iloc[i]["linea_codigo_proveedor"]).strip()
        r = str(df.iloc[i]["referencia_codigo_proveedor"]).strip()
        if l and r:
            continue
        img = _cell_str(df.iloc[i]["imagen_nombre"])
        m = _IMAGEN_LR_RE.match(img)
        if not m:
            continue
        if not l:
            df.iloc[i, df.columns.get_loc("linea_codigo_proveedor")] = m.group(1)
        if not r:
            df.iloc[i, df.columns.get_loc("referencia_codigo_proveedor")] = m.group(2)
        filled += 1
    return filled


def diagnose_retail_import(raw: pd.DataFrame, norm: pd.DataFrame) -> dict[str, Any]:
    """Diagnóstico legible cuando el import queda bloqueado."""
    mapped: list[dict[str, str | None]] = []
    for col in raw.columns:
        mapped.append({"columna_excel": str(col), "mapeo": map_header_retail(str(col))})

    vacias = norm["linea_codigo_proveedor"].eq("") | norm["referencia_codigo_proveedor"].eq("")
    if "tipo_v2_id" in norm.columns:
        calzado = norm["tipo_v2_id"] == TIPO_V2_CALZADO
        vacias_check = vacias & calzado
        n_conf = int((norm["tipo_v2_id"] == TIPO_V2_CONFECCIONES).sum())
        n_calz = int(calzado.sum())
    else:
        vacias_check = vacias
        n_conf = 0
        n_calz = len(norm)

    n_bad = int(vacias_check.sum())
    n_ok = int(len(norm) - n_bad) if "tipo_v2_id" in norm.columns else int((~vacias).sum())

    sample_bad = norm.loc[vacias_check if "tipo_v2_id" in norm.columns else vacias,
                          ["tipo_v2_id", "excel_tipo_v2", "linea_codigo_proveedor", "referencia_codigo_proveedor", "imagen_nombre"]].head(5)
    sample_ok = norm.loc[~(vacias_check if "tipo_v2_id" in norm.columns else vacias),
                         ["tipo_v2_id", "excel_tipo_v2", "linea_codigo_proveedor", "referencia_codigo_proveedor", "imagen_nombre"]].head(3)

    lr_cols = [str(c) for c in raw.columns if re.search(r"line|ref|style", str(c), re.I)]
    has_lr_mapped = any(m["mapeo"] in ("linea_codigo_proveedor", "referencia_codigo_proveedor", "line_ref_raw") for m in mapped)

    return {
        "columnas_mapeadas": mapped,
        "filas_ok": n_ok,
        "filas_sin_lr": n_bad,
        "filas_calzado": n_calz,
        "filas_confecciones": n_conf,
        "tiene_columnas_lr": has_lr_mapped,
        "tiene_tipo_v2": any(m["mapeo"] == "excel_tipo_v2" for m in mapped),
        "columnas_lr_en_excel": lr_cols,
        "muestra_ok": sample_ok.to_dict("records"),
        "muestra_mala": sample_bad.to_dict("records"),
    }


def assess_import_gate(norm: pd.DataFrame, errors: list[str], diag: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
    """¿Puede pulsarse Importar? + motivos legibles para el operador."""
    reasons: list[str] = []
    if norm is None or norm.empty:
        reasons.append("La hoja st+vt+RC no tiene filas para importar.")
    if diag:
        if not diag.get("tiene_columnas_lr"):
            reasons.append(
                "Nexus no mapeó LINEA ni REFERENCIA. Revisá cabeceras (LINEA, REFERENCIA, lin, ref o LINE-REF). "
                f"Columnas en Excel: {[m['columna_excel'] for m in diag.get('columnas_mapeadas', [])]}"
            )
        if not diag.get("tiene_tipo_v2"):
            reasons.append(
                "Columna TIPO_V2 no detectada: todas las filas se tratan como calzado (654). "
                "Para Kyly usá columna TIPO_V2 con valor 2 o 638."
            )
    for e in errors:
        if e not in reasons:
            reasons.append(e)
    return len(reasons) == 0, reasons


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
    df = df.replace("", pd.NA).dropna(how="all").reset_index(drop=True)
    return df, target, meta


def normalize_retail_dataframe(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []
    if raw is None or raw.empty:
        errors.append(f"La hoja {EXCEL_SHEET_RETAIL} no tiene filas.")
        return raw, errors

    ren: dict[str, str] = {}
    used: set[str] = set()
    line_ref_cols: list[str] = []
    for col in raw.columns:
        canon = map_header_retail(str(col))
        if canon == "line_ref_raw":
            line_ref_cols.append(str(col))
            continue
        if canon and canon not in used:
            ren[str(col)] = canon
            used.add(canon)
    df = raw.rename(columns=ren)

    if line_ref_cols:
        df["line_ref_raw"] = df[line_ref_cols[0]].astype(str)
        for extra in line_ref_cols[1:]:
            empty = df["line_ref_raw"].map(_cell_str).eq("")
            df.loc[empty, "line_ref_raw"] = df.loc[empty, extra].astype(str)

    for c in CANON:
        if c not in df.columns:
            if c in ("fecha_mov", "codigo_barras", "precio_unitario", "monto", "imagen_nombre"):
                df[c] = None
            elif c in ("origen_holding", "tipo_movimiento", "excel_tipo_v2"):
                df[c] = ""
            elif c == "grada":
                df[c] = "(sin grada)"
            else:
                df[c] = ""

    df["excel_tipo_v2"] = df["excel_tipo_v2"].map(_cell_str)
    df["tipo_v2_id"] = df["excel_tipo_v2"].map(parse_tipo_v2_id).astype(int)
    mask_calzado = df["tipo_v2_id"] == TIPO_V2_CALZADO

    if "line_ref_raw" in df.columns:
        for i, raw_lr in enumerate(df["line_ref_raw"]):
            if not mask_calzado.iloc[i]:
                continue
            linea, ref = _split_linea_referencia(raw_lr)
            _fill_linea_referencia_from_pair(df, i, linea, ref)
        df = df.drop(columns=["line_ref_raw"], errors="ignore")

    # STYLE 1184.100 — solo calzado (tipo_v2=1)
    for i in range(len(df)):
        if not mask_calzado.iloc[i]:
            continue
        if str(df.iloc[i]["linea_codigo_proveedor"]).strip() and str(df.iloc[i]["referencia_codigo_proveedor"]).strip():
            continue
        linea, ref = _split_linea_referencia(df.iloc[i]["linea_codigo_proveedor"])
        if ref:
            _fill_linea_referencia_from_pair(df, i, linea, ref)

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

    n_img = 0
    if mask_calzado.any():
        sub = df.loc[mask_calzado].copy()
        n_img = _backfill_linea_ref_desde_imagen(sub)
        df.loc[mask_calzado, ["linea_codigo_proveedor", "referencia_codigo_proveedor"]] = sub[
            ["linea_codigo_proveedor", "referencia_codigo_proveedor"]
        ].values

    vacias = df["linea_codigo_proveedor"].eq("") | df["referencia_codigo_proveedor"].eq("")
    vacias_calzado = vacias & mask_calzado
    n_conf = int((df["tipo_v2_id"] == TIPO_V2_CONFECCIONES).sum())
    n_calz = int(mask_calzado.sum())

    if vacias_calzado.any():
        n = int(vacias_calzado.sum())
        hint = (
            f"Hay {n} filas **calzado** (tipo_v2=1/654) sin línea o referencia. "
            "Revisá **LINEA** + **REFERENCIA** o **STYLE** `9093.300`. "
            f"Confecciones Kyly (tipo_v2=2/638): {n_conf} filas — no exigen L+R."
        )
        if n_img:
            hint += f" Desde IMAGEN se completaron {n_img} filas calzado; aún faltan {n}."
        errors.append(hint)

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
    # MODIFICADO: linea_id y referencia_id ahora se resuelven en fk_resolve (no backfill manual)
    out["linea_id"] = resolved["linea_id"]
    out["referencia_id"] = resolved["referencia_id"]
    # NUEVO: cliente_id derivado desde origen_holding + marca_id (Venta en Tienda)
    out["cliente_id"] = resolved["cliente_id"]
    # NUEVO: tipo_v2_id (1=CALZADO, futuro 2=CONFECCIONES)
    out["tipo_v2_id"] = resolved["tipo_v2_id"]
    out["archivo_origen"] = (archivo_origen or "").strip() or None
    out["excel_sheet"] = excel_sheet
    out["created_by"] = (created_by or "").strip() or None

    cols = [
        "batch_id", "batch_label", "fecha_mov", "origen_holding", "tipo_movimiento",
        "codigo_barras", "linea_codigo_proveedor", "referencia_codigo_proveedor",
        "excel_material_code", "excel_color_code",
        "material_id", "color_id", "linea_id", "referencia_id",
        "marca_id", "genero_id", "grupo_estilo_id", "tipo_1_id",
        "cliente_id", "tipo_v2_id",  # NUEVO: Para Venta en Tienda
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
