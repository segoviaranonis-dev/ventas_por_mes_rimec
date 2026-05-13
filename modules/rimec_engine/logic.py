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
        razones = []
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
                razon = f"Hoja '{hoja}': No se encontró fila de encabezados (FOB, PRECIO, REFERENCIA)."
                DBInspector.log(f"[ENGINE] {razon}", "AVISO")
                razones.append(razon)
                continue

            df_raw.columns = df_raw.iloc[header_row]
            df_raw = df_raw.iloc[header_row + 1:].reset_index(drop=True)
            df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]

            col_map = _mapear_columnas(df_raw.columns.tolist())
            if not col_map:
                razon = f"Hoja '{hoja}': No se pudieron mapear las columnas obligatorias. Detectadas: {df_raw.columns.tolist()}"
                DBInspector.log(f"[ENGINE] {razon}", "AVISO")
                razones.append(razon)
                continue
            DBInspector.log(f"[ENGINE] Hoja '{hoja}' mapeada: {col_map}", "SUCCESS")

            df_clean = pd.DataFrame({
                "marca":        hoja,
                "linea":        df_raw[col_map["linea"]].astype(str).str.strip() if col_map.get("linea") else "—",
                "referencia":   df_raw[col_map["referencia"]].astype(str).str.strip(),
                "material":     df_raw[col_map["material"]].astype(str).str.strip() if col_map.get("material") else "—",
                "descripcion":  df_raw[col_map["descripcion"]].astype(str).str.strip() if col_map.get("descripcion") else "",
                "fob_fabrica":  pd.to_numeric(df_raw[col_map["fob"]], errors="coerce"),
            })
            total_antes = len(df_clean)
            df_clean = df_clean.dropna(subset=["fob_fabrica", "referencia"])
            df_clean = df_clean[df_clean["fob_fabrica"] > 0]
            df_clean = df_clean[df_clean["referencia"].str.len() > 0]
            
            if df_clean.empty:
                razon = f"Hoja '{hoja}': Sin datos tras limpiar valores nulos o FOB=0 (de {total_antes} filas)."
                razones.append(razon)
            else:
                frames.append(df_clean)

        if not frames:
            mensaje_error = "No se encontraron hojas con datos válidos.\n\nDetalles:\n" + "\n".join(f"- {r}" for r in razones)
            return {"marcas": [], "skus": pd.DataFrame(), "error": mensaje_error}

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
    Al cerrar un evento, actualiza linea.caso_id para las lineas que aparecieron
    en el evento. El "caso conceptual" se busca en caso_precio_biblioteca por
    (proveedor_id, nombre_caso). Si no hay match en biblioteca, se omite la
    actualizacion para esa linea (no se inventa un caso).

    Tabla linea es la unica fuente de verdad - ya no se usa linea_caso.
    """
    if _evento_esta_cerrado(evento_id):
        DBInspector.log(
            f"[ENGINE] generar_maestro bloqueado - evento {evento_id} ya CERRADO",
            "WARNING",
        )
        return
    df = get_dataframe("""
        SELECT DISTINCT
            l.id           AS linea_id,
            l.proveedor_id,
            pec.nombre_caso
        FROM precio_lista pl
        JOIN precio_evento_caso pec ON pec.id = pl.caso_id
        JOIN linea l ON l.id = pl.linea_id
        WHERE pl.evento_id = :eid
          AND pl.linea_id IS NOT NULL
    """, {"eid": evento_id})

    if df is None or df.empty:
        DBInspector.log(f"[ENGINE] generar_maestro_lineas: sin datos para evento {evento_id}", "AVISO")
        return

    df_dedup = df.drop_duplicates(subset=["linea_id"])

    ok_count = 0
    skipped = 0
    for _, row in df_dedup.iterrows():
        ok = commit_query("""
            UPDATE linea
            SET caso_id = cpb.id
            FROM caso_precio_biblioteca cpb
            WHERE linea.id = :lid
              AND cpb.proveedor_id = :pid
              AND cpb.nombre_caso  = :caso
              AND cpb.activo = true
        """, {
            "lid":  int(row["linea_id"]),
            "pid":  int(row["proveedor_id"]),
            "caso": str(row["nombre_caso"]).strip(),
        })
        if ok:
            ok_count += 1
        else:
            skipped += 1

    DBInspector.log(
        f"[ENGINE] linea.caso_id actualizado: {ok_count}/{len(df_dedup)} lineas "
        f"({skipped} sin match en biblioteca)",
        "SUCCESS",
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
    # Generar maestro de líneas automáticamente al cerrar
    generar_maestro_lineas_desde_evento(evento_id)


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


def resolver_casos_skus(skus_df: pd.DataFrame, proveedor_id: int, df_bib: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """
    Cruza el DataFrame de SKUs con la asignacion linea.caso_id -> caso_precio_biblioteca.
    Retorna el DataFrame enriquecido con 'caso_asignado' y 'estado_validacion',
    y un booleano indicando si esta listo para calcular (sin errores).
    """
    nombres_bib = set(df_bib["nombre_caso"].tolist()) if not df_bib.empty else set()

    # Mapeo: codigo_linea -> nombre_caso (desde linea.caso_id)
    df_maestro = get_dataframe("""
        SELECT l.codigo_proveedor::text AS linea, cpb.nombre_caso AS caso_nombre
        FROM linea l
        JOIN caso_precio_biblioteca cpb ON cpb.id = l.caso_id
        WHERE l.proveedor_id = :pid AND l.activo = true
          AND cpb.nombre_caso IS NOT NULL
    """, {"pid": proveedor_id})
    
    maestro_map = {}
    if df_maestro is not None and not df_maestro.empty:
        maestro_map = dict(zip(df_maestro["linea"], df_maestro["caso_nombre"]))

    casos_asignados = []
    estados = []
    hay_error = False

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

        caso_maestro = maestro_map.get(linea_val)
        
        if caso_maestro:
            if caso_maestro in nombres_bib:
                casos_asignados.append(caso_maestro)
                estados.append("✅ OK")
            else:
                casos_asignados.append(caso_maestro)
                estados.append(f"❌ ERROR (Falta '{caso_maestro}' en Biblioteca)")
                hay_error = True
        else:
            # Fallback
            if marca in ["BR SPORT", "ACTVITTA"]:
                fallback = "NORMAL BR-S ACT"
            else:
                fallback = "NORMAL BR-VZ-ML-MD-MKA/O"
                
            if fallback in nombres_bib:
                casos_asignados.append(fallback)
                estados.append("⚠️ NUEVA (Usando Default)")
            else:
                casos_asignados.append(fallback)
                estados.append(f"❌ ERROR (Falta fallback '{fallback}' en Biblioteca)")
                hay_error = True

    # Para evitar warnings de copias encadenadas
    skus_df = skus_df.copy()
    skus_df["caso_asignado"] = casos_asignados
    skus_df["estado_validacion"] = estados
    
    return skus_df, not hay_error


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

def eliminar_evento(evento_id: int) -> bool:
    """Elimina evento y sus datos. Rechaza eventos cerrados o en uso por otros módulos."""
    try:
        # Verificar que no sea cerrado
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT estado FROM precio_evento WHERE id = :eid"),
                {"eid": evento_id}
            ).fetchone()
        if not row or row[0] == "cerrado":
            DBInspector.log(f"[ENGINE] Intento de eliminar evento cerrado {evento_id} — rechazado", "AVISO")
            return False

        # Verificar que no esté en uso por módulos internos
        uso = evento_esta_en_uso(evento_id)
        if uso["en_uso"]:
            DBInspector.log(f"[ENGINE] Evento {evento_id} en uso — rechazado: {uso['detalle']}", "AVISO")
            return False

        # Borrar en orden (hijos antes que padres)
        with engine.begin() as conn:
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


def sincronizar_lineas_caso(proveedor_id: int, caso_nombre: str, codigos_proveedor: list[str]) -> tuple[bool, int]:
    """
    Sincroniza que lineas (codigos_proveedor) estan asignadas al caso `caso_nombre`
    de la biblioteca del proveedor. Funciona en dos pasos atomicos:
      1) Des-asigna (caso_id -> NULL) las lineas del proveedor que hoy tienen ese caso
         pero NO estan en la lista nueva.
      2) Asigna ese caso a las lineas de la lista nueva (UPDATE linea.caso_id).
    """
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
                    f"[ENGINE] sincronizar_lineas_caso: caso '{caso_nombre}' no existe "
                    f"en biblioteca del proveedor {proveedor_id}",
                    "WARNING",
                )
                return False, 0
            caso_id = int(row[0])

            codigos_int = []
            for cod in codigos_proveedor:
                try:
                    codigos_int.append(int(cod))
                except (ValueError, TypeError):
                    continue

            if codigos_int:
                conn.execute(
                    text("""UPDATE linea SET caso_id = NULL
                            WHERE proveedor_id = :pid
                              AND caso_id = :cid
                              AND codigo_proveedor::bigint <> ALL(:codigos)"""),
                    {"pid": proveedor_id, "cid": caso_id, "codigos": codigos_int},
                )
            else:
                conn.execute(
                    text("""UPDATE linea SET caso_id = NULL
                            WHERE proveedor_id = :pid AND caso_id = :cid"""),
                    {"pid": proveedor_id, "cid": caso_id},
                )

            n_actualizadas = 0
            if codigos_int:
                result = conn.execute(
                    text("""UPDATE linea SET caso_id = :cid
                            WHERE proveedor_id = :pid
                              AND codigo_proveedor::bigint = ANY(:codigos)"""),
                    {"pid": proveedor_id, "cid": caso_id, "codigos": codigos_int},
                )
                n_actualizadas = result.rowcount

            return True, n_actualizadas
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
    UPDATE linea (tabla pilar) para todas las lineas del proveedor cuyo
    codigo_proveedor este en el rango [cod_desde, cod_hasta] (ambos inclusive).

      - caso_nombre: nombre del caso en caso_precio_biblioteca -> linea.caso_id
      - genero: descripcion del genero en tabla genero -> linea.genero_id

    None = no tocar ese campo. Retorna (ok, n_filas_afectadas).
    """
    if not caso_nombre and genero is None:
        return False, 0

    sets = []
    params: dict = {"pid": proveedor_id, "desde": cod_desde, "hasta": cod_hasta}

    if caso_nombre:
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
                    f"[ENGINE] actualizar_lineas_por_rango: caso '{caso_nombre}' no "
                    f"encontrado en biblioteca del proveedor {proveedor_id}",
                    "WARNING",
                )
                return False, 0
            sets.append("caso_id = :caso_id")
            params["caso_id"] = int(row[0])
        except Exception as e:
            DBInspector.log(f"[ENGINE] resolver caso_id error: {e}", "ERROR")
            return False, 0

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
    Elimina TODOS los eventos de precio, sus casos y su precio_lista.
    Preserva intactos: linea (con su caso_id), referencia, material, color, linea_referencia.
    Retorna (ok, {"eventos": n, "casos": n, "skus": n}).
    """
    try:
        with engine.begin() as conn:
            n_skus    = conn.execute(text("SELECT COUNT(*) FROM precio_lista")).fetchone()[0]
            n_casos   = conn.execute(text("SELECT COUNT(*) FROM precio_evento_caso")).fetchone()[0]
            n_eventos = conn.execute(text("SELECT COUNT(*) FROM precio_evento")).fetchone()[0]

            conn.execute(text("DELETE FROM precio_auditoria"))
            conn.execute(text("DELETE FROM precio_evento_linea_excepcion"))
            conn.execute(text("DELETE FROM precio_lista"))
            conn.execute(text("DELETE FROM precio_evento_caso"))
            conn.execute(text("DELETE FROM precio_evento"))

        DBInspector.log(
            f"[ENGINE] PURGA TOTAL: {n_eventos} eventos, {n_casos} casos, {n_skus} SKUs eliminados",
            "WARNING"
        )
        return True, {"eventos": int(n_eventos), "casos": int(n_casos), "skus": int(n_skus)}
    except Exception as e:
        DBInspector.log(f"[ENGINE] purgar_todas_las_listas error: {e}", "ERROR")
        return False, {}
