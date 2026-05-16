"""
RIMEC ENGINE — logic.py
Motor de cálculo de precios. Lee Excel del proveedor, ejecuta fórmulas,
persiste en Supabase. Sin lógica de UI.
"""

import ast
import math
import zipfile
from io import BytesIO
from datetime import date as date_type

import pandas as pd
from core.database import get_dataframe, commit_query, engine, DBInspector
from sqlalchemy import text


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: INSERT con RETURNING
# ─────────────────────────────────────────────────────────────────────────────

def _insert_returning(query: str, params: dict) -> int | None:
    """Ejecuta un INSERT ... RETURNING id y devuelve el id generado."""
    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), params)
            row = result.fetchone()
            return int(row[0]) if row else None
    except Exception as e:
        DBInspector.log(f"[ENGINE] INSERT RETURNING falló: {e}", "ERROR")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR DE CÁLCULO
# ─────────────────────────────────────────────────────────────────────────────

def redondeo_centena_inferior(x: float) -> int:
    return math.floor(x / 100) * 100


def calcular_fob_ajustado(fob: float, d1, d2, d3, d4) -> float:
    result = fob
    for d in [d1, d2, d3, d4]:
        if d is not None and d > 0:
            result = result * (1 - float(d))
    return result


def calcular_precios_caso(fob: float, caso: dict) -> dict:
    fob_ajustado = calcular_fob_ajustado(
        fob,
        caso.get("descuento_1"),
        caso.get("descuento_2"),
        caso.get("descuento_3"),
        caso.get("descuento_4"),
    )
    indice  = (float(caso["dolar_politica"]) * float(caso["factor_conversion"])) / 100
    lpn_raw = fob_ajustado * indice
    lpn     = redondeo_centena_inferior(lpn_raw)

    lpc03 = redondeo_centena_inferior(lpn * 1.12) if caso.get("genera_lpc03_lpc04") else None
    lpc04 = redondeo_centena_inferior(lpn * 1.20) if caso.get("genera_lpc03_lpc04") else None

    return {
        "fob_ajustado": round(fob_ajustado, 4),
        "lpn":   lpn,
        "lpc03": lpc03,
        "lpc04": lpc04,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LECTURA DEL ARCHIVO EXCEL
# ─────────────────────────────────────────────────────────────────────────────

def leer_excel_proveedor(archivo_bytes, nombre_archivo: str) -> dict:
    """
    Lee el .xls/.xlsx del proveedor. Cada hoja = una marca.
    Retorna: { "marcas": [str], "skus": DataFrame, "error": str|None }
    """
    try:
        engine_xls = "xlrd" if nombre_archivo.lower().endswith(".xls") else "openpyxl"
        xl = pd.ExcelFile(archivo_bytes, engine=engine_xls)
        hojas = xl.sheet_names

        frames = []
        razones = []
        for hoja in hojas:
            df_raw = xl.parse(hoja, header=None)

            # Layout Bacera (prioridad): A=línea B=ref C=mat D=desc E=FOB; F+ ignoradas
            df_clean = _extraer_hoja_layout_bacera(df_raw, hoja)
            if df_clean is not None and not df_clean.empty:
                DBInspector.log(
                    f"[ENGINE] Hoja '{hoja}' leída por posición A–E ({len(df_clean)} SKUs)",
                    "SUCCESS",
                )
                frames.append(df_clean)
                continue

            # Fallback: encabezados por nombre (otros formatos de proveedor)
            df_legacy, razon_legacy = _extraer_hoja_por_nombres(df_raw, hoja)
            if df_legacy is not None and not df_legacy.empty:
                DBInspector.log(f"[ENGINE] Hoja '{hoja}' leída por nombres de columna", "SUCCESS")
                frames.append(df_legacy)
            elif razon_legacy:
                razones.append(razon_legacy)

        if not frames:
            mensaje_error = "No se encontraron hojas con datos válidos.\n\nDetalles:\n" + "\n".join(f"- {r}" for r in razones)
            return {"marcas": [], "skus": pd.DataFrame(), "error": mensaje_error}

        skus = pd.concat(frames, ignore_index=True)
        marcas = skus["marca"].unique().tolist()
        return {"marcas": marcas, "skus": skus, "error": None}

    except Exception as e:
        DBInspector.log(f"[ENGINE] Error leyendo Excel: {e}", "ERROR")
        return {"marcas": [], "skus": pd.DataFrame(), "error": str(e)}


def _parse_fob(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace(",", ".")
    if s in ("", "nan", "None", "-"):
        return None
    try:
        n = float(s)
        return n if n > 0 else None
    except (ValueError, TypeError):
        return None


def _extraer_hoja_layout_bacera(df_raw: pd.DataFrame, marca: str) -> pd.DataFrame | None:
    """
    Formato Bacera / listado proveedor por POSICIÓN (nombres de columna irrelevantes):
      A (0)=línea, B (1)=referencia, C (2)=código material, D (3)=descripción, E (4)=FOB USD.
      Columna F en adelante se ignora.
    """
    if df_raw is None or df_raw.empty or df_raw.shape[1] < 5:
        return None

    sub = df_raw.iloc[:, :5].copy()
    sub.columns = ["linea", "referencia", "material", "descripcion", "fob_fabrica"]

    _skip_hdr = {
        "STYLE", "REF", "REFERENCIA", "MATERIAL", "MATERIAL CODE", "MAT",
        "UNIT", "USD", "FOB", "PRECIO", "LINEA", "LÍNEA", "DESCRIPCION", "DESCRIPCIÓN",
    }
    filas: list[dict] = []
    for _, row in sub.iterrows():
        fob = _parse_fob(row["fob_fabrica"])
        if fob is None:
            continue
        ref = str(row["referencia"]).strip()
        if not ref or ref.lower() in ("nan", "none", "—", "-"):
            continue
        if ref.upper() in _skip_hdr:
            continue
        lin = str(row["linea"]).strip()
        if not lin or lin.lower() in ("nan", "none", "—", "-"):
            continue
        if lin.upper() in _skip_hdr:
            continue
        mat = str(row["material"]).strip()
        if mat.lower() in ("nan", "none"):
            mat = "—"
        desc = str(row["descripcion"]).strip()
        if desc.lower() in ("nan", "none"):
            desc = ""
        filas.append({
            "marca":       marca,
            "linea":       lin,
            "referencia":  ref,
            "material":    mat,
            "descripcion": desc,
            "fob_fabrica": fob,
        })

    if not filas:
        return None
    return pd.DataFrame(filas)


def _extraer_hoja_por_nombres(df_raw: pd.DataFrame, hoja: str) -> tuple[pd.DataFrame | None, str | None]:
    """Lectura legacy por fila de encabezados y nombres de columna."""
    header_row = None
    for i, row in df_raw.iterrows():
        row_str = " ".join(str(v).upper() for v in row if pd.notna(v))
        if any(k in row_str for k in ["FOB", "PRECIO", "COSTO", "REFERENCIA", "REF", "UNIT", "USD"]):
            header_row = i
            break

    if header_row is None:
        return None, f"Hoja '{hoja}': sin encabezados reconocibles ni datos en columnas A–E."

    df = df_raw.iloc[header_row + 1:].copy()
    df.columns = [str(c).strip().upper() for c in df_raw.iloc[header_row]]
    df = df.reset_index(drop=True)

    col_map = _mapear_columnas(df.columns.tolist())
    if not col_map:
        return None, (
            f"Hoja '{hoja}': no se mapearon columnas por nombre. "
            f"Detectadas: {df.columns.tolist()}. Se espera layout A–E."
        )

    df_clean = pd.DataFrame({
        "marca":        hoja,
        "linea":        df[col_map["linea"]].astype(str).str.strip() if col_map.get("linea") else "—",
        "referencia":   df[col_map["referencia"]].astype(str).str.strip(),
        "material":     df[col_map["material"]].astype(str).str.strip() if col_map.get("material") else "—",
        "descripcion":  df[col_map["descripcion"]].astype(str).str.strip() if col_map.get("descripcion") else "",
        "fob_fabrica":  pd.to_numeric(df[col_map["fob"]], errors="coerce"),
    })
    total_antes = len(df_clean)
    df_clean = df_clean.dropna(subset=["fob_fabrica", "referencia"])
    df_clean = df_clean[df_clean["fob_fabrica"] > 0]
    df_clean = df_clean[df_clean["referencia"].str.len() > 0]

    if df_clean.empty:
        return None, f"Hoja '{hoja}': sin datos tras limpiar (de {total_antes} filas)."
    return df_clean, None


def _mapear_columnas(cols: list) -> dict:
    mapping = {}
    for c in cols:
        cu = c.upper().strip()
        if any(k in cu for k in ["FOB", "PRECIO", "COSTO", "PRICE", "UNIT", "USD"]) and "fob" not in mapping:
            mapping["fob"] = c
        if any(k in cu for k in ["REF", "MODELO", "ARTICULO", "ARTÍCULO", "SKU"]) and "referencia" not in mapping:
            mapping["referencia"] = c
        if any(k in cu for k in ["STYLE", "LINEA", "LÍNEA", "LINHA", "LINE", "LIN.", "GRUPO", "GRP"]) and "linea" not in mapping:
            mapping["linea"] = c
        if any(k in cu for k in ["DESC"]) and "descripcion" not in mapping:
            mapping["descripcion"] = c
        if any(k in cu for k in ["MATERIAL", "MATER", "MAT", "ACAB", "CABEDAL", "CAB.", "UPPER", "CODE"]) and "material" not in mapping:
            if "CODE" in cu and "MATERIAL" not in cu and "material" in mapping:
                continue
            if "material" not in mapping:
                mapping["material"] = c
    if "fob" not in mapping or "referencia" not in mapping:
        return {}
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# OPERACIONES EN precio_evento
# ─────────────────────────────────────────────────────────────────────────────

def get_proveedores() -> pd.DataFrame:
    df = get_dataframe("SELECT id, codigo, nombre FROM proveedor_importacion ORDER BY nombre")
    return df if df is not None else pd.DataFrame()


def build_pillar_cache(proveedor_id: int) -> dict:
    """
    Carga linea, referencia y material en memoria con 3 queries.
    Elimina los N×3 round-trips por SKU — usar una vez antes del loop.
    Returns: {"linea": {cod: id}, "referencia": {(linea_id, cod): id}, "material": {cod: id}}
    """
    try:
        with engine.connect() as conn:
            lineas = conn.execute(
                text("SELECT codigo_proveedor, id FROM linea WHERE proveedor_id = :pid"),
                {"pid": proveedor_id}
            ).fetchall()
            refs = conn.execute(
                text("SELECT linea_id, codigo_proveedor, id FROM referencia WHERE proveedor_id = :pid"),
                {"pid": proveedor_id}
            ).fetchall()
            mats = conn.execute(
                text("SELECT codigo_proveedor, id FROM material WHERE proveedor_id = :pid"),
                {"pid": proveedor_id}
            ).fetchall()
        cache = {
            "linea":      {int(r[0]): int(r[1]) for r in lineas},
            "referencia": {(int(r[0]), int(r[1])): int(r[2]) for r in refs},
            "material":   {int(r[0]): int(r[1]) for r in mats},
        }
        DBInspector.log(
            f"[ENGINE] Cache pilares: {len(cache['linea'])} lineas, "
            f"{len(cache['referencia'])} refs, {len(cache['material'])} materiales",
            "SUCCESS"
        )
        return cache
    except Exception as e:
        DBInspector.log(f"[ENGINE] build_pillar_cache falló: {e}", "ERROR")
        return {"linea": {}, "referencia": {}, "material": {}}


def get_or_create_linea_cached(cache: dict, proveedor_id: int, codigo_proveedor: int) -> int | None:
    """Resuelve desde caché; va a BD solo si el código es nuevo."""
    if codigo_proveedor in cache["linea"]:
        return cache["linea"][codigo_proveedor]
    new_id = get_or_create_linea(proveedor_id, codigo_proveedor)
    if new_id:
        cache["linea"][codigo_proveedor] = new_id
    return new_id


def get_or_create_referencia_cached(cache: dict, proveedor_id: int, linea_id: int, codigo_proveedor: int) -> int | None:
    key = (linea_id, codigo_proveedor)
    if key in cache["referencia"]:
        return cache["referencia"][key]
    new_id = get_or_create_referencia(proveedor_id, linea_id, codigo_proveedor)
    if new_id:
        cache["referencia"][key] = new_id
    return new_id


def get_or_create_material_cached(cache: dict, proveedor_id: int, codigo_proveedor: int, descripcion: str = "") -> int | None:
    if codigo_proveedor in cache["material"]:
        return cache["material"][codigo_proveedor]
    new_id = get_or_create_material(proveedor_id, codigo_proveedor, descripcion)
    if new_id:
        cache["material"][codigo_proveedor] = new_id
    return new_id


def get_or_create_linea(proveedor_id: int, codigo_proveedor: int) -> int | None:
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT id FROM linea WHERE proveedor_id = :pid AND codigo_proveedor = :cod LIMIT 1"),
                {"pid": proveedor_id, "cod": codigo_proveedor}
            ).fetchone()
            if row:
                return int(row[0])
            row = conn.execute(
                text("INSERT INTO linea (proveedor_id, codigo_proveedor) VALUES (:pid, :cod) RETURNING id"),
                {"pid": proveedor_id, "cod": codigo_proveedor}
            ).fetchone()
            return int(row[0]) if row else None
    except Exception as e:
        DBInspector.log(f"[ENGINE] get_or_create_linea({codigo_proveedor}): {e}", "ERROR")
        return None


def get_or_create_referencia(proveedor_id: int, linea_id: int, codigo_proveedor: int) -> int | None:
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""SELECT id FROM referencia
                        WHERE proveedor_id = :pid AND linea_id = :lid AND codigo_proveedor = :cod LIMIT 1"""),
                {"pid": proveedor_id, "lid": linea_id, "cod": codigo_proveedor}
            ).fetchone()
            if row:
                return int(row[0])
            row = conn.execute(
                text("""INSERT INTO referencia (proveedor_id, linea_id, codigo_proveedor)
                        VALUES (:pid, :lid, :cod) RETURNING id"""),
                {"pid": proveedor_id, "lid": linea_id, "cod": codigo_proveedor}
            ).fetchone()
            return int(row[0]) if row else None
    except Exception as e:
        DBInspector.log(f"[ENGINE] get_or_create_referencia({codigo_proveedor}): {e}", "ERROR")
        return None


def get_or_create_material(proveedor_id: int, codigo_proveedor: int, descripcion: str = "") -> int | None:
    """
    Busca material por proveedor+codigo. Si no existe, lo crea con su descripción.
    Si ya existe y no tiene descripción, la actualiza. descripcion es fundamental.
    """
    desc_clean = descripcion.strip() if descripcion else ""
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT id, descripcion FROM material WHERE proveedor_id = :pid AND codigo_proveedor = :cod LIMIT 1"),
                {"pid": proveedor_id, "cod": codigo_proveedor}
            ).fetchone()
            if row:
                mat_id = int(row[0])
                # Actualizar descripcion si el registro no la tiene y ahora tenemos una
                if desc_clean and (row[1] is None or str(row[1]).strip() == ""):
                    conn.execute(
                        text("UPDATE material SET descripcion = :desc WHERE id = :mid"),
                        {"desc": desc_clean, "mid": mat_id}
                    )
                return mat_id
            row = conn.execute(
                text("""INSERT INTO material (proveedor_id, codigo_proveedor, descripcion)
                        VALUES (:pid, :cod, :desc) RETURNING id"""),
                {"pid": proveedor_id, "cod": codigo_proveedor, "desc": desc_clean or None}
            ).fetchone()
            return int(row[0]) if row else None
    except Exception as e:
        DBInspector.log(f"[ENGINE] get_or_create_material({codigo_proveedor}): {e}", "ERROR")
        return None


def crear_evento(nombre_evento: str, nombre_archivo: str,
                 fecha_desde: str, proveedor_id: int, usuario_id=None) -> int | None:
    return _insert_returning(
        """INSERT INTO precio_evento
           (nombre_evento, nombre_archivo, fecha_vigencia_desde, proveedor_id, usuario_id)
           VALUES (:ne, :nf, :fd, :pid, :uid)
           RETURNING id""",
        {"ne": nombre_evento, "nf": nombre_archivo,
         "fd": fecha_desde, "pid": proveedor_id, "uid": usuario_id}
    )


def crear_caso(evento_id: int, caso: dict) -> int | None:
    return _insert_returning(
        """INSERT INTO precio_evento_caso
           (evento_id, nombre_caso, dolar_politica, factor_conversion,
            descuento_1, descuento_2, descuento_3, descuento_4,
            genera_lpc03_lpc04, regla_redondeo, marcas)
           VALUES (:eid, :nc, :dp, :fc, :d1, :d2, :d3, :d4, :glpc, :rr, :marcas)
           RETURNING id""",
        {
            "eid":    evento_id,
            "nc":     caso["nombre_caso"],
            "dp":     caso["dolar_politica"],
            "fc":     caso["factor_conversion"],
            "d1":     caso.get("descuento_1"),
            "d2":     caso.get("descuento_2"),
            "d3":     caso.get("descuento_3"),
            "d4":     caso.get("descuento_4"),
            "glpc":   caso.get("genera_lpc03_lpc04", False),
            "rr":     caso.get("regla_redondeo", "centena"),
            "marcas": caso.get("marcas"),
        }
    )


def get_lineas_por_evento(evento_id: int) -> dict:
    """
    Retorna {caso_id: [cod_proveedor_str, ...]} para casos sin marcas.
    Fuente 1: precio_evento_linea_excepcion (eventos registrados correctamente).
    Fuente 2: precio_lista → linea (fallback para eventos históricos sin registro).
    """
    result: dict = {}

    # Fuente 1: tabla de excepciones
    df1 = get_dataframe(
        """SELECT pele.caso_id, l.codigo_proveedor
           FROM precio_evento_linea_excepcion pele
           JOIN linea l ON l.id = pele.linea_id
           JOIN precio_evento_caso pec ON pec.id = pele.caso_id
           WHERE pec.evento_id = :eid
           ORDER BY pele.caso_id, l.codigo_proveedor""",
        {"eid": evento_id}
    )
    if df1 is not None and not df1.empty:
        for _, row in df1.iterrows():
            result.setdefault(int(row["caso_id"]), []).append(str(int(row["codigo_proveedor"])))

    # Fuente 2: reconstruir desde precio_lista para casos sin marcas no cubiertos por Fuente 1
    df_casos = get_dataframe(
        "SELECT id FROM precio_evento_caso WHERE evento_id = :eid AND marcas IS NULL",
        {"eid": evento_id}
    )
    if df_casos is not None and not df_casos.empty:
        for _, cr in df_casos.iterrows():
            cid = int(cr["id"])
            if cid in result:
                continue
            df2 = get_dataframe(
                """SELECT DISTINCT l.codigo_proveedor
                   FROM precio_lista pl
                   JOIN linea l ON l.id = pl.linea_id
                   WHERE pl.caso_id = :cid
                     AND pl.linea_id IS NOT NULL
                   ORDER BY l.codigo_proveedor""",
                {"cid": cid}
            )
            if df2 is not None and not df2.empty:
                result[cid] = [str(int(r["codigo_proveedor"])) for _, r in df2.iterrows()]

    return result


def parse_marcas_array(marcas_raw) -> list[str]:
    """Convierte marcas PostgreSQL / Python a lista limpia."""
    if marcas_raw is None or (isinstance(marcas_raw, float) and pd.isna(marcas_raw)):
        return []
    if isinstance(marcas_raw, (list, tuple)):
        return [str(m).strip() for m in marcas_raw if m]
    if isinstance(marcas_raw, str):
        s = marcas_raw.strip()
        if s in ("", "None", "nan"):
            return []
        if s.startswith("["):
            try:
                parsed = ast.literal_eval(s)
                return [str(m).strip() for m in parsed if m]
            except Exception:
                pass
        return [m.strip().strip("'\"") for m in s.strip("{}").split(",") if m.strip()]
    return []


def parse_lineas_array(lineas_raw) -> list[str]:
    """Convierte columna lineas de biblioteca a códigos proveedor (str enteros)."""
    if lineas_raw is None or (isinstance(lineas_raw, float) and pd.isna(lineas_raw)):
        return []
    if isinstance(lineas_raw, (list, tuple)):
        raw = lineas_raw
    elif isinstance(lineas_raw, str):
        s = lineas_raw.strip()
        if s in ("", "None", "nan", "[]"):
            return []
        if s.startswith("["):
            try:
                raw = ast.literal_eval(s)
            except Exception:
                raw = [p.strip() for p in s.strip("{}").split(",") if p.strip()]
        else:
            raw = [p.strip() for p in s.split(",") if p.strip()]
    else:
        return []
    out: list[str] = []
    for c in raw:
        try:
            out.append(str(int(float(str(c).strip()))))
        except (ValueError, TypeError):
            continue
    return out


def normalizar_caso_evento(rec: dict) -> dict:
    """Normaliza un caso de la matriz del listado (session / plantilla de evento)."""
    lineas = parse_lineas_array(rec.get("lineas"))
    marcas = parse_marcas_array(rec.get("marcas"))
    if lineas:
        alcance = "lineas"
    elif marcas:
        alcance = "marcas"
    else:
        at = str(rec.get("alcance_tipo") or "marcas").strip().lower()
        alcance = "lineas" if at.startswith("line") else "marcas"

    def _f(key: str, default: float | None = None):
        v = rec.get(key)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    return {
        "nombre_caso":        str(rec.get("nombre_caso", "")).replace("*", "").strip(),
        "dolar_politica":     _f("dolar_politica", 8000.0),
        "factor_conversion":  _f("factor_conversion", 180.0),
        "descuento_1":        _f("descuento_1"),
        "descuento_2":        _f("descuento_2"),
        "descuento_3":        _f("descuento_3"),
        "descuento_4":        _f("descuento_4"),
        "genera_lpc03_lpc04": bool(rec.get("genera_lpc03_lpc04", True)),
        "regla_redondeo":     str(rec.get("regla_redondeo") or "centena"),
        "marcas":             marcas if marcas else None,
        "lineas":             lineas,
        "referencias":        [],
        "alcance_tipo":       alcance,
    }


def casos_evento_to_dataframe(casos: list[dict]) -> pd.DataFrame:
    """DataFrame de casos del listado actual (misma forma que biblioteca para resolver)."""
    if not casos:
        return pd.DataFrame()
    return pd.DataFrame([normalizar_caso_evento(c) for c in casos])


def build_mapa_caso_desde_biblioteca(
    df_bib: pd.DataFrame,
) -> tuple[dict[str, str], dict[str, str], list[dict]]:
    """
    Mapas de alcance comercial desde plantillas de biblioteca (sin leer linea.caso_id).
    Retorna (linea_codigo -> nombre_caso, MARCA_UPPER -> nombre_caso, conflictos_detalle).

    Cada conflicto: {tipo, codigo, caso_a, caso_b, mensaje}.
    """
    linea_map: dict[str, str] = {}
    marca_map: dict[str, str] = {}
    conflictos: list[dict] = []
    if df_bib is None or df_bib.empty:
        return linea_map, marca_map, conflictos

    def _add_conf(tipo: str, codigo: str, caso_a: str, caso_b: str) -> None:
        conflictos.append({
            "tipo":    tipo,
            "codigo":  codigo,
            "caso_a":  caso_a,
            "caso_b":  caso_b,
            "mensaje": f"{tipo} {codigo}: asignada a «{caso_a}» y «{caso_b}»",
        })

    for _, row in df_bib.iterrows():
        nombre = str(row.get("nombre_caso", "")).replace("*", "").strip()
        if not nombre:
            continue
        for cod in parse_lineas_array(row.get("lineas")):
            prev = linea_map.get(cod)
            if prev and prev != nombre:
                _add_conf("Línea", cod, prev, nombre)
            linea_map[cod] = nombre
        for m in parse_marcas_array(row.get("marcas")):
            key = m.strip().upper()
            if not key:
                continue
            prev = marca_map.get(key)
            if prev and prev != nombre:
                _add_conf("Marca", m, prev, nombre)
            marca_map[key] = nombre
    return linea_map, marca_map, conflictos


def _mapa_excepciones_evento(evento_id: int) -> dict[str, str]:
    """linea_codigo -> nombre_caso desde precio_evento_linea_excepcion del evento."""
    df = get_dataframe(
        """SELECT l.codigo_proveedor::text AS linea, pec.nombre_caso
           FROM precio_evento_linea_excepcion pele
           JOIN linea l ON l.id = pele.linea_id
           JOIN precio_evento_caso pec ON pec.id = pele.caso_id
           WHERE pec.evento_id = :eid""",
        {"eid": evento_id},
    )
    out: dict[str, str] = {}
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        try:
            cod = str(int(float(str(row["linea"]).strip())))
        except (ValueError, TypeError):
            continue
        out[cod] = str(row["nombre_caso"]).replace("*", "").strip()
    return out


def guardar_lineas_excepcion(caso_id: int, linea_codigos: list, proveedor_id: int) -> int:
    """Inserta excepciones línea→caso del evento (sin duplicar filas existentes)."""
    n = 0
    for cod in linea_codigos:
        try:
            cod_int = int(cod)
        except (ValueError, TypeError):
            continue
        ok = commit_query(
            """INSERT INTO precio_evento_linea_excepcion (caso_id, linea_id)
               SELECT :cid, id FROM linea
               WHERE proveedor_id = :pid AND codigo_proveedor = :cod
                 AND NOT EXISTS (
                     SELECT 1 FROM precio_evento_linea_excepcion x
                     WHERE x.caso_id = :cid AND x.linea_id = linea.id
                 )
               LIMIT 1""",
            {"cid": caso_id, "pid": proveedor_id, "cod": cod_int},
            show_error=False,
        )
        if ok:
            n += 1
    return n


def reemplazar_lineas_excepcion(
    caso_id: int, linea_codigos: list, proveedor_id: int
) -> int:
    """Reemplaza el alcance por líneas de un caso dentro del evento."""
    commit_query(
        "DELETE FROM precio_evento_linea_excepcion WHERE caso_id = :cid",
        {"cid": caso_id},
        show_error=False,
    )
    return guardar_lineas_excepcion(caso_id, linea_codigos, proveedor_id)


def _cargar_lookups_maestros(proveedor_id: int, conn) -> tuple[dict, dict, dict]:
    """
    Carga los 3 lookups de pilares desde BD para resolver FKs en precio_lista.
    Retorna: (linea_map, ref_map, mat_map)
      linea_map : {codigo_proveedor_str: linea_id}
      ref_map   : {(linea_id_str, ref_codigo_str): referencia_id}
      mat_map   : {descripcion_upper: material_id}
    """
    lineas = conn.execute(text(
        "SELECT id, codigo_proveedor::text FROM linea WHERE proveedor_id=:p"
    ), {"p": proveedor_id}).fetchall()
    linea_map = {r[1]: r[0] for r in lineas}

    refs = conn.execute(text(
        "SELECT id, linea_id::text, codigo_proveedor::text FROM referencia"
    )).fetchall()
    ref_map = {(r[1], r[2]): r[0] for r in refs}

    mats = conn.execute(text(
        "SELECT id, UPPER(descripcion) FROM material WHERE proveedor_id=:p"
    ), {"p": proveedor_id}).fetchall()
    mat_map = {r[1]: r[0] for r in mats if r[1]}

    return linea_map, ref_map, mat_map


def _evento_esta_cerrado(evento_id: int) -> bool:
    """Retorna True si el evento está CERRADO — bloquea escrituras de precio."""
    if not evento_id:
        return False
    df = get_dataframe(
        "SELECT estado FROM precio_evento WHERE id = :eid",
        {"eid": evento_id},
    )
    if df is None or df.empty:
        return False
    return str(df.iloc[0]["estado"]).lower() == "cerrado"


def guardar_precio_lista(filas: list[dict]):
    """
    Inserta todas las filas en precio_lista en UNA sola transacción (bulk).
    Usa linea_id_fk / ref_id_fk / mat_id_fk pre-resueltos por la UI.
    """
    if not filas:
        return
    evento_id = filas[0].get("evento_id")
    if _evento_esta_cerrado(evento_id):
        DBInspector.log(
            f"[ENGINE] Escritura bloqueada — evento {evento_id} en estado CERRADO",
            "WARNING",
        )
        return
    try:
        with engine.begin() as conn:
            filas_enriquecidas = []
            for f in filas:
                filas_enriquecidas.append({
                    **f,
                    "linea_id": f.get("linea_id_fk"),
                    "ref_id":   f.get("ref_id_fk"),
                    "mat_id":   f.get("mat_id_fk"),
                })

            sin_linea = sum(1 for f in filas_enriquecidas if not f["linea_id"])
            sin_mat   = sum(1 for f in filas_enriquecidas if not f["mat_id"])
            DBInspector.log(
                f"[ENGINE] Bulk {len(filas_enriquecidas)} filas — sin linea_id: {sin_linea}, sin mat_id: {sin_mat}",
                "WARNING" if sin_linea or sin_mat else "SUCCESS"
            )

            conn.execute(
                text("""INSERT INTO precio_lista
                        (evento_id, caso_id, marca,
                         linea_id, referencia_id, material_id,
                         linea_codigo, referencia_codigo, material_descripcion,
                         fob_fabrica, fob_ajustado, lpn, lpc03, lpc04, vigente,
                         dolar_aplicado, factor_aplicado, indice_aplicado,
                         descuento_1_aplicado, descuento_2_aplicado,
                         descuento_3_aplicado, descuento_4_aplicado,
                         nombre_caso_aplicado)
                        VALUES (:eid, :cid, :marca,
                                :linea_id, :ref_id, :mat_id,
                                :lc, :rc, :md,
                                :fob, :foba, :lpn, :lpc03, :lpc04, false,
                                :dolar_ap, :factor_ap, :indice_ap,
                                :d1_ap, :d2_ap, :d3_ap, :d4_ap,
                                :nombre_caso_ap)"""),
                filas_enriquecidas,
            )
            DBInspector.log(f"[ENGINE] Bulk INSERT: {len(filas)} filas con 3 pilares FK", "SUCCESS")
    except Exception as e:
        DBInspector.log(f"[ENGINE] Bulk INSERT falló: {e}", "ERROR")


def avanzar_estado_evento(evento_id: int, estado: str):
    commit_query(
        "UPDATE precio_evento SET estado = :e WHERE id = :id",
        {"e": estado, "id": evento_id}
    )


def generar_maestro_lineas_desde_evento(evento_id: int):
    """
    DEPRECATED (arquitectura 2026-05): el caso comercial no se escribe en linea.caso_id.
    La trazabilidad vive en precio_evento + precio_evento_linea_excepcion + precio_lista.
    """
    DBInspector.log(
        f"[ENGINE] generar_maestro_lineas omitido (caso desacoplado del pilar) "
        f"evento={evento_id}",
        "INFO",
    )


def cerrar_evento_y_activar(evento_id: int, fecha_hasta: str):
    commit_query(
        """UPDATE precio_lista SET vigente = false
           WHERE evento_id IN (
               SELECT id FROM precio_evento
               WHERE estado = 'cerrado' AND id <> :eid
           )""",
        {"eid": evento_id}
    )
    commit_query(
        """UPDATE precio_evento
           SET fecha_vigencia_hasta = :fh
           WHERE estado = 'cerrado' AND id <> :eid""",
        {"fh": fecha_hasta, "eid": evento_id}
    )
    commit_query(
        "UPDATE precio_lista SET vigente = true WHERE evento_id = :eid",
        {"eid": evento_id}
    )
    commit_query(
        "UPDATE precio_evento SET estado = 'cerrado' WHERE id = :eid",
        {"eid": evento_id}
    )


def registrar_auditoria(evento_id: int, tabla: str, campo: str,
                         valor_ant, valor_nvo, justificacion: str, usuario_id=None):
    commit_query(
        """INSERT INTO precio_auditoria
           (evento_id, tabla_afectada, campo_modificado,
            valor_anterior, valor_nuevo, justificacion, usuario_id)
           VALUES (:eid, :ta, :cm, :va, :vn, :j, :uid)""",
        {"eid": evento_id, "ta": tabla, "cm": campo,
         "va": str(valor_ant) if valor_ant is not None else None,
         "vn": str(valor_nvo) if valor_nvo is not None else None,
         "j": justificacion, "uid": usuario_id}
    )


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTAS DE LECTURA
# ─────────────────────────────────────────────────────────────────────────────

def get_ultimo_evento_cerrado():
    df = get_dataframe(
        """SELECT pe.*,
           (SELECT COUNT(*) FROM precio_lista pl WHERE pl.evento_id = pe.id) as total_skus
           FROM precio_evento pe
           WHERE pe.estado = 'cerrado'
           ORDER BY pe.created_at DESC LIMIT 1"""
    )
    if df is None or df.empty:
        return None
    return df.iloc[0].to_dict()


def get_casos_evento(evento_id: int) -> pd.DataFrame:
    df = get_dataframe(
        "SELECT * FROM precio_evento_caso WHERE evento_id = :eid ORDER BY id",
        {"eid": evento_id}
    )
    return df if df is not None else pd.DataFrame()


def get_todos_eventos() -> pd.DataFrame:
    df = get_dataframe(
        """SELECT pe.id, pe.nombre_evento, pe.nombre_archivo, pe.estado,
                  pe.fecha_vigencia_desde, pe.fecha_vigencia_hasta, pe.created_at,
                  COUNT(pl.id) as total_skus
           FROM precio_evento pe
           LEFT JOIN precio_lista pl ON pl.evento_id = pe.id
           GROUP BY pe.id
           ORDER BY pe.created_at DESC"""
    )
    return df if df is not None else pd.DataFrame()


def get_preview_skus(skus_caso: pd.DataFrame, caso: dict, n: int = 5) -> pd.DataFrame:
    muestra = skus_caso.head(n).copy()
    resultados = []
    for _, row in muestra.iterrows():
        calc = calcular_precios_caso(float(row["fob_fabrica"]), caso)
        resultados.append({
            "Marca":        row["marca"],
            "Línea":        row.get("linea", "—"),
            "Referencia":   row["referencia"],
            "Material":     row.get("material", "—"),
            "FOB":          row["fob_fabrica"],
            "FOB Ajustado": calc["fob_ajustado"],
            "LPN":          calc["lpn"],
            "LPC03":        calc["lpc03"] if calc["lpc03"] else "—",
            "LPC04":        calc["lpc04"] if calc["lpc04"] else "—",
        })
    return pd.DataFrame(resultados)


def resolver_casos_skus(
    skus_df: pd.DataFrame,
    proveedor_id: int,
    df_bib: pd.DataFrame,
    evento_id: int | None = None,
) -> tuple[pd.DataFrame, bool, list[dict]]:
    """
    Asigna caso por SKU usando alcance de biblioteca (líneas / marcas) y, si existe,
    excepciones del evento (precio_evento_linea_excepcion). No lee linea.caso_id.

    Retorna (df enriquecido, listo_para_calcular, conflictos_detalle).
    """
    _ = proveedor_id  # reservado para validaciones futuras por proveedor
    nombres_bib = {
        str(n).replace("*", "").strip()
        for n in df_bib["nombre_caso"].tolist()
    } if not df_bib.empty else set()

    linea_map, marca_map, conflictos = build_mapa_caso_desde_biblioteca(df_bib)
    if evento_id:
        linea_map.update(_mapa_excepciones_evento(evento_id))

    casos_asignados: list[str] = []
    estados: list[str] = []
    hay_error = bool(conflictos)

    for _, row in skus_df.iterrows():
        try:
            linea_val = str(int(float(str(row.get("linea", 0)).strip() or 0)))
        except (ValueError, TypeError):
            linea_val = ""

        marca = str(row.get("marca", "")).strip().upper()

        if not linea_val or linea_val == "0":
            casos_asignados.append("—")
            estados.append("❌ ERROR (Sin Línea)")
            hay_error = True
            continue

        caso = linea_map.get(linea_val) or marca_map.get(marca)

        if caso:
            if caso in nombres_bib:
                origen = "línea" if linea_val in linea_map else "marca"
                casos_asignados.append(caso)
                estados.append(f"✅ OK ({origen})")
            else:
                casos_asignados.append(caso)
                estados.append(f"❌ ERROR (Falta '{caso}' en matriz del listado)")
                hay_error = True
            continue

        if marca in ["BR SPORT", "ACTVITTA"]:
            fallback = "NORMAL BR-S ACT"
        else:
            fallback = "NORMAL BR-VZ-ML-MD-MKA/O"

        if fallback in nombres_bib:
            casos_asignados.append(fallback)
            estados.append("⚠️ DEFAULT (sin alcance en biblioteca)")
        else:
            casos_asignados.append(fallback)
            estados.append(f"❌ ERROR (Falta fallback '{fallback}' en matriz)")
            hay_error = True

    skus_df = skus_df.copy()
    skus_df["caso_asignado"] = casos_asignados
    skus_df["estado_validacion"] = estados
    return skus_df, not hay_error, conflictos


def contar_skus_procesados(evento_id: int) -> int:
    df = get_dataframe(
        "SELECT COUNT(*) as n FROM precio_lista WHERE evento_id = :eid",
        {"eid": evento_id}
    )
    return int(df.iloc[0]["n"]) if df is not None and not df.empty else 0


# ─────────────────────────────────────────────────────────────────────────────
# CANDADO DINÁMICO — ¿Está el evento siendo usado por algún módulo?
# ─────────────────────────────────────────────────────────────────────────────

def evento_esta_en_uso(evento_id: int) -> dict:
    """
    Consulta si el evento de precio está referenciado por algún módulo interno.
    El estado 'en_uso' es dinámico — no se almacena en BD.

    Retorna:
        { 'en_uso': bool, 'modulos': [str], 'detalle': str }
    """
    modulos_en_uso = []

    df_ic = get_dataframe(
        "SELECT numero_registro FROM intencion_compra WHERE precio_evento_id = :eid",
        {"eid": evento_id}
    )
    if df_ic is not None and not df_ic.empty:
        nros = ", ".join(df_ic["numero_registro"].tolist())
        modulos_en_uso.append(f"Intención de Compra: {nros}")

    df_icp = get_dataframe(
        "SELECT COUNT(*) AS n FROM intencion_compra_pedido WHERE precio_evento_id = :eid",
        {"eid": evento_id}
    )
    if df_icp is not None and not df_icp.empty:
        n = int(df_icp["n"].iloc[0])
        if n > 0:
            modulos_en_uso.append(f"Digitación: {n} asignación(es) en tabla puente")

    en_uso = len(modulos_en_uso) > 0
    return {
        "en_uso":   en_uso,
        "modulos":  modulos_en_uso,
        "detalle":  " | ".join(modulos_en_uso) if en_uso else "Libre para edición",
    }


def get_estado_real_evento(evento_id: int, estado_db: str) -> str:
    """
    Calcula el estado real de un evento. No se almacena — se calcula en tiempo real.
    Estados posibles: borrador | validado | en_uso | cerrado
    """
    if estado_db == "cerrado":
        return "cerrado"
    uso = evento_esta_en_uso(evento_id)
    return "en_uso" if uso["en_uso"] else estado_db


# ─────────────────────────────────────────────────────────────────────────────
# BIBLIOTECA DE CASOS — configuración permanente por proveedor
# ─────────────────────────────────────────────────────────────────────────────

def get_generos() -> list[str]:
    """Retorna los códigos de género activos desde la tabla maestra."""
    df = get_dataframe(
        "SELECT codigo FROM genero WHERE activo = true ORDER BY id"
    )
    return df["codigo"].tolist() if df is not None and not df.empty else [
        "DAMA", "CABALLERO", "NINO", "NINA", "UNISEX"
    ]


def get_biblioteca_casos(proveedor_id: int) -> pd.DataFrame:
    """Retorna los casos activos de la biblioteca para el proveedor."""
    df = get_dataframe(
        """SELECT id, nombre_caso, dolar_politica, factor_conversion,
                  indice_calculado, descuento_1, descuento_2, descuento_3, descuento_4,
                  genera_lpc03_lpc04, alcance_tipo, marcas, lineas
           FROM caso_precio_biblioteca
           WHERE proveedor_id = :pid AND activo = true
           ORDER BY nombre_caso""",
        {"pid": proveedor_id}
    )
    return df if df is not None else pd.DataFrame()


def save_caso_biblioteca(proveedor_id: int, caso: dict) -> bool:
    """Guarda o actualiza un caso en la biblioteca. Upsert por (proveedor_id, nombre_caso)."""
    return commit_query(
        """INSERT INTO caso_precio_biblioteca
               (proveedor_id, nombre_caso, dolar_politica, factor_conversion,
                descuento_1, descuento_2, descuento_3, descuento_4,
                genera_lpc03_lpc04, alcance_tipo, marcas, lineas)
           VALUES (:pid, :nc, :dp, :fc, :d1, :d2, :d3, :d4, :glpc, :at, :marcas, :lineas)
           ON CONFLICT (proveedor_id, nombre_caso) DO UPDATE SET
               dolar_politica    = EXCLUDED.dolar_politica,
               factor_conversion = EXCLUDED.factor_conversion,
               descuento_1       = EXCLUDED.descuento_1,
               descuento_2       = EXCLUDED.descuento_2,
               descuento_3       = EXCLUDED.descuento_3,
               descuento_4       = EXCLUDED.descuento_4,
               genera_lpc03_lpc04 = EXCLUDED.genera_lpc03_lpc04,
               alcance_tipo      = EXCLUDED.alcance_tipo,
               marcas            = EXCLUDED.marcas,
               lineas            = EXCLUDED.lineas""",
        {
            "pid":    proveedor_id,
            "nc":     caso["nombre_caso"].strip(),
            "dp":     float(caso["dolar_politica"]),
            "fc":     float(caso["factor_conversion"]),
            "d1":     caso.get("descuento_1"),
            "d2":     caso.get("descuento_2"),
            "d3":     caso.get("descuento_3"),
            "d4":     caso.get("descuento_4"),
            "glpc":   bool(caso.get("genera_lpc03_lpc04", True)),
            "at":     caso.get("alcance_tipo", "marcas"),
            "marcas": caso.get("marcas"),
            "lineas": caso.get("lineas"),
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# ELIMINACIÓN DE EVENTOS (solo no-cerrados y no-en_uso)
# ─────────────────────────────────────────────────────────────────────────────

def eliminar_evento(evento_id: int) -> tuple[bool, str]:
    """
    Elimina un listado de precios (evento) y todo lo calculado.
    Desvincula IC/ICP automáticamente. Pilares intactos.
    Retorna (ok, mensaje para UI).
    """
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, nombre_evento, estado FROM precio_evento WHERE id = :eid"),
                {"eid": evento_id},
            ).fetchone()
        if not row:
            return False, "El listado no existe o ya fue eliminado."

        nombre = str(row[1])

        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE intencion_compra SET precio_evento_id = NULL "
                    "WHERE precio_evento_id = :eid"
                ),
                {"eid": evento_id},
            )
            conn.execute(
                text(
                    "UPDATE intencion_compra_pedido SET precio_evento_id = NULL "
                    "WHERE precio_evento_id = :eid"
                ),
                {"eid": evento_id},
            )

        uso = evento_esta_en_uso(evento_id)
        if uso["en_uso"]:
            det = "; ".join(uso["modulos"])
            return False, f"No se puede eliminar: sigue referenciado. {det}"

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM precio_auditoria WHERE evento_id = :eid"), {"eid": evento_id})
            conn.execute(text(
                """DELETE FROM precio_evento_linea_excepcion
                   WHERE caso_id IN (SELECT id FROM precio_evento_caso WHERE evento_id = :eid)"""
            ), {"eid": evento_id})
            conn.execute(text("DELETE FROM precio_lista WHERE evento_id = :eid"), {"eid": evento_id})
            conn.execute(text("DELETE FROM precio_evento_caso WHERE evento_id = :eid"), {"eid": evento_id})
            conn.execute(text("DELETE FROM precio_evento WHERE id = :eid"), {"eid": evento_id})

        DBInspector.log(f"[ENGINE] Listado {evento_id} ({nombre}) eliminado", "SUCCESS")
        return True, f"Listado «{nombre}» eliminado. Podés cargar uno nuevo desde Nuevo Evento."
    except Exception as e:
        DBInspector.log(f"[ENGINE] Error eliminando evento {evento_id}: {e}", "ERROR")
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE ZIP DE PDFs POR EVENTO
# ─────────────────────────────────────────────────────────────────────────────

def get_precio_lista_completa(evento_id: int) -> pd.DataFrame:
    return get_dataframe(
        """SELECT pec.nombre_caso,
                  pl.marca,
                  COALESCE(l.codigo_proveedor::text, pl.linea_codigo)       AS linea,
                  COALESCE(r.codigo_proveedor::text, pl.referencia_codigo)  AS referencia,
                  COALESCE(m.codigo_proveedor::text, pl.material_descripcion) AS cod_material,
                  COALESCE(m.descripcion, pl.material_descripcion)          AS material,
                  pl.lpn, pl.lpc03, pl.lpc04,
                  pe.fecha_vigencia_desde AS fecha
           FROM precio_lista pl
           JOIN precio_evento_caso pec ON pec.id = pl.caso_id
           JOIN precio_evento      pe  ON pe.id  = pl.evento_id
           LEFT JOIN linea     l ON l.id  = pl.linea_codigo::bigint
           LEFT JOIN referencia r ON r.id = pl.referencia_codigo::bigint
           LEFT JOIN material   m ON m.id = pl.material_descripcion::bigint
           WHERE pl.evento_id = :eid
           ORDER BY pec.nombre_caso, pl.marca,
                    COALESCE(l.codigo_proveedor, pl.linea_codigo::bigint),
                    COALESCE(r.codigo_proveedor, pl.referencia_codigo::bigint)""",
        {"eid": evento_id},
    )


def _codigo_a_str(series: pd.Series) -> pd.Series:
    """
    Convierte códigos numéricos (línea, ref., material) a string entero limpio.
    Evita que ReportEngine aplique separadores de miles (8.224 → 8224).
    """
    def _fmt(v):
        try:
            if pd.isna(v) or str(v).strip() in ("", "nan", "None", "—"):
                return "—"
            return str(int(float(v)))
        except Exception:
            return str(v)
    return series.apply(_fmt)


def generar_zip_pdfs_evento(evento_id: int) -> BytesIO:
    """
    Genera un ZIP con un PDF por cada combinación (caso × marca × tipo_precio).
    Reutiliza ExportManager → ReportEngine (core centralizado).
    """
    from modules.sales_report.export import ExportManager

    df = get_precio_lista_completa(evento_id)
    if df is None or df.empty:
        return BytesIO()

    fecha_str = str(df["fecha"].iloc[0])[:10] if "fecha" in df.columns else str(date_type.today())
    nombre_evento_str = f"Evento #{evento_id} · {fecha_str}"

    zip_buf = BytesIO()
    count = 0

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for caso in df["nombre_caso"].unique():
            df_caso = df[df["nombre_caso"] == caso]
            for marca in df_caso["marca"].unique():
                df_marca = df_caso[df_caso["marca"] == marca]

                for col_precio, label in [("lpn", "LPN"), ("lpc03", "LPC03"), ("lpc04", "LPC04")]:
                    col_data = df_marca[col_precio].dropna()
                    if col_data.empty or (col_data == 0).all():
                        continue

                    df_pdf = df_marca[["linea", "referencia", "cod_material", "material", col_precio]].copy()
                    df_pdf = df_pdf[df_pdf[col_precio].notna() & (df_pdf[col_precio] > 0)]

                    # Códigos como strings enteros → sin separador de miles en el PDF
                    df_pdf["linea"]        = _codigo_a_str(df_pdf["linea"])
                    df_pdf["referencia"]   = _codigo_a_str(df_pdf["referencia"])
                    df_pdf["cod_material"] = _codigo_a_str(df_pdf["cod_material"])

                    df_pdf.columns = ["Línea", "Ref.", "Cód. Mat.", "Desc. Mat.", label]

                    titulo = f"{marca}  {label}  —  {caso}  —  {fecha_str}"
                    nombre_arch = f"{marca}_{caso}_{label}.pdf".replace(" ", "_")

                    pdf_io = ExportManager.generate_general_report(
                        titulo,
                        df_pdf,
                        group_cols=None,           # listado: sin jerarquía oculta
                        show_total=False,
                        mode="listado",
                        meta_info={"subtitulo": f"Lista de Precios · {nombre_evento_str}"},
                    )
                    zf.writestr(nombre_arch, pdf_io.getvalue())
                    count += 1

    DBInspector.log(f"[ENGINE] ZIP generado: {count} PDFs para evento {evento_id}", "SUCCESS")
    zip_buf.seek(0)
    return zip_buf


# ─────────────────────────────────────────────────────────────────────────────
# ADMINISTRACIÓN DE CASOS — CRUD biblioteca
# ─────────────────────────────────────────────────────────────────────────────

def eliminar_caso_biblioteca(caso_id: int) -> bool:
    """Elimina un caso de la biblioteca (marca como inactivo)."""
    return commit_query(
        "DELETE FROM caso_precio_biblioteca WHERE id = :id",
        {"id": caso_id}
    )


def update_caso_biblioteca(caso_id: int, caso: dict) -> bool:
    """Actualiza un caso existente en la biblioteca."""
    return commit_query(
        """UPDATE caso_precio_biblioteca SET
               nombre_caso        = :nc,
               dolar_politica     = :dp,
               factor_conversion  = :fc,
               descuento_1        = :d1,
               descuento_2        = :d2,
               descuento_3        = :d3,
               descuento_4        = :d4,
               genera_lpc03_lpc04 = :glpc,
               alcance_tipo       = :at,
               marcas             = :marcas,
               lineas             = :lineas
           WHERE id = :id""",
        {
            "id":     caso_id,
            "nc":     caso["nombre_caso"].strip(),
            "dp":     float(caso["dolar_politica"]),
            "fc":     float(caso["factor_conversion"]),
            "d1":     caso.get("descuento_1"),
            "d2":     caso.get("descuento_2"),
            "d3":     caso.get("descuento_3"),
            "d4":     caso.get("descuento_4"),
            "glpc":   bool(caso.get("genera_lpc03_lpc04", True)),
            "at":     caso.get("alcance_tipo", "marcas"),
            "marcas": caso.get("marcas"),
            "lineas": caso.get("lineas"),
        }
    )


def get_lineas_proveedor(proveedor_id: int) -> list[tuple[str, int]]:
    """Retorna lista de tuplas (codigo_proveedor, linea_id) para un proveedor."""
    df = get_dataframe(
        "SELECT codigo_proveedor::text, id FROM linea WHERE proveedor_id = :pid AND activo = true ORDER BY codigo_proveedor::int",
        {"pid": proveedor_id}
    )
    if df is None or df.empty:
        return []
    return [(str(row["codigo_proveedor"]), int(row["id"])) for _, row in df.iterrows()]


def actualizar_lineas_en_biblioteca(caso_id: int, codigos_proveedor: list[str]) -> tuple[bool, int]:
    """Persiste alcance por línea en caso_precio_biblioteca.lineas (no toca linea.caso_id)."""
    codigos = parse_lineas_array(codigos_proveedor)
    ok = commit_query(
        "UPDATE caso_precio_biblioteca SET lineas = :lineas WHERE id = :id",
        {"lineas": codigos, "id": caso_id},
    )
    return ok, len(codigos)


def sincronizar_lineas_caso(proveedor_id: int, caso_nombre: str, codigos_proveedor: list[str]) -> tuple[bool, int]:
    """Actualiza plantilla biblioteca.lineas; el caso operativo vive en el evento de precios."""
    from core.database import engine
    from sqlalchemy import text

    if not caso_nombre.strip():
        return False, 0
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""SELECT id FROM caso_precio_biblioteca
                       WHERE proveedor_id = :pid AND nombre_caso = :cn AND activo = true
                       LIMIT 1"""),
                {"pid": proveedor_id, "cn": caso_nombre.strip()},
            ).fetchone()
        if not row:
            DBInspector.log(
                f"[ENGINE] sincronizar_lineas_caso: caso '{caso_nombre}' no en biblioteca",
                "WARNING",
            )
            return False, 0
        return actualizar_lineas_en_biblioteca(int(row[0]), codigos_proveedor)
    except Exception as e:
        DBInspector.log(f"[ENGINE] sincronizar_lineas_caso error: {e}", "ERROR")
        return False, 0


# ─────────────────────────────────────────────────────────────────────────────
# EDITOR DE LINEA POR RANGO DE CODIGO (Caso + Genero)
# ─────────────────────────────────────────────────────────────────────────────

def actualizar_lineas_por_rango(
    proveedor_id: int,
    cod_desde: int,
    cod_hasta: int,
    caso_nombre: str | None,
    genero: str | None,
) -> tuple[bool, int]:
    """
    UPDATE linea (pilar) por rango de codigo_proveedor.
    Solo permite genero_id; caso_nombre se ignora (caso = por evento de precios).
    """
    if caso_nombre:
        DBInspector.log(
            "[ENGINE] actualizar_lineas_por_rango: caso_nombre ignorado "
            "(alcance comercial en precio_evento, no en linea)",
            "WARNING",
        )
    if genero is None:
        return False, 0

    sets = []
    params: dict = {"pid": proveedor_id, "desde": cod_desde, "hasta": cod_hasta}

    if genero is not None:
        g = (genero or "").strip()
        if g:
            with engine.begin() as conn:
                row = conn.execute(
                    text("SELECT id FROM genero WHERE descripcion = :g OR codigo = :g LIMIT 1"),
                    {"g": g},
                ).fetchone()
            if not row:
                DBInspector.log(
                    f"[ENGINE] actualizar_lineas_por_rango: genero '{g}' no encontrado",
                    "WARNING",
                )
                return False, 0
            sets.append("genero_id = :gen_id")
            params["gen_id"] = int(row[0])
        else:
            sets.append("genero_id = NULL")

    sql = f"""
        UPDATE linea
        SET {', '.join(sets)}
        WHERE proveedor_id = :pid
          AND codigo_proveedor::bigint BETWEEN :desde AND :hasta
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text(sql), params)
            return True, result.rowcount
    except Exception as e:
        DBInspector.log(f"[ENGINE] actualizar_lineas_por_rango error: {e}", "ERROR")
        return False, 0


# ─────────────────────────────────────────────────────────────────────────────
# PURGA COMPLETA DE LISTAS DE PRECIOS (mantiene pilares)
# ─────────────────────────────────────────────────────────────────────────────

def purgar_todas_las_listas() -> tuple[bool, dict]:
    """
    Elimina TODOS los eventos de precio y reinicia contadores (RESTART IDENTITY).
    Desvincula intencion_compra / intencion_compra_pedido antes de borrar (FK).
    Conserva: pilares, listado_precio (catálogo LPN/LPC). Vacía caso_precio_biblioteca (legacy).
  """
    try:
        with engine.begin() as conn:
            n_skus    = conn.execute(text("SELECT COUNT(*) FROM precio_lista")).fetchone()[0]
            n_casos   = conn.execute(text("SELECT COUNT(*) FROM precio_evento_caso")).fetchone()[0]
            n_eventos = conn.execute(text("SELECT COUNT(*) FROM precio_evento")).fetchone()[0]
            n_bib     = conn.execute(
                text("SELECT COUNT(*) FROM caso_precio_biblioteca")
            ).fetchone()[0]

            conn.execute(text(
                "UPDATE intencion_compra SET precio_evento_id = NULL "
                "WHERE precio_evento_id IS NOT NULL"
            ))
            conn.execute(text(
                "UPDATE intencion_compra_pedido SET precio_evento_id = NULL "
                "WHERE precio_evento_id IS NOT NULL"
            ))

            for tbl in (
                "precio_auditoria",
                "precio_evento_linea_excepcion",
                "precio_lista",
                "precio_evento_caso",
                "precio_evento",
            ):
                reg = conn.execute(
                    text("SELECT to_regclass(:r)"), {"r": f"public.{tbl}"}
                ).scalar()
                if reg:
                    conn.execute(text(f"TRUNCATE TABLE public.{tbl} RESTART IDENTITY CASCADE"))

            # NUNCA TRUNCATE CASCADE en biblioteca: linea.caso_id → caso_precio_biblioteca
            # y PostgreSQL borraría linea, referencia, linea_referencia en cascada.
            reg_bib = conn.execute(
                text("SELECT to_regclass('public.caso_precio_biblioteca')")
            ).scalar()
            if reg_bib:
                conn.execute(text("DELETE FROM public.caso_precio_biblioteca"))
                conn.execute(
                    text(
                        "SELECT setval(pg_get_serial_sequence("
                        "'public.caso_precio_biblioteca', 'id'), 1, false)"
                    )
                )

        DBInspector.log(
            f"[ENGINE] PURGA TOTAL: {n_eventos} eventos, {n_casos} casos evento, "
            f"{n_skus} SKUs, {n_bib} plantillas biblioteca; IDs reiniciados",
            "WARNING",
        )
        return True, {
            "eventos": int(n_eventos),
            "casos": int(n_casos),
            "skus": int(n_skus),
            "biblioteca": int(n_bib),
        }
    except Exception as e:
        DBInspector.log(f"[ENGINE] purgar_todas_las_listas error: {e}", "ERROR")
        return False, {}
