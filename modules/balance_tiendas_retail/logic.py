"""
Lógica: Excel multi-tienda → public.retail_multitienda_staging (Supabase).

Columnas esperadas (cabeceras flexibles, ver map_header_to_canon). Marca / género /
estilo / tipo_1 no vienen en el Excel: se resuelven a FK desde linea + linea_referencia;
si el par falta y línea+ref son numéricos, `fk_resolve` da de alta el par en pilares
(coherencia por bloque de mil líneas) antes de resolver dimensiones.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

from modules.balance_tiendas_retail.fk_resolve import _canon_codigo_pilar, resolve_retail_fks

# Cabeceras canónicas obligatorias (Excel)
CANON = (
    "origen_tienda",
    "tipo_movimiento",
    "fecha_mov",
    "linea_code",
    "referencia_code",
    "material_id",
    "color_id",
    "grada",
    "cantidad",
    "precio_unitario",
    "monto",
)


def _norm_header(h: str) -> str:
    s = str(h).strip()
    # BOM / caracteres raros de Excel
    s = s.replace("\ufeff", "").replace("\xa0", " ")
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    # Guiones tipográficos → ASCII
    s = s.replace("–", "-").replace("—", "-")
    return s


def _header_collapses(h: str) -> set[str]:
    """Variantes de la misma cabecera para buscar en tablas de sinónimos."""
    h = _norm_header(h)
    out = {h}
    hn = h.replace(" ", "").replace(".", "").replace("_", "")
    out.add(hn)
    # sin acentos comunes (solo para match en tabla)
    trans = str.maketrans("áéíóúñ", "aeioun")
    out.add(h.translate(trans))
    out.add(h.replace(" ", "").translate(trans))
    return {x for x in out if x}


def map_header_to_canon(col: str) -> str | None:
    """
    Mapea cabecera Excel (español / variaciones) → nombre canónico CANON.

    Orden: coincidencias exactas por variante → patrones regex (más específicos primero)
    → reglas por palabra clave (evitando falsos positivos en «cantidad»).
    """
    raw_label = str(col).strip()
    if not raw_label or raw_label.lower().startswith("unnamed"):
        return None

    variants = _header_collapses(raw_label)

    # --- 1) Tabla amplia de sinónimos (clave normalizada sin espacios opcional) ---
    exact: dict[str, str] = {
        # Origen / tienda
        "tienda": "origen_tienda",
        "origen": "origen_tienda",
        "sucursal": "origen_tienda",
        "local": "origen_tienda",
        "origen tienda": "origen_tienda",
        "origen_tienda": "origen_tienda",
        "punto de venta": "origen_tienda",
        "punto venta": "origen_tienda",
        "pdv": "origen_tienda",
        "canal": "origen_tienda",
        "ubicacion": "origen_tienda",
        "ubicación": "origen_tienda",
        # Tipo movimiento
        "tipo": "tipo_movimiento",
        "movimiento": "tipo_movimiento",
        "tipo movimiento": "tipo_movimiento",
        "tipo_movimiento": "tipo_movimiento",
        "tipo mov": "tipo_movimiento",
        "tipo_mov": "tipo_movimiento",
        "mov": "tipo_movimiento",
        # Fecha
        "fecha": "fecha_mov",
        "fecha mov": "fecha_mov",
        "fecha movimiento": "fecha_mov",
        "fecha_mov": "fecha_mov",
        "fecha documento": "fecha_mov",
        "fecha doc": "fecha_mov",
        "f mov": "fecha_mov",
        # Línea / referencia
        "linea": "linea_code",
        "línea": "linea_code",
        "linea codigo": "linea_code",
        "línea codigo": "linea_code",
        "cod linea": "linea_code",
        "cod. linea": "linea_code",
        "código linea": "linea_code",
        "codigo linea": "linea_code",
        "cod línea": "linea_code",
        "nro linea": "linea_code",
        "n° linea": "linea_code",
        "nº linea": "linea_code",
        "linea cod": "linea_code",
        "codigo de linea": "linea_code",
        "referencia": "referencia_code",
        "ref": "referencia_code",
        "ref.": "referencia_code",
        "referencia codigo": "referencia_code",
        "referencia código": "referencia_code",
        "cod referencia": "referencia_code",
        "cod. referencia": "referencia_code",
        "cod ref": "referencia_code",
        "cod. ref": "referencia_code",
        "código referencia": "referencia_code",
        "nro referencia": "referencia_code",
        "n° referencia": "referencia_code",
        "nº referencia": "referencia_code",
        # Material / color (códigos proveedor)
        "material": "material_id",
        "material id": "material_id",
        "material_id": "material_id",
        "cod material": "material_id",
        "cod. material": "material_id",
        "código material": "material_id",
        "codigo material": "material_id",
        "id material": "material_id",
        "mat": "material_id",
        "mat.": "material_id",
        "color": "color_id",
        "color id": "color_id",
        "color_id": "color_id",
        "cod color": "color_id",
        "cod. color": "color_id",
        "código color": "color_id",
        "codigo color": "color_id",
        "id color": "color_id",
        "col": "color_id",
        "col.": "color_id",
        # Grada / talla
        "grada": "grada",
        "talla": "grada",
        "tallas": "grada",
        "curva": "grada",
        "gradacion": "grada",
        "gradación": "grada",
        "grade": "grada",
        # Cantidad / precio / monto
        "cantidad": "cantidad",
        "qty": "cantidad",
        "uds": "cantidad",
        "uds.": "cantidad",
        "unidades": "cantidad",
        "pares": "cantidad",
        "pairs": "cantidad",
        "precio unitario": "precio_unitario",
        "precio_unitario": "precio_unitario",
        "p unitario": "precio_unitario",
        "p. unitario": "precio_unitario",
        "p unit": "precio_unitario",
        "pu": "precio_unitario",
        "precio u": "precio_unitario",
        "precio venta": "precio_unitario",
        "valor unitario": "precio_unitario",
        "valor unit": "precio_unitario",
        "monto": "monto",
        "importe": "monto",
        "subtotal": "monto",
        "monto gs": "monto",
        "monto guaranies": "monto",
        "monto guaraníes": "monto",
        "total gs": "monto",
        "valor total": "monto",
        "total venta": "monto",
    }

    h = _norm_header(raw_label)
    hnospace = h.replace(" ", "")

    for key, canon in exact.items():
        if h == key or hnospace == key.replace(" ", ""):
            return canon

    for v in variants:
        if v in exact:
            return exact[v]

    # --- 2) Patrones regex (orden: más específicos primero) ---
    patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"tipo\s*mov|movimiento|tipo\s*de\s*mov", re.I), "tipo_movimiento"),
        (re.compile(r"^(fecha|f\.?)\b.*(mov|doc|oper)", re.I), "fecha_mov"),
        (re.compile(r"^(fecha)\b$", re.I), "fecha_mov"),
        (re.compile(r"(cod|nro|n°|nº|#).*\blinea", re.I), "linea_code"),
        (re.compile(r"\blinea\b.*(cod|nro|n°|id)\b", re.I), "linea_code"),
        (re.compile(r"^linea$", re.I), "linea_code"),
        (re.compile(r"(cod|nro|n°|nº|#).*\brefer", re.I), "referencia_code"),
        (re.compile(r"\bref(erencia)?\b.*(cod|nro|n°|id)\b", re.I), "referencia_code"),
        (re.compile(r"^ref$", re.I), "referencia_code"),
        (re.compile(r"(cod|id).*\bmat", re.I), "material_id"),
        (re.compile(r"\bmat(er)?\b.*(cod|id)\b", re.I), "material_id"),
        (re.compile(r"(cod|id).*\bcol", re.I), "color_id"),
        (re.compile(r"\bcol(or)?\b.*(cod|id)\b", re.I), "color_id"),
        (re.compile(r"precio.*unit|unit.*precio|valor\s*unit", re.I), "precio_unitario"),
        (re.compile(r"^pu$", re.I), "precio_unitario"),
        (re.compile(r"\b(importe|monto)\b", re.I), "monto"),
        (re.compile(r"^(total|valor)\s*(gs|gs\.|guaran)", re.I), "monto"),
        (re.compile(r"^(origen|tienda|sucursal|local|pdv)\b", re.I), "origen_tienda"),
    ]
    for rx, canon in patterns:
        if rx.search(raw_label) or rx.search(h):
            return canon

    # --- 3) Reglas por subcadena (cuidado con falsos positivos) ---
    if h in ("gradación", "gradacion", "gradas", "grade_range", "tallas", "curva"):
        return "grada"

    if "precio" in hnospace and "unitario" in hnospace:
        return "precio_unitario"

    if hnospace == "monto" or (h.startswith("monto") and "unit" not in hnospace):
        return "monto"
    if h in ("importe", "subtotal"):
        return "monto"
    if h in ("total", "valor") and "unit" not in hnospace and "linea" not in hnospace and "ref" not in hnospace:
        return "monto"

    # Cantidad: evitar "subcantidad", "cantidad max", etc.
    if re.match(r"^cantidad\b", h) and "max" not in hnospace and "min" not in hnospace:
        return "cantidad"
    if hnospace in ("qty", "uds", "unidades", "pares", "pairs"):
        return "cantidad"
    if h == "unidades" or h == "uds.":
        return "cantidad"

    return None


def _normalize_tipo_movimiento_cell(v: str) -> str:
    """Normaliza texto Excel → Stock / Venta (tolerante a abreviaturas)."""
    s = (v or "").strip()
    if not s:
        return ""
    sl = re.sub(r"\s+", " ", s.lower()).strip()
    slc = re.sub(r"\s+", "", sl)
    if slc in ("nan", "none", "<na>", "nat"):
        return ""
    if slc.startswith("vent") or slc in ("ventas", "sales", "sale"):
        return "Venta"
    if slc in ("stock", "stk", "inventario", "stck") or "stock" in slc:
        return "Stock"
    t = s.strip().title()
    return t if t in ("Venta", "Stock") else t


def _excel_scalar_to_float(val: Any) -> float:
    """Interpreta números con coma decimal / miles (típico Excel regional)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return float("nan")
    if isinstance(val, bool):
        return float("nan")
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("\xa0", "").replace(" ", "")
    if not s or s.lower() in ("nan", "none", "-", "—", "na"):
        return float("nan")
    for suf in ("gs", "pyg", "guaranies", "guaraníes", "gs."):
        if s.lower().endswith(suf):
            s = s[: -len(suf)].strip()
            break
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def _series_excel_float(s: pd.Series) -> pd.Series:
    return s.map(_excel_scalar_to_float)


def read_excel_all_sheets(
    file_like, *, engine: str = "openpyxl"
) -> tuple[pd.DataFrame, list[str], list[dict[str, Any]]]:
    """
    Lee todas las hojas con celdas como texto (object) para no perder gradas tipo
    ``34(1 2 3 3 2 1)39`` ni filas en hojas distintas a la primera (p. ej. Importadora).

    Returns:
        (DataFrame concatenado, nombres de hoja incluidas, metadatos por hoja para diagnóstico)
    """
    if hasattr(file_like, "seek"):
        try:
            file_like.seek(0)
        except Exception:
            pass
    xl = pd.ExcelFile(file_like, engine=engine)
    frames: list[pd.DataFrame] = []
    used_sheets: list[str] = []
    meta: list[dict[str, Any]] = []
    for sheet in xl.sheet_names:
        df_sheet = pd.read_excel(
            xl,
            sheet_name=sheet,
            engine=engine,
            dtype=object,
            keep_default_na=False,
        )
        if df_sheet is None or df_sheet.empty:
            meta.append(
                {
                    "hoja": sheet,
                    "filas_leidas": 0,
                    "filas_tras_limpiar": 0,
                    "filas_descartadas": 0,
                    "omitida": True,
                }
            )
            print(f"[RETAIL-STAGING] hoja omitida (vacía): {sheet!r}", flush=True)
            continue
        n_before = len(df_sheet)
        df_sheet = df_sheet.replace("", pd.NA).dropna(how="all")
        n_after = len(df_sheet)
        dropped = n_before - n_after
        meta.append(
            {
                "hoja": sheet,
                "filas_leidas": n_before,
                "filas_tras_limpiar": n_after,
                "filas_descartadas": dropped,
                "omitida": False,
            }
        )
        print(
            f"[RETAIL-STAGING] hoja={sheet!r} filas_leidas={n_before} "
            f"tras_quitar_filas_todas_na={n_after} descartadas={dropped}",
            flush=True,
        )
        if df_sheet.empty:
            continue
        frames.append(df_sheet)
        used_sheets.append(sheet)
    if not frames:
        print("[RETAIL-STAGING] ninguna hoja con datos; raw vacío", flush=True)
        return pd.DataFrame(), used_sheets, meta
    raw = pd.concat(frames, ignore_index=True)
    print(
        f"[RETAIL-STAGING] concat total_filas={len(raw)} hojas_con_datos={used_sheets!r}",
        flush=True,
    )
    return raw, used_sheets, meta


def normalize_excel_dataframe(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Renombra columnas al modelo staging; devuelve (df, errores)."""
    errors: list[str] = []
    ren: dict[str, str] = {}
    used: set[str] = set()
    for c in raw.columns:
        canon = map_header_to_canon(str(c))
        if not canon:
            continue
        if canon in used:
            errors.append(
                f"Cabecera duplicada para el mismo dato «{canon}»: se mantiene la primera columna; "
                f"se ignora {str(c)!r}."
            )
            continue
        ren[c] = canon
        used.add(canon)
    df = raw.rename(columns=ren)
    print(f"[RETAIL-STAGING] mapeo Excel→canon: {ren}", flush=True)
    print(
        f"[RETAIL-STAGING] normalize entrada filas={len(df)} n_columnas={len(df.columns)}",
        flush=True,
    )
    missing = [c for c in CANON if c not in df.columns]
    if missing:
        errors.append(f"Faltan columnas (o cabeceras no reconocidas): {', '.join(missing)}")
        return df, errors

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

    df = df[list(CANON)].copy()

    # Tipos (evitar astype(str) sobre NaN → literal "nan" en origen/tipo)
    df["origen_tienda"] = df["origen_tienda"].map(_cell_str)
    df["tipo_movimiento"] = df["tipo_movimiento"].map(_cell_str).map(_normalize_tipo_movimiento_cell)
    bad_tipo = ~df["tipo_movimiento"].isin(["Stock", "Venta"])
    if bad_tipo.any():
        errors.append(
            f"Tipo inválido (use Stock o Venta): {df.loc[bad_tipo, 'tipo_movimiento'].unique()[:5].tolist()}"
        )

    df["fecha_mov"] = pd.to_datetime(df["fecha_mov"], dayfirst=True, errors="coerce").dt.date
    if df["fecha_mov"].isna().any():
        errors.append("Hay fechas no parseables (use DD/MM/YYYY).")

    for col in ("linea_code", "referencia_code"):
        df[col] = df[col].map(_cell_str)

    def _grada_str(v: Any) -> str:
        """Preserva curvas tipo 34(1 2 3 3 2 1)39; evita '34.0' y literales 'nan'."""
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        if isinstance(v, str):
            s = v.strip()
            if s.lower() in ("nan", "none", "<na>", "nat"):
                return ""
            return s
        if isinstance(v, (int, float)):
            try:
                fv = float(v)
                if fv == int(fv):
                    return str(int(fv))
            except (ValueError, TypeError, OverflowError):
                pass
        s = str(v).strip()
        if s.lower() in ("nan", "none", "<na>", "nat"):
            return ""
        return s

    df["grada"] = df["grada"].map(_grada_str)
    # NOT NULL en BD: marcador si la celda venía vacía o ilegible
    df.loc[df["grada"] == "", "grada"] = "(sin grada)"

    for col in ("material_id", "color_id"):
        df[col] = _series_excel_float(df[col])
    if df["material_id"].isna().any() or df["color_id"].isna().any():
        errors.append("material_id o color_id no numéricos en alguna fila.")

    df["cantidad"] = _series_excel_float(df["cantidad"]).fillna(0)
    df["precio_unitario"] = _series_excel_float(df["precio_unitario"])
    df["monto"] = _series_excel_float(df["monto"])

    print(f"[RETAIL-STAGING] normalize salida filas={len(df)} errores={len(errors)}", flush=True)
    return df, errors


def insert_batch(
    engine,
    df: pd.DataFrame,
    *,
    batch_label: str | None,
    archivo_origen: str | None,
    created_by: str | None,
) -> str:
    """Inserta filas normalizadas con un mismo batch_id. Devuelve batch_id UUID string."""
    bid = str(uuid.uuid4())
    bl = (batch_label or "").strip() or None
    ao = (archivo_origen or "").strip() or None
    cb = (created_by or "").strip() or None

    df = df.copy()
    df, _fk_warns = resolve_retail_fks(engine, df)
    df.insert(0, "batch_id", bid)
    df.insert(1, "batch_label", bl)
    df["archivo_origen"] = ao
    df["created_by"] = cb

    cols = [
        "batch_id",
        "batch_label",
        "origen_tienda",
        "tipo_movimiento",
        "fecha_mov",
        "linea_code",
        "referencia_code",
        "material_id",
        "color_id",
        "grada",
        "cantidad",
        "precio_unitario",
        "monto",
        "marca_id",
        "genero_id",
        "grupo_estilo_id",
        "tipo_1_id",
        "archivo_origen",
        "created_by",
    ]
    out = df[cols]
    n = len(out)
    print(
        f"[RETAIL-STAGING] insert_batch INICIO batch_id={bid} filas_a_insertar={n} "
        f"archivo={ao!r}",
        flush=True,
    )
    with engine.begin() as conn:
        out.to_sql(
            "retail_multitienda_staging",
            conn,
            schema="public",
            if_exists="append",
            index=False,
            method="multi",
            chunksize=500,
        )
    print(f"[RETAIL-STAGING] insert_batch FIN batch_id={bid} filas_esperadas={n}", flush=True)
    return bid


def count_batch_rows(engine, batch_id: str) -> int:
    """Cuenta filas en Supabase para un lote (verificación post-import)."""
    q = text(
        "SELECT COUNT(*)::int FROM public.retail_multitienda_staging "
        "WHERE batch_id = CAST(:b AS uuid)"
    )
    with engine.connect() as c:
        v = c.execute(q, {"b": batch_id}).scalar()
    return int(v or 0)


def list_batches(engine) -> pd.DataFrame:
    q = text("""
        SELECT
            batch_id::text AS batch_id,
            COALESCE(batch_label, '') AS batch_label,
            COALESCE(archivo_origen, '') AS archivo_origen,
            MIN(fecha_mov) AS fecha_min,
            MAX(fecha_mov) AS fecha_max,
            COUNT(*)::int AS filas,
            MAX(created_at) AS cargado_en
        FROM public.retail_multitienda_staging
        GROUP BY batch_id, batch_label, archivo_origen
        ORDER BY MAX(created_at) DESC
        LIMIT 50
    """)
    with engine.connect() as c:
        return pd.read_sql(q, c)


def delete_batch(engine, batch_id: str) -> int:
    with engine.begin() as conn:
        r = conn.execute(
            text("DELETE FROM public.retail_multitienda_staging WHERE batch_id = CAST(:b AS uuid)"),
            {"b": batch_id},
        )
        return r.rowcount or 0


def refresh_batch_fks(engine, batch_id: str, *, proveedor_id: int | None = None) -> int:
    """
    Recalcula marca_id, genero_id, grupo_estilo_id, tipo_1_id y resolución material/color
    para todas las filas del lote (útil si se importó con lógica vieja o catálogo incompleto).
    """
    q = text(
        """
        SELECT id, linea_code, referencia_code, material_id, color_id
        FROM public.retail_multitienda_staging
        WHERE batch_id = CAST(:b AS uuid)
        ORDER BY id
        """
    )
    with engine.connect() as c:
        df = pd.read_sql(q, c, params={"b": batch_id})
    if df.empty:
        return 0
    work = df[["linea_code", "referencia_code", "material_id", "color_id"]].copy()
    resolved, warns = resolve_retail_fks(engine, work, proveedor_id=proveedor_id)
    n = len(df)
    with engine.begin() as conn:
        for i in range(n):
            rid = int(df.iloc[i]["id"])
            conn.execute(
                text(
                    """
                    UPDATE public.retail_multitienda_staging
                    SET marca_id = CAST(:mid AS bigint),
                        genero_id = CAST(:gid AS bigint),
                        grupo_estilo_id = CAST(:geid AS bigint),
                        tipo_1_id = CAST(:t1id AS bigint),
                        material_id = CAST(:mat AS bigint),
                        color_id = CAST(:col AS bigint)
                    WHERE id = CAST(:rid AS bigint)
                    """
                ),
                {
                    "rid": rid,
                    "mid": int(resolved.iloc[i]["marca_id"]),
                    "gid": int(resolved.iloc[i]["genero_id"]),
                    "geid": int(resolved.iloc[i]["grupo_estilo_id"]),
                    "t1id": int(resolved.iloc[i]["tipo_1_id"]),
                    "mat": int(resolved.iloc[i]["material_id"]),
                    "col": int(resolved.iloc[i]["color_id"]),
                },
            )
    if warns:
        print(f"[RETAIL-STAGING] refresh_batch_fks avisos ({len(warns)}): {warns[:12]}", flush=True)
    return n


def load_batch_df(engine, batch_id: str) -> pd.DataFrame:
    q = text("""
        SELECT
            s.origen_tienda,
            s.tipo_movimiento,
            s.fecha_mov,
            s.linea_code,
            s.referencia_code,
            s.material_id,
            s.color_id,
            s.grada,
            s.cantidad,
            s.precio_unitario,
            s.monto,
            s.sku_key,
            s.marca_id,
            s.genero_id,
            s.grupo_estilo_id,
            s.tipo_1_id,
            COALESCE(
                NULLIF(btrim(mv.descp_marca::text), ''),
                '(sin marca)'
            ) AS marca,
            COALESCE(
                NULLIF(btrim(g.descripcion::text), ''),
                NULLIF(btrim(g.codigo::text), ''),
                '(sin género)'
            ) AS genero,
            COALESCE(
                NULLIF(btrim(ge.descp_grupo_estilo::text), ''),
                '(sin estilo)'
            ) AS estilo,
            COALESCE(
                NULLIF(btrim(t1.descp_tipo_1::text), ''),
                '(sin tipo_1)'
            ) AS tipo_1
        FROM public.retail_multitienda_staging s
        LEFT JOIN public.marca_v2 mv ON mv.id_marca = s.marca_id
        LEFT JOIN public.genero g ON g.id = s.genero_id
        LEFT JOIN public.grupo_estilo_v2 ge ON ge.id_grupo_estilo = s.grupo_estilo_id
        LEFT JOIN public.tipo_1 t1 ON t1.id_tipo_1 = s.tipo_1_id
        WHERE s.batch_id = CAST(:b AS uuid)
    """)
    with engine.connect() as c:
        return pd.read_sql(q, c, params={"b": batch_id})


def _norm_sku_key(v: Any) -> str:
    """Clave estable para cruzar staging, pivot y rankings (evita fallos dict numpy/str)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _image_stem_aliases(raw_stem: str) -> set[str]:
    """
    Variantes de nombre de archivo → misma ruta.

    Formato principal (proveedor): ``linea-referencia-material-color`` con guiones,
    ej. ``1143-309-5881-47164``. También se indexan variantes con ``_``, ``|``, prefijos, etc.
    """
    s0 = raw_stem.strip().lower()
    out: set[str] = set()

    def add(x: str) -> None:
        t = (x or "").strip().lower()
        if t:
            out.add(t)
            out.add(re.sub(r"[\s\-]+", "_", t))

    if not s0:
        return out
    add(s0)
    # Formato proveedor: L-R-m-c (cuatro segmentos separados por guión)
    parts_hyp = [p.strip() for p in s0.split("-") if p.strip()]
    if len(parts_hyp) >= 4:
        L, R, m0, c0 = (
            _canon_codigo_pilar(parts_hyp[0]),
            _canon_codigo_pilar(parts_hyp[1]),
            _canon_codigo_pilar(parts_hyp[2]),
            _canon_codigo_pilar(parts_hyp[3]),
        )
        if L and R and m0 and c0:
            add(f"{L}-{R}-{m0}-{c0}")
    if len(parts_hyp) >= 2:
        L2, R2 = _canon_codigo_pilar(parts_hyp[0]), _canon_codigo_pilar(parts_hyp[1])
        if L2 and R2:
            add(f"{L2}-{R2}")
    for pref in ("img_", "foto_", "photo_", "pic_", "r_", "ref_"):
        if s0.startswith(pref) and len(s0) > len(pref) + 2:
            add(s0[len(pref) :])
    if "|" in s0:
        parts = [p.strip() for p in s0.split("|") if p.strip()]
        if len(parts) >= 2:
            L, R = _canon_codigo_pilar(parts[0]), _canon_codigo_pilar(parts[1])
            if L and R:
                add(f"{L}-{R}")
                add(f"{L}_{R}")
                add(f"{L}|{R}")
            if len(parts) >= 4:
                m, c = _canon_codigo_pilar(parts[2]), _canon_codigo_pilar(parts[3])
                if L and R and m and c:
                    add(f"{L}-{R}-{m}-{c}")
                    add(f"{L}_{R}_{m}_{c}")
                    add(f"{L}|{R}|{m}|{c}")
    mo = re.match(r"^(\d+(?:[.,]\d+)?)\D+(\d+(?:[.,]\d+)?)", re.sub(r"\s+", "", s0))
    if mo:
        L = _canon_codigo_pilar(mo.group(1))
        R = _canon_codigo_pilar(mo.group(2))
        if L and R:
            add(f"{L}-{R}")
            add(f"{L}_{R}")
    return out


def build_image_index(folder: str) -> dict[str, str]:
    """
    Indexa archivos por stem y alias. Formato típico de proveedor:
    ``linea-referencia-material-color.jpg`` (ej. ``1143-309-5881-47164``).
    """
    base = Path(folder)
    if not base.is_dir():
        return {}
    idx: dict[str, str] = {}
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    for p in base.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        resolved = str(p.resolve())
        for alias in _image_stem_aliases(p.stem):
            idx[alias] = resolved
    return idx


def _mat_col_id(v: Any) -> str:
    if pd.isna(v):
        return ""
    try:
        if float(v) == int(float(v)):
            return str(int(float(v)))
    except (ValueError, TypeError):
        pass
    return str(v).strip()


def _resolve_image_lookup_keys(L: str, R: str, m: str, c: str) -> list[str]:
    """
    Orden: más específico primero.
    Prioridad al formato proveedor con guiones: ``linea-referencia-material-color``.
    """
    keys: list[str] = []
    if not L or not R:
        return keys
    if m and c:
        hyphen_full = f"{L}-{R}-{m}-{c}"
        keys.extend(
            [
                hyphen_full,
                f"{L}_{R}_{m}_{c}",
                f"{L}|{R}|{m}|{c}",
                f"{L}{R}{m}{c}",
            ]
        )
    keys.extend(
        [
            f"{L}-{R}",
            f"{L}_{R}",
            f"{L}|{R}",
        ]
    )
    return [k.lower() for k in keys]


def resolve_image(
    idx: dict[str, str],
    linea: str,
    ref: str,
    mat: Any,
    col: Any,
) -> str | None:
    """Resuelve ruta de imagen; formato canónico de archivo: ``linea-referencia-material-color``."""
    if not idx:
        return None
    L, R = _canon_codigo_pilar(linea), _canon_codigo_pilar(ref)
    m, c = _mat_col_id(mat), _mat_col_id(col)
    for key in _resolve_image_lookup_keys(L, R, m, c):
        if key in idx:
            return idx[key]
    return None


def sorted_material_color_options(series: pd.Series) -> list[str]:
    """Lista de ids numéricos únicos ordenados, como strings (para selectbox)."""
    v = pd.to_numeric(series, errors="coerce").dropna()
    if v.empty:
        return []
    ints = sorted({int(float(x)) for x in v.unique()})
    return [str(x) for x in ints]


_FILTER_SENTINEL = frozenset({"(todas)", "(todos)", "", "(ninguna)", "(ninguno)"})


def apply_retail_filters(
    df: pd.DataFrame,
    *,
    linea: str,
    referencia: str,
    material: str,
    color: str,
) -> pd.DataFrame:
    """
    Central de filtrado por pilares (línea, referencia, material, color).
    Ranking y pivotes del reporte deben operar sobre el DataFrame que devuelve esta función.
    """
    out = df.copy()
    s_linea = (linea or "").strip()
    s_ref = (referencia or "").strip()
    s_mat = (material or "").strip()
    s_col = (color or "").strip()
    if s_linea not in _FILTER_SENTINEL:
        out = out[out["linea_code"].astype(str) == s_linea]
    if s_ref not in _FILTER_SENTINEL:
        out = out[out["referencia_code"].astype(str) == s_ref]
    if s_mat not in _FILTER_SENTINEL:
        mv = pd.to_numeric(s_mat, errors="coerce")
        if pd.notna(mv):
            out = out[pd.to_numeric(out["material_id"], errors="coerce") == float(mv)]
    if s_col not in _FILTER_SENTINEL:
        cv = pd.to_numeric(s_col, errors="coerce")
        if pd.notna(cv):
            out = out[pd.to_numeric(out["color_id"], errors="coerce") == float(cv)]
    return out


def aggregate_top_skus(df: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    """Ranking por ventas totales (pares) a nivel sku_key."""
    ventas = df[df["tipo_movimiento"].astype(str).str.strip().str.lower() == "venta"].copy()
    if ventas.empty:
        return pd.DataFrame()
    ventas["sku_key"] = ventas["sku_key"].map(_norm_sku_key)
    ventas = ventas[ventas["sku_key"].ne("")]
    if ventas.empty:
        return pd.DataFrame()
    agg_kw: dict[str, tuple] = {
        "venta_pares": ("cantidad", "sum"),
        "venta_gs": ("monto", "sum"),
        "linea_code": ("linea_code", "first"),
        "referencia_code": ("referencia_code", "first"),
        "material_id": ("material_id", "first"),
        "color_id": ("color_id", "first"),
    }
    for col in ("marca", "genero", "estilo"):
        if col in ventas.columns:
            agg_kw[col] = (col, "first")
    g = (
        ventas.groupby("sku_key", as_index=False)
        .agg(**agg_kw)
        .sort_values("venta_pares", ascending=False)
        .head(top_n)
    )
    return g


def _pivot_col_label(origen: str, suffix: str) -> str:
    """Nombre de columna estable para AgGrid / merge (origen puede traer espacios)."""
    base = str(origen).strip().replace(" ", "_")
    base = re.sub(r"[^\w\d\-]+", "_", base, flags=re.UNICODE).strip("_") or "origen"
    return f"{base}_{suffix}"


def pivot_tiendas_stock_venta(df: pd.DataFrame) -> pd.DataFrame:
    """Resumen por sku_key y origen: suma cantidad venta y último stock por fecha."""
    if df.empty or "sku_key" not in df.columns:
        return pd.DataFrame()
    d = df.copy()
    d["sku_key"] = d["sku_key"].map(_norm_sku_key)
    d = d[d["sku_key"].ne("")]
    if d.empty:
        return pd.DataFrame()
    d["origen_tienda"] = d["origen_tienda"].astype(str).str.strip()
    rows = []
    for sku, sub in d.groupby("sku_key", sort=False):
        piece: dict[str, Any] = {"sku_key": sku}
        for origen in sorted(sub["origen_tienda"].unique()):
            so = sub[sub["origen_tienda"] == origen]
            v = so[so["tipo_movimiento"].astype(str).str.strip().str.lower() == "venta"]
            s = so[so["tipo_movimiento"].astype(str).str.strip().str.lower() == "stock"]
            piece[_pivot_col_label(origen, "venta")] = float(v["cantidad"].sum()) if not v.empty else 0.0
            if not s.empty:
                maxd = s["fecha_mov"].max()
                slast = s[s["fecha_mov"] == maxd]
                piece[_pivot_col_label(origen, "stock")] = float(slast["cantidad"].sum())
            else:
                piece[_pivot_col_label(origen, "stock")] = 0.0
        rows.append(piece)
    return pd.DataFrame(rows)


def slice_movimiento(df: pd.DataFrame, tipo: str) -> pd.DataFrame:
    """Filtra filas por tipo_movimiento (Venta / Stock)."""
    if df.empty:
        return df.copy()
    m = df["tipo_movimiento"].astype(str).str.strip().str.lower() == tipo.strip().lower()
    return df.loc[m].copy()


def resumen_por_tienda(df_mov: pd.DataFrame) -> pd.DataFrame:
    """Pares y monto por origen_tienda."""
    if df_mov.empty:
        return pd.DataFrame(columns=["origen_tienda", "pares", "monto_gs"])
    return (
        df_mov.groupby("origen_tienda", as_index=False)
        .agg(pares=("cantidad", "sum"), monto_gs=("monto", "sum"))
        .sort_values("origen_tienda")
    )


def desglose_dim(df_mov: pd.DataFrame, dim: str, top: int = 35) -> pd.DataFrame | None:
    """Top por una dimensión de texto (etiquetas marca / género / estilo / tipo_1 desde maestros)."""
    if df_mov.empty or dim not in df_mov.columns:
        return None
    s = df_mov[dim].astype(str).str.strip()
    mask = s.ne("") & s.str.lower().ne("nan") & s.str.lower().ne("none")
    if not mask.any():
        return None
    d2 = df_mov.loc[mask].copy()
    return (
        d2.groupby(dim, as_index=False)
        .agg(pares=("cantidad", "sum"), monto_gs=("monto", "sum"))
        .sort_values("pares", ascending=False)
        .head(top)
    )


def desglose_linea_referencia(df_mov: pd.DataFrame, top: int = 45) -> pd.DataFrame:
    """Ranking por línea + referencia; incluye marca / género / estilo si vienen en el DataFrame."""
    if df_mov.empty:
        return pd.DataFrame()
    d = df_mov.copy()
    d["linea_code"] = d["linea_code"].map(_canon_codigo_pilar)
    d["referencia_code"] = d["referencia_code"].map(_canon_codigo_pilar)
    gkeys = ["linea_code", "referencia_code"]
    agg_kw: dict[str, tuple] = {
        "pares": ("cantidad", "sum"),
        "monto_gs": ("monto", "sum"),
    }
    for col in ("marca", "genero", "estilo"):
        if col in d.columns:
            agg_kw[col] = (col, "first")
    out = (
        d.groupby(gkeys, as_index=False)
        .agg(**agg_kw)
        .sort_values("pares", ascending=False)
        .head(top)
    )
    front = ["linea_code", "referencia_code"]
    mids = [c for c in ("marca", "genero", "estilo") if c in out.columns]
    tail = ["pares", "monto_gs"]
    return out[[c for c in front + mids + tail if c in out.columns]]


def representative_row_for_linea_ref(df: pd.DataFrame, linea: str, ref: str) -> pd.Series | None:
    """Una fila representativa (máx. cantidad) para resolver miniatura mat/col."""
    if df.empty:
        return None
    lc, rc = _canon_codigo_pilar(linea), _canon_codigo_pilar(ref)
    lc_s = df["linea_code"].map(_canon_codigo_pilar)
    rc_s = df["referencia_code"].map(_canon_codigo_pilar)
    m = (lc_s == lc) & (rc_s == rc)
    chunk = df.loc[m]
    if chunk.empty:
        return None
    qty = pd.to_numeric(chunk["cantidad"], errors="coerce").fillna(0.0)
    return chunk.loc[qty.idxmax()]


def album_candidates_from_ventas(df: pd.DataFrame, top: int = 30) -> pd.DataFrame:
    """SKU con más venta para galería / reposición."""
    v = slice_movimiento(df, "venta")
    if v.empty:
        return pd.DataFrame()
    v = v.copy()
    v["sku_key"] = v["sku_key"].map(_norm_sku_key)
    v = v[v["sku_key"].ne("")]
    if v.empty:
        return pd.DataFrame()
    agg_kw: dict[str, tuple] = {
        "venta_pares": ("cantidad", "sum"),
        "linea_code": ("linea_code", "first"),
        "referencia_code": ("referencia_code", "first"),
        "material_id": ("material_id", "first"),
        "color_id": ("color_id", "first"),
    }
    for col in ("marca", "genero"):
        if col in v.columns:
            agg_kw[col] = (col, "first")
    out = (
        v.groupby("sku_key", as_index=False)
        .agg(**agg_kw)
        .sort_values("venta_pares", ascending=False)
        .head(top)
    )
    return out


def _grada_sort_key(g: Any) -> tuple:
    """Orden de tallas/gradas: número inicial si existe (p. ej. 34 dentro de 34(1 2…))."""
    s = str(g).strip()
    if not s or s.lower() in ("(sin grada)", "nan", "none", "<na>"):
        return (9999, 9999, s)
    m = re.match(r"^(\d+)", s)
    if m:
        return (0, int(m.group(1)), s)
    return (1, 0, s)


def _album_origen_is_importadora(name: str) -> bool:
    """True si el origen es importadora / depósito central (RIMEC, etc.)."""
    nl = str(name).lower().strip()
    return "import" in nl or "rimec" in nl


def _grada_es_caja_curva_importadora(g: str) -> bool:
    """
    Grada que representa **caja cerrada / curva** de la importadora (p. ej. ``34(1 2 3 3 2 1)39``).
    No debe mostrarse como columna en filas de **tiendas** (allí van tallas simples).
    """
    sraw = str(g).strip()
    sl = sraw.lower()
    if not sraw or "sin grada" in sl:
        return False
    return "(" in sraw and ")" in sraw


def _gradas_visibles_para_origen(origen: str, gradas_orden_global: list[str]) -> list[str]:
    """Filtra columnas de grada según origen: tiendas ≠ importadora."""
    es_imp = _album_origen_is_importadora(origen)
    out: list[str] = []
    for g in gradas_orden_global:
        curva = _grada_es_caja_curva_importadora(g)
        if es_imp:
            if curva:
                out.append(g)
        else:
            if not curva:
                out.append(g)
    return out


def _album_origenes_ordered(origenes: list[Any]) -> list[str]:
    """Tiendas primero (orden natural), importadora / RIMEC al final."""
    names = sorted({str(o).strip() for o in origenes if str(o).strip()})
    if not names:
        return []

    tiendas = [n for n in names if not _album_origen_is_importadora(n)]
    imp = [n for n in names if _album_origen_is_importadora(n)]

    def nat_key(label: str) -> tuple:
        parts = re.split(r"(\d+)", label)
        key: list[Any] = []
        for p in parts:
            if p.isdigit():
                key.append(int(p))
            else:
                key.append(p.lower())
        return tuple(key)

    tiendas.sort(key=nat_key)
    imp.sort(key=nat_key)
    return tiendas + imp


def album_grada_summary_for_sku(df: pd.DataFrame, sku_key: str) -> dict[str, Any] | None:
    """
    Para el álbum: por cada origen, filas **VENTA** y **STOCK** con columnas por **grada**.

    - **Tiendas**: solo tallas / gradas “simples” (sin curva tipo caja cerrada).
    - **Importadora**: solo gradas tipo **caja/curva** (p. ej. ``34(1 2 3 3 2 1)39`` con paréntesis).

    Stock = último ``fecha_mov`` declarado para ese origen + SKU.
    """
    if df.empty or "sku_key" not in df.columns or "grada" not in df.columns:
        return None
    sku = _norm_sku_key(sku_key)
    if not sku:
        return None
    sub = df.loc[df["sku_key"].map(_norm_sku_key) == sku].copy()
    if sub.empty:
        return None
    sub["grada_s"] = sub["grada"].astype(str).str.strip()
    gradas_sorted = sorted({g for g in sub["grada_s"].unique() if g}, key=_grada_sort_key)
    if not gradas_sorted:
        return None

    blocks: list[dict[str, Any]] = []
    for origen in _album_origenes_ordered(sub["origen_tienda"].unique()):
        col_keys = _gradas_visibles_para_origen(origen, gradas_sorted)
        if not col_keys:
            continue
        so = sub[sub["origen_tienda"].astype(str).str.strip() == origen]
        vent = so[so["tipo_movimiento"].astype(str).str.strip().str.lower() == "venta"]
        stk = so[so["tipo_movimiento"].astype(str).str.strip().str.lower() == "stock"]
        if vent.empty and stk.empty:
            continue
        if not vent.empty:
            vq = pd.to_numeric(vent["cantidad"], errors="coerce").fillna(0.0)
            vs = vent.assign(_q=vq).groupby("grada_s")["_q"].sum().reindex(col_keys, fill_value=0)
        else:
            vs = pd.Series(0.0, index=col_keys)
        if not stk.empty:
            maxd = stk["fecha_mov"].max()
            sl = stk[stk["fecha_mov"] == maxd]
            sq = pd.to_numeric(sl["cantidad"], errors="coerce").fillna(0.0)
            ss = sl.assign(_q=sq).groupby("grada_s")["_q"].sum().reindex(col_keys, fill_value=0)
        else:
            ss = pd.Series(0.0, index=col_keys)
        blocks.append(
            {
                "origen": origen,
                "gradas": col_keys,
                "venta": {g: float(vs.loc[g]) for g in col_keys},
                "stock": {g: float(ss.loc[g]) for g in col_keys},
            }
        )
    if not blocks:
        return None
    return {"blocks": blocks}


def pivot_resumen_texto(df: pd.DataFrame, max_skus: int = 15) -> str:
    """Texto plano con stock/venta por SKU y tienda (para herramienta reposición)."""
    piv = pivot_tiendas_stock_venta(df)
    if piv.empty:
        return ""
    lines: list[str] = []
    for _, row in piv.head(max_skus).iterrows():
        sku = row.get("sku_key", "")
        parts = [str(sku)]
        for k, v in row.items():
            if k == "sku_key":
                continue
            if isinstance(v, float):
                parts.append(f"{k}={v:,.0f}".replace(",", "."))
            else:
                parts.append(f"{k}={v}")
        lines.append(" · ".join(parts))
    return "\n".join(lines)


def merge_top_skus_con_pivot(top: pd.DataFrame, pivot: pd.DataFrame) -> pd.DataFrame:
    """
    Cruza ranking de ventas con pivot stock/venta por tienda (misma sku_key normalizada).
    """
    if top.empty:
        return top.copy()
    t = top.copy()
    t["sku_key"] = t["sku_key"].map(_norm_sku_key)
    if pivot.empty or "sku_key" not in pivot.columns:
        return t
    p = pivot.copy()
    p["sku_key"] = p["sku_key"].map(_norm_sku_key)
    merged = t.merge(p, on="sku_key", how="left")
    for c in merged.columns:
        if c == "sku_key":
            continue
        cs = str(c)
        if cs.endswith("_venta") or cs.endswith("_stock"):
            merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0.0)
    return merged


def pick_folder_dialog() -> str | None:
    """Solo escritorio local Windows/macOS."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Carpeta de imágenes (calzados)")
        root.destroy()
        return path or None
    except Exception:
        return None
