"""
HIEDRA v2.0 — Motor de importación inteligente.
Dos perfiles de entrada, un solo motor de salida.

  PERFIL A (normal)  → Excel limpio, columnas con cabecera → leer_excel_proveedor()
  PERFIL B (Hiedra)  → Excel sucio, columnas por posición  → leer_excel_hiedra()

La detección es automática por nombre de archivo en Paso 0.
Si el nombre no coincide con el patrón Hiedra, el flujo normal no se toca.
"""

import re
import pandas as pd


# ── IDs reales de categoria_v2 ────────────────────────────────────────────────
_MAPA_CATEGORIAS = {
    "CP": 2,   # PRE VENTA (Compra Previa)
    "PR": 3,   # PROGRAMADO
}


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 1 — Parser de nombre de archivo
# ─────────────────────────────────────────────────────────────────────────────

def parsear_nombre_hiedra(nombre_archivo: str) -> dict:
    """
    Extrae metadatos del nombre del archivo.
    Formato esperado: {CATEGORIA}-{NRO_PROFORMA}-PP-{NRO_PP_EXTERNO}.xls(x)
    Ejemplo: CP-6421-PP-4015.xls

    Retorna dict con campos (todos None si el nombre no coincide):
      - categoria_codigo    : "CP" | "PR" | None
      - categoria_id        : int  | None  (id_categoria real en BD)
      - nro_proforma_fabrica: str  | None
      - nro_pp_externo      : str  | None
      - reconocido          : bool
    """
    resultado = {
        "categoria_codigo":     None,
        "categoria_id":         None,
        "nro_proforma_fabrica": None,
        "nro_pp_externo":       None,
        "reconocido":           False,
    }

    nombre = re.sub(r"\.xlsx?$", "", nombre_archivo, flags=re.IGNORECASE).upper().strip()
    match  = re.match(r"^([A-Z]{2})-(\d+)-PP-(\d+)$", nombre)

    if match:
        codigo = match.group(1)
        cat_id = _MAPA_CATEGORIAS.get(codigo)
        resultado.update({
            "categoria_codigo":     codigo,
            "categoria_id":         cat_id,
            "nro_proforma_fabrica": match.group(2),
            "nro_pp_externo":       match.group(3),
            "reconocido":           cat_id is not None,
        })

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 2 — Parser de celda Línea/Referencia con separador punto
# ─────────────────────────────────────────────────────────────────────────────

def parsear_linea_referencia(valor_celda) -> tuple[int, int | None]:
    """
    Interpreta el valor de la celda de línea.

    '1122.806' → (1122, 806)   — línea y referencia juntas
    '1122'     → (1122, None)  — solo línea, referencia en siguiente columna
    1122       → (1122, None)

    Raises ValueError si el valor no es parseable.
    """
    valor_str = str(valor_celda).strip()

    if "." in valor_str:
        partes = valor_str.split(".", 1)
        try:
            return (int(partes[0]), int(partes[1]))
        except ValueError:
            raise ValueError(f"No se pudo parsear '{valor_celda}' como Línea.Referencia")

    try:
        return (int(float(valor_str)), None)
    except ValueError:
        raise ValueError(f"Valor de línea inválido: '{valor_celda}'")


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 3 — Detector de fila de inicio de datos
# ─────────────────────────────────────────────────────────────────────────────

def detectar_fila_inicio(df_raw) -> int:
    """
    Escanea las primeras 20 filas buscando donde comienzan los datos reales.
    Criterio: columna A es numérica (o formato NNN.NNN) y columna E es FOB > 0.

    Retorna el índice de la primera fila de datos.
    Raises ValueError si no encuentra datos válidos.
    """
    for i, row in df_raw.head(20).iterrows():
        val_a = str(row.iloc[0]).strip()
        val_e = row.iloc[4] if len(row) > 4 else None

        es_linea = bool(re.match(r"^\d+(\.\d+)?$", val_a))

        es_fob = False
        try:
            if val_e is not None:
                es_fob = float(val_e) > 0
        except (ValueError, TypeError):
            pass

        if es_linea and es_fob:
            return i

    raise ValueError("No se encontraron datos válidos en las primeras 20 filas del archivo.")


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 4 — Lector de Excel sucio (columnas por posición)
# ─────────────────────────────────────────────────────────────────────────────

def leer_excel_hiedra(archivo_bytes, nombre_archivo: str) -> dict:
    """
    Parser Perfil B: Excel con pilares en posición fija (sin cabecera confiable).
    Posiciones: 0=linea, 1=referencia, 2=material_cod, 3=material_desc, 4=fob_usd
    Columnas extra se ignoran.

    Retorna el mismo dict que leer_excel_proveedor():
      {"marcas": [str], "skus": DataFrame, "error": str|None}
    Con columns: marca, linea, referencia, material, descripcion, fob_fabrica
    """
    try:
        engine_xls = "xlrd" if nombre_archivo.lower().endswith(".xls") else "openpyxl"
        xl = pd.ExcelFile(archivo_bytes, engine=engine_xls)

        frames = []
        for hoja in xl.sheet_names:
            df_raw = xl.parse(hoja, header=None)
            try:
                fila_inicio = detectar_fila_inicio(df_raw)
            except ValueError:
                continue

            df_datos = df_raw.iloc[fila_inicio:].reset_index(drop=True)
            filas = []

            for _, row in df_datos.iterrows():
                try:
                    linea_cod, ref_cod = parsear_linea_referencia(row.iloc[0])
                    if ref_cod is None:
                        ref_cod = int(float(str(row.iloc[1]).strip()))
                    mat_cod  = int(float(str(row.iloc[2]).strip()))
                    mat_desc = str(row.iloc[3]).strip() if len(row) > 3 else ""
                    fob      = float(row.iloc[4])
                    if fob <= 0:
                        continue
                    filas.append({
                        "marca":       hoja,
                        "linea":       str(linea_cod),
                        "referencia":  str(ref_cod),
                        "material":    str(mat_cod),
                        "descripcion": mat_desc,
                        "fob_fabrica": fob,
                    })
                except (ValueError, TypeError, IndexError):
                    continue

            if filas:
                frames.append(pd.DataFrame(filas))

        if not frames:
            return {"marcas": [], "skus": pd.DataFrame(),
                    "error": "No se encontraron datos válidos en ninguna hoja."}

        skus   = pd.concat(frames, ignore_index=True)
        marcas = skus["marca"].unique().tolist()
        return {"marcas": marcas, "skus": skus, "error": None}

    except Exception as e:
        return {"marcas": [], "skus": pd.DataFrame(), "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 5 — Utilidades de talla
# ─────────────────────────────────────────────────────────────────────────────

def extraer_valor_numerico_talla(etiqueta) -> float:
    """
    Convierte cualquier formato de talla a float para ordenamiento.
    '19'    → 19.0
    '27/28' → 27.0  (toma el menor)
    '35/36' → 35.0
    27      → 27.0
    """
    etiqueta_str = str(etiqueta).strip()
    if "/" in etiqueta_str:
        return float(etiqueta_str.split("/")[0])
    try:
        return float(etiqueta_str)
    except ValueError:
        return 0.0
