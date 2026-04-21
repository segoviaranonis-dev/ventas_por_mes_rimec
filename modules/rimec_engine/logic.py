"""
RIMEC ENGINE — logic.py
Motor de cálculo de precios. Lee Excel del proveedor, ejecuta fórmulas,
persiste en Supabase. Sin lógica de UI.
"""

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
        for hoja in hojas:
            df_raw = xl.parse(hoja, header=None)

            # Buscar fila de encabezado
            header_row = None
            for i, row in df_raw.iterrows():
                row_str = " ".join(str(v).upper() for v in row if pd.notna(v))
                if any(k in row_str for k in ["FOB", "PRECIO", "COSTO", "REFERENCIA", "REF"]):
                    header_row = i
                    break

            if header_row is None:
                DBInspector.log(f"[ENGINE] Hoja '{hoja}' sin encabezado — saltada", "AVISO")
                continue

            df_raw.columns = df_raw.iloc[header_row]
            df_raw = df_raw.iloc[header_row + 1:].reset_index(drop=True)
            df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]

            col_map = _mapear_columnas(df_raw.columns.tolist())
            if not col_map:
                DBInspector.log(f"[ENGINE] Hoja '{hoja}' sin columnas mapeables — saltada. Columnas detectadas: {df_raw.columns.tolist()}", "AVISO")
                continue
            DBInspector.log(f"[ENGINE] Hoja '{hoja}' mapeada: {col_map}", "SUCCESS")

            df_clean = pd.DataFrame({
                "marca":       hoja,
                "linea":       df_raw[col_map["linea"]].astype(str).str.strip() if col_map.get("linea") else "—",
                "referencia":  df_raw[col_map["referencia"]].astype(str).str.strip(),
                "material":    df_raw[col_map["material"]].astype(str).str.strip() if col_map.get("material") else "—",
                "fob_fabrica": pd.to_numeric(df_raw[col_map["fob"]], errors="coerce"),
            })
            df_clean = df_clean.dropna(subset=["fob_fabrica", "referencia"])
            df_clean = df_clean[df_clean["fob_fabrica"] > 0]
            df_clean = df_clean[df_clean["referencia"].str.len() > 0]
            frames.append(df_clean)

        if not frames:
            return {"marcas": [], "skus": pd.DataFrame(), "error": "No se encontraron hojas con datos válidos."}

        skus = pd.concat(frames, ignore_index=True)
        marcas = skus["marca"].unique().tolist()
        return {"marcas": marcas, "skus": skus, "error": None}

    except Exception as e:
        DBInspector.log(f"[ENGINE] Error leyendo Excel: {e}", "ERROR")
        return {"marcas": [], "skus": pd.DataFrame(), "error": str(e)}


def _mapear_columnas(cols: list) -> dict:
    mapping = {}
    for c in cols:
        cu = c.upper().strip()
        if any(k in cu for k in ["FOB", "PRECIO", "COSTO", "PRICE"]) and "fob" not in mapping:
            mapping["fob"] = c
        if any(k in cu for k in ["REF", "MODELO", "ARTICULO", "ARTÍCULO", "SKU"]) and "referencia" not in mapping:
            mapping["referencia"] = c
        if any(k in cu for k in ["LINEA", "LÍNEA", "LINHA", "LINE", "LIN.", "GRUPO", "GRP"]) and "linea" not in mapping:
            mapping["linea"] = c
        # Descripción textual del material (ej. "DESC. CAB." → "NAPA TURIM")
        if any(k in cu for k in ["DESC"]) and "descripcion" not in mapping:
            mapping["descripcion"] = c
        # Código numérico del material/cabedal (ej. "CAB." → 9569)
        if any(k in cu for k in ["MATERIAL", "MATER", "MAT", "ACAB", "CABEDAL", "CAB.", "UPPER"]) and "material" not in mapping:
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


def get_or_create_material(proveedor_id: int, codigo_proveedor: int) -> int | None:
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT id FROM material WHERE proveedor_id = :pid AND codigo_proveedor = :cod LIMIT 1"),
                {"pid": proveedor_id, "cod": codigo_proveedor}
            ).fetchone()
            if row:
                return int(row[0])
            row = conn.execute(
                text("INSERT INTO material (proveedor_id, codigo_proveedor) VALUES (:pid, :cod) RETURNING id"),
                {"pid": proveedor_id, "cod": codigo_proveedor}
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


def guardar_lineas_excepcion(caso_id: int, linea_codigos: list, proveedor_id: int):
    """Guarda excepciones por código de línea del proveedor."""
    for cod in linea_codigos:
        try:
            cod_int = int(cod)
        except (ValueError, TypeError):
            continue
        commit_query(
            """INSERT INTO precio_evento_linea_excepcion (caso_id, linea_id)
               SELECT :cid, id FROM linea
               WHERE proveedor_id = :pid AND codigo_proveedor = :cod LIMIT 1""",
            {"cid": caso_id, "pid": proveedor_id, "cod": cod_int},
            show_error=False
        )


def guardar_precio_lista(filas: list[dict]):
    """
    Inserta todas las filas en precio_lista en UNA sola transacción (bulk).
    Cada fila: eid, cid, marca, lc, rc, md, fob, foba, lpn, lpc03, lpc04,
               dolar_ap, factor_ap, indice_ap, d1..d4_ap, nombre_caso_ap
    """
    if not filas:
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""INSERT INTO precio_lista
                        (evento_id, caso_id, marca,
                         linea_codigo, referencia_codigo, material_descripcion,
                         fob_fabrica, fob_ajustado, lpn, lpc03, lpc04, vigente,
                         dolar_aplicado, factor_aplicado, indice_aplicado,
                         descuento_1_aplicado, descuento_2_aplicado,
                         descuento_3_aplicado, descuento_4_aplicado,
                         nombre_caso_aplicado)
                        VALUES (:eid, :cid, :marca,
                                :lc, :rc, :md,
                                :fob, :foba, :lpn, :lpc03, :lpc04, false,
                                :dolar_ap, :factor_ap, :indice_ap,
                                :d1_ap, :d2_ap, :d3_ap, :d4_ap,
                                :nombre_caso_ap)"""),
                filas,
            )
            DBInspector.log(f"[ENGINE] Bulk INSERT: {len(filas)} filas en 1 transacción", "SUCCESS")
    except Exception as e:
        DBInspector.log(f"[ENGINE] Bulk INSERT falló: {e}", "ERROR")


def avanzar_estado_evento(evento_id: int, estado: str):
    commit_query(
        "UPDATE precio_evento SET estado = :e WHERE id = :id",
        {"e": estado, "id": evento_id}
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


def contar_skus_procesados(evento_id: int) -> int:
    df = get_dataframe(
        "SELECT COUNT(*) as n FROM precio_lista WHERE evento_id = :eid",
        {"eid": evento_id}
    )
    return int(df.iloc[0]["n"]) if df is not None and not df.empty else 0


# ─────────────────────────────────────────────────────────────────────────────
# ELIMINACIÓN DE EVENTOS (solo no-cerrados)
# ─────────────────────────────────────────────────────────────────────────────

def eliminar_evento(evento_id: int) -> bool:
    """Elimina evento y sus datos. Rechaza eventos cerrados."""
    try:
        with engine.begin() as conn:
            # Verificar que no sea cerrado
            row = conn.execute(
                text("SELECT estado FROM precio_evento WHERE id = :eid"),
                {"eid": evento_id}
            ).fetchone()
            if not row or row[0] == "cerrado":
                DBInspector.log(f"[ENGINE] Intento de eliminar evento cerrado {evento_id} — rechazado", "AVISO")
                return False
            # Borrar en orden (sin CASCADE)
            conn.execute(text("DELETE FROM precio_auditoria WHERE evento_id = :eid"), {"eid": evento_id})
            conn.execute(text(
                """DELETE FROM precio_evento_linea_excepcion
                   WHERE caso_id IN (SELECT id FROM precio_evento_caso WHERE evento_id = :eid)"""
            ), {"eid": evento_id})
            conn.execute(text("DELETE FROM precio_lista WHERE evento_id = :eid"), {"eid": evento_id})
            conn.execute(text("DELETE FROM precio_evento_caso WHERE evento_id = :eid"), {"eid": evento_id})
            conn.execute(text("DELETE FROM precio_evento WHERE id = :eid"), {"eid": evento_id})
        DBInspector.log(f"[ENGINE] Evento {evento_id} eliminado", "SUCCESS")
        return True
    except Exception as e:
        DBInspector.log(f"[ENGINE] Error eliminando evento {evento_id}: {e}", "ERROR")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE ZIP DE PDFs POR EVENTO
# ─────────────────────────────────────────────────────────────────────────────

def get_precio_lista_completa(evento_id: int) -> pd.DataFrame:
    return get_dataframe(
        """SELECT pec.nombre_caso,
                  pl.marca,
                  COALESCE(l.codigo_proveedor::text, pl.linea_codigo)       AS linea,
                  COALESCE(r.codigo_proveedor::text, pl.referencia_codigo)  AS referencia,
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
           ORDER BY pec.nombre_caso, pl.marca, pl.linea_codigo, pl.referencia_codigo""",
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

                    df_pdf = df_marca[["linea", "referencia", "material", col_precio]].copy()
                    # "material" ya contiene COALESCE(m.descripcion, cab_codigo) del JOIN
                    df_pdf = df_pdf[df_pdf[col_precio].notna() & (df_pdf[col_precio] > 0)]

                    # Códigos como strings enteros → sin separador de miles en el PDF
                    df_pdf["linea"]     = _codigo_a_str(df_pdf["linea"])
                    df_pdf["referencia"] = _codigo_a_str(df_pdf["referencia"])
                    df_pdf["material"]  = _codigo_a_str(df_pdf["material"])

                    df_pdf.columns = ["Línea", "Ref.", "Desc. Cab.", label]

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
