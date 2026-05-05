# =============================================================================
# MÓDULO: Carga Stock Tránsito
# ARCHIVO: modules/carga_transito/logic.py
# DESCRIPCIÓN: Carga masiva de stock en tránsito desde Proforma Beira Rio.
#              Garantiza los 5 Pilares y deja el PP listo para reservas.
# =============================================================================

import io
import math
import json
import pandas as pd
from datetime import date
from sqlalchemy import text as sqlt

from core.database import get_dataframe, engine, DBInspector
from core.auditoria import log_flujo, A


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _safe_int(val) -> int:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _safe_float(val) -> float:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# NUMERACIÓN PP
# ─────────────────────────────────────────────────────────────────────────────

def _get_next_nro_pp(anio: int | None = None) -> str:
    if anio is None:
        anio = date.today().year
    df = get_dataframe("""
        SELECT COALESCE(
            MAX(CAST(SPLIT_PART(numero_registro, '-', 3) AS INTEGER)), 0
        ) AS ultimo
        FROM pedido_proveedor
        WHERE numero_registro ~ '^PP-[0-9]{4}-[0-9]+$'
          AND numero_registro LIKE :patron
    """, {"patron": f"PP-{anio}-%"})
    ultimo = int(df["ultimo"].iloc[0]) if df is not None and not df.empty else 0
    return f"PP-{anio}-{ultimo + 1:04d}"


# ─────────────────────────────────────────────────────────────────────────────
# PARSER DE PROFORMA BEIRA RIO
# ─────────────────────────────────────────────────────────────────────────────

def parse_proforma_beira_rio(file_bytes: bytes) -> tuple[pd.DataFrame, int, str | None]:
    """
    Parser oficial de Fatura Proforma Beira Rio.
    
    Extrae los 5 Pilares:
      - Linea (STYLE columna A antes del punto)
      - Referencia (STYLE columna A después del punto)  
      - Material (MATERIAL CODE + MATERIAL descripción)
      - Color (COLOR CODE + COLOR descripción)
      - Tallas (curva dinámica desde columna O en adelante)
    
    Retorna: (DataFrame con SKUs, total_pares, error_msg)
    """
    from modules.rimec_engine.hiedra import parsear_linea_referencia

    GRADE_START = 14  # Columna O (índice 14)

    try:
        try:
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, engine="openpyxl")
        except Exception:
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, engine="xlrd")
    except Exception as e:
        return pd.DataFrame(), 0, f"No se pudo leer el archivo: {e}"

    if df_raw.empty or df_raw.shape[1] < 15:
        return pd.DataFrame(), 0, "El archivo no tiene el formato esperado de Fatura Proforma."

    def _grade_label(v) -> str | None:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        s = str(v).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return s if s else None

    # Buscar el offset real de la tabla y la fila de encabezados
    offset = 0
    grade_start = 14
    header_row_idx = 0
    for i in range(min(50, len(df_raw))):
        row_strs = [str(x).strip().upper() for x in df_raw.iloc[i]]
        if "STYLE" in row_strs and "ITEM" in row_strs:
            header_row_idx = i
            offset = row_strs.index("ITEM")
            if "AMOUNT" in row_strs:
                grade_start = row_strs.index("AMOUNT") + 1
            else:
                grade_start = 14 + offset
            break

    # Leer cabecera de tallas inicial
    current_grades: list[str] = []
    if header_row_idx < len(df_raw):
        for col_i in range(grade_start, df_raw.shape[1]):
            lbl = _grade_label(df_raw.iloc[header_row_idx, col_i])
            if lbl:
                current_grades.append(lbl)

    rows: list[dict] = []

    for row_i in range(header_row_idx + 1, len(df_raw)):
        row = df_raw.iloc[row_i]

        if offset >= len(row):
            continue

        item_val = row.iloc[offset]

        # Fila de TOTALES → fin de datos
        col_pairs_idx = 11 + offset
        col_style_idx = 2 + offset

        pairs_str = str(row.iloc[col_pairs_idx]).strip().upper() if len(row) > col_pairs_idx else ""
        col2_str = str(row.iloc[col_style_idx]).strip().upper() if len(row) > col_style_idx else ""
        if pairs_str == "TOTAL" or col2_str == "TOTAL":
            break

        item_null = item_val is None or (isinstance(item_val, float) and math.isnan(item_val))

        # Fila SEPARADORA (col A nula, cols O+ con tallas)
        if item_null:
            new_grades: list[str] = []
            for col_i in range(grade_start, df_raw.shape[1]):
                lbl = _grade_label(row.iloc[col_i])
                if lbl:
                    new_grades.append(lbl)
            if new_grades:
                current_grades = new_grades
            continue

        # Fila de DATOS
        style_raw = str(row.iloc[col_style_idx]).strip() if len(row) > col_style_idx and pd.notna(row.iloc[col_style_idx]) else ""
        try:
            linea_cod, ref_cod = parsear_linea_referencia(style_raw)
        except ValueError:
            continue  # fila mal formada, saltar

        # Curva de tallas: {talla_label: cantidad}
        grades_json: dict[str, int] = {}
        for g_i, grade in enumerate(current_grades):
            col_i = grade_start + g_i
            if col_i < len(row):
                qty = _safe_int(row.iloc[col_i])
                if qty > 0:
                    grades_json[grade] = qty

        # Rango compacto: "33-40"
        active = sorted(grades_json.keys(), key=lambda x: float(x.split("/")[0]) if x.replace("/", "").replace(".", "").isdigit() else 0)
        grade_range = f"{active[0]}-{active[-1]}" if active else ""

        rows.append({
            "item":          str(_safe_int(item_val)),
            "ncm":           str(row.iloc[1 + offset]).strip() if len(row) > 1 + offset and pd.notna(row.iloc[1 + offset]) else "",
            "style_code":    style_raw,
            "linea_cod":     str(linea_cod),
            "ref_cod":       str(ref_cod) if ref_cod is not None else "",
            "name":          str(row.iloc[3 + offset]).strip() if len(row) > 3 + offset and pd.notna(row.iloc[3 + offset]) else "",
            "material_code": str(_safe_int(row.iloc[4 + offset])) if len(row) > 4 + offset else "0",
            "material":      str(row.iloc[5 + offset]).strip() if len(row) > 5 + offset and pd.notna(row.iloc[5 + offset]) else "",
            "color_code":    str(_safe_int(row.iloc[6 + offset])) if len(row) > 6 + offset else "0",
            "color":         str(row.iloc[7 + offset]).strip() if len(row) > 7 + offset and pd.notna(row.iloc[7 + offset]) else "",
            "brand":         str(row.iloc[8 + offset]).strip() if len(row) > 8 + offset and pd.notna(row.iloc[8 + offset]) else "",
            "boxes":         _safe_int(row.iloc[10 + offset]) if len(row) > 10 + offset else 0,
            "pairs":         _safe_int(row.iloc[11 + offset]) if len(row) > 11 + offset else 0,
            "unit_fob":      _safe_float(row.iloc[12 + offset]) if len(row) > 12 + offset else 0.0,
            "amount_fob":    _safe_float(row.iloc[13 + offset]) if len(row) > 13 + offset else 0.0,
            "grade_range":   grade_range,
            "grades_json":   grades_json,
        })

    if not rows:
        return pd.DataFrame(), 0, "No se encontraron artículos en la proforma."

    df_result = pd.DataFrame(rows)
    total_pares = int(df_result["pairs"].sum())
    return df_result, total_pares, None


# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULO FOB AJUSTADO
# ─────────────────────────────────────────────────────────────────────────────

def _calcular_fob_ajustado(fob: float, d1: float, d2: float, d3: float, d4: float) -> float:
    """Aplica descuentos comerciales escalados al precio FOB unitario."""
    result = fob
    for d in (d1, d2, d3, d4):
        if d and d > 0:
            result *= (1 - float(d) / 100)
    return round(result, 4)


# ─────────────────────────────────────────────────────────────────────────────
# CREACIÓN DE PP CON STOCK EN TRÁNSITO
# ─────────────────────────────────────────────────────────────────────────────

def crear_pp_con_proforma(
    proforma: str,
    fecha_eta: date | None,
    descuento_1: float,
    descuento_2: float,
    descuento_3: float,
    descuento_4: float,
    detalle_rows: list[dict],
    proveedor_id: int = 654,  # Beira Rio
    usuario_id: int | None = None,
) -> tuple[bool, str, int | None]:
    """
    Crea un PP nuevo con el detalle de la proforma.
    
    Garantiza los 5 Pilares en cada SKU:
      - Linea (codigo_proveedor de linea_cod)
      - Referencia (codigo_proveedor de ref_cod)
      - Material (codigo_proveedor de material_code)
      - Color (codigo_proveedor de color_code)
      - Tallas (grades_json con distribución)
    
    El PP queda listo para recibir reservas (FI con nomenclatura [PP_ID]-PV001).
    
    Retorna: (ok, mensaje, pp_id)
    """
    anio = date.today().year
    nro_pp = _get_next_nro_pp(anio)
    total_pares = sum(int(r.get("pairs", 0)) for r in detalle_rows)
    total_fob = round(sum(float(r.get("amount_fob", 0)) for r in detalle_rows), 2)

    try:
        with engine.begin() as conn:
            # ── Crear cabecera PP ─────────────────────────────────────────────
            row = conn.execute(sqlt("""
                INSERT INTO pedido_proveedor (
                    numero_registro, anio_fiscal, estado,
                    proveedor_importacion_id, numero_proforma,
                    descuento_1, descuento_2, descuento_3, descuento_4,
                    fecha_arribo_estimada, pares_comprometidos,
                    fecha_pedido, estado_arribo
                ) VALUES (
                    :nro, :anio, 'ABIERTO',
                    :prov, :proforma,
                    :d1, :d2, :d3, :d4,
                    :eta, :pares,
                    CURRENT_DATE, 'EN_TRANSITO'
                )
                RETURNING id
            """), {
                "nro": nro_pp,
                "anio": anio,
                "prov": proveedor_id,
                "proforma": proforma.strip() or None,
                "d1": descuento_1,
                "d2": descuento_2,
                "d3": descuento_3,
                "d4": descuento_4,
                "eta": fecha_eta or None,
                "pares": total_pares,
            })
            pp_id = int(row.fetchone()[0])

            # ── Lookup de marcas ──────────────────────────────────────────────
            marc_rows = conn.execute(sqlt(
                "SELECT id_marca, UPPER(descp_marca) AS nom FROM marca_v2"
            )).fetchall()
            marca_lookup: dict[str, int] = {r.nom: int(r.id_marca) for r in marc_rows if r.nom}

            # ── Lookup material ───────────────────────────────────────────────
            mat_rows = conn.execute(sqlt(
                "SELECT id, codigo_proveedor::text, descripcion FROM material WHERE proveedor_id = :prov"
            ), {"prov": proveedor_id}).fetchall()
            mat_lookup: dict[str, tuple] = {r[1]: (int(r[0]), str(r[2] or "")) for r in mat_rows}

            # ── Lookup color ──────────────────────────────────────────────────
            col_rows = conn.execute(sqlt(
                "SELECT id, codigo_proveedor::text, nombre FROM color WHERE proveedor_id = :prov"
            ), {"prov": proveedor_id}).fetchall()
            col_lookup: dict[str, tuple] = {r[1]: (int(r[0]), str(r[2] or "")) for r in col_rows}

            # ── Insertar cada SKU con los 5 Pilares ───────────────────────────
            skus_insertados = 0
            for r in detalle_rows:
                fob_unit = float(r.get("unit_fob", 0))
                fob_aj = _calcular_fob_ajustado(fob_unit, descuento_1, descuento_2, descuento_3, descuento_4)
                grades = r.get("grades_json", {})
                brand_key = r.get("brand", "").strip().upper()
                id_marca = marca_lookup.get(brand_key)
                grada_val = r.get("grade_range", "") or ""
                mat_code_s = str(r.get("material_code", "") or "").strip()
                col_code_s = str(r.get("color_code", "") or "").strip()
                mat_hit = mat_lookup.get(mat_code_s)
                col_hit = col_lookup.get(col_code_s)
                id_mat = mat_hit[0] if mat_hit else None
                descp_mat = mat_hit[1] if mat_hit else (r.get("material", "") or "")
                id_col = col_hit[0] if col_hit else None
                descp_col = col_hit[1] if col_hit else (r.get("color", "") or "")

                # Extraer tallas t33-t40 del grades_json
                t33 = grades.get("33", 0)
                t34 = grades.get("34", 0)
                t35 = grades.get("35", 0)
                t36 = grades.get("36", 0)
                t37 = grades.get("37", 0)
                t38 = grades.get("38", 0)
                t39 = grades.get("39", 0)
                t40 = grades.get("40", 0)

                conn.execute(sqlt("""
                    INSERT INTO pedido_proveedor_detalle (
                        pedido_proveedor_id, cantidad,
                        id_marca, ncm, style_code,
                        linea, referencia,
                        nombre,
                        id_material, descp_material, material_code,
                        id_color, descp_color, color_code,
                        grada,
                        t33, t34, t35, t36, t37, t38, t39, t40,
                        cantidad_cajas, cantidad_pares,
                        unit_fob, unit_fob_ajustado,
                        amount_fob, grades_json,
                        fila_origen_f9, pares_vendidos
                    ) VALUES (
                        :pp_id, :pairs,
                        :id_marca, :ncm, :style,
                        :linea, :ref,
                        :nombre,
                        :id_mat, :mat, :mat_code,
                        :id_col, :col, :col_code,
                        :grada,
                        :t33, :t34, :t35, :t36, :t37, :t38, :t39, :t40,
                        :boxes, :pairs,
                        :ufob, :ufob_aj,
                        :afob, CAST(:grades AS jsonb),
                        :fila, 0
                    )
                """), {
                    "pp_id": pp_id,
                    "id_marca": id_marca,
                    "ncm": r.get("ncm", "") or "",
                    "style": r.get("style_code", "") or "",
                    "linea": r.get("linea_cod", "") or "",
                    "ref": r.get("ref_cod", "") or "",
                    "nombre": r.get("name", "") or "",
                    "id_mat": id_mat,
                    "mat": descp_mat,
                    "mat_code": mat_code_s,
                    "id_col": id_col,
                    "col": descp_col,
                    "col_code": col_code_s,
                    "grada": grada_val,
                    "t33": t33, "t34": t34, "t35": t35, "t36": t36,
                    "t37": t37, "t38": t38, "t39": t39, "t40": t40,
                    "boxes": int(r.get("boxes", 0)),
                    "pairs": int(r.get("pairs", 0)),
                    "ufob": fob_unit,
                    "ufob_aj": fob_aj,
                    "afob": float(r.get("amount_fob", 0)),
                    "grades": json.dumps(grades, ensure_ascii=False),
                    "fila": int(r.get("item", 0)),
                })
                skus_insertados += 1

        # ── Auditoría ─────────────────────────────────────────────────────────
        log_flujo(
            entidad="PP", entidad_id=pp_id, nro_registro=nro_pp,
            accion=A.PP_F9_CARGADO,
            estado_despues="EN_TRANSITO",
            snap={
                "proforma": proforma.strip(),
                "proveedor_id": proveedor_id,
                "total_pares": total_pares,
                "total_fob_usd": total_fob,
                "n_skus": skus_insertados,
                "descuento_1": descuento_1,
                "descuento_2": descuento_2,
                "descuento_3": descuento_3,
                "descuento_4": descuento_4,
                "fecha_eta": str(fecha_eta) if fecha_eta else None,
            },
            usuario_id=usuario_id,
        )
        
        msg = f"PP {nro_pp} creado: {skus_insertados} SKUs · {total_pares:,} pares · USD {total_fob:,.2f}"
        DBInspector.log(f"[CARGA_TRANSITO] {msg}", "SUCCESS")
        return True, msg, pp_id

    except Exception as e:
        DBInspector.log(f"[CARGA_TRANSITO] Error creando PP: {e}", "ERROR")
        return False, f"Error: {e}", None


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTAS
# ─────────────────────────────────────────────────────────────────────────────

def get_pps_en_transito() -> pd.DataFrame:
    """Retorna los PPs en tránsito listos para recibir reservas."""
    return get_dataframe("""
        SELECT
            pp.id,
            pp.numero_registro AS nro_pp,
            pp.numero_proforma AS proforma,
            pi2.nombre AS proveedor,
            pp.fecha_arribo_estimada AS eta,
            pp.pares_comprometidos AS total_pares,
            COALESCE(SUM(ppd.pares_vendidos), 0) AS pares_reservados,
            pp.pares_comprometidos - COALESCE(SUM(ppd.pares_vendidos), 0) AS saldo_disponible,
            COUNT(DISTINCT ppd.id) AS n_skus,
            COUNT(DISTINCT fi.id) AS n_facturas
        FROM pedido_proveedor pp
        LEFT JOIN proveedor_importacion pi2 ON pi2.id = pp.proveedor_importacion_id
        LEFT JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
        LEFT JOIN factura_interna fi ON fi.pp_id = pp.id
        WHERE pp.estado = 'ABIERTO'
          AND pp.estado_arribo = 'EN_TRANSITO'
        GROUP BY pp.id, pp.numero_registro, pp.numero_proforma, pi2.nombre,
                 pp.fecha_arribo_estimada, pp.pares_comprometidos
        ORDER BY pp.fecha_arribo_estimada ASC NULLS LAST, pp.numero_registro
    """)


def get_detalle_pp(pp_id: int) -> pd.DataFrame:
    """Detalle de SKUs de un PP con los 5 Pilares y saldo."""
    return get_dataframe("""
        SELECT
            ppd.id,
            COALESCE(mv.descp_marca, '—') AS marca,
            ppd.linea,
            ppd.referencia,
            ppd.descp_material AS material,
            ppd.descp_color AS color,
            ppd.grada,
            ppd.cantidad_cajas AS cajas,
            ppd.cantidad_pares AS pares_inicial,
            COALESCE(ppd.pares_vendidos, 0) AS reservados,
            ppd.cantidad_pares - COALESCE(ppd.pares_vendidos, 0) AS saldo,
            ppd.unit_fob,
            ppd.unit_fob_ajustado
        FROM pedido_proveedor_detalle ppd
        LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
        WHERE ppd.pedido_proveedor_id = :pp_id
        ORDER BY ppd.linea, ppd.referencia
    """, {"pp_id": pp_id})


def get_resumen_5_pilares(pp_id: int) -> dict:
    """Resumen de los 5 Pilares de un PP."""
    df = get_dataframe("""
        SELECT
            COUNT(DISTINCT ppd.linea) AS n_lineas,
            COUNT(DISTINCT ppd.referencia) AS n_referencias,
            COUNT(DISTINCT ppd.material_code) AS n_materiales,
            COUNT(DISTINCT ppd.color_code) AS n_colores,
            COUNT(DISTINCT ppd.grada) AS n_gradas,
            COUNT(*) AS n_skus,
            SUM(ppd.cantidad_pares) AS total_pares,
            SUM(ppd.cantidad_cajas) AS total_cajas
        FROM pedido_proveedor_detalle ppd
        WHERE ppd.pedido_proveedor_id = :pp_id
    """, {"pp_id": pp_id})
    
    if df is None or df.empty:
        return {}
    
    row = df.iloc[0]
    return {
        "lineas": int(row["n_lineas"] or 0),
        "referencias": int(row["n_referencias"] or 0),
        "materiales": int(row["n_materiales"] or 0),
        "colores": int(row["n_colores"] or 0),
        "gradas": int(row["n_gradas"] or 0),
        "skus": int(row["n_skus"] or 0),
        "pares": int(row["total_pares"] or 0),
        "cajas": int(row["total_cajas"] or 0),
    }