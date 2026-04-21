# =============================================================================
# MÓDULO: Pedido Proveedor
# ARCHIVO: modules/pedido_proveedor/logic.py
# DESCRIPCIÓN: Capa de datos del módulo.
#
#  Arquitectura Doble Ala:
#    Padre   → get_pp_header(id_pp)          cabecera del PP
#    Ala Norte → get_pp_ala_norte(id_pp)     artículos F9 con saldo disponible
#    Ala Sur   → get_ventas_transito(id_pp)  ventas registradas en tránsito
#
#  Flujo creación (formulario):
#    1. get_intenciones_con_saldo()  → ICs disponibles
#    2. get_ic_saldo(id_ic)          → balance de IC específica
#    3. parse_f9(file, proforma, marca) → extrae filas del F9
#    4. save_pp(header, detalle)     → INSERT PP + detalle + UPDATE IC estado
# =============================================================================

import io
import math
import pandas as pd
from datetime import date
from sqlalchemy import text as sqlt

from core.database import get_dataframe, engine


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _safe_int(val) -> int:
    """Convierte cualquier valor del F9 a entero. Tolerante a NaN y strings."""
    if val is None:
        return 0
    if isinstance(val, float):
        return 0 if math.isnan(val) else int(val)
    if isinstance(val, int):
        return val
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", ""):
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _find_col(df: pd.DataFrame, *candidates: str):
    """Retorna el primer nombre de columna que existe en el DataFrame."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ─────────────────────────────────────────────────────────────────────────────
# NUMERACIÓN PP-YYYY-XXXX
# ─────────────────────────────────────────────────────────────────────────────

def get_next_numero_pp(anio: int | None = None) -> str:
    """
    Genera el próximo PP-YYYY-XXXX consultando el máximo en BD.
    Solo cuenta registros NEXUS (PP-YYYY-XXXX), no los legados (PP-3936, etc.).
    """
    if anio is None:
        anio = date.today().year
    df = get_dataframe(
        """
        SELECT COALESCE(
            MAX(CAST(SPLIT_PART(numero_registro, '-', 3) AS INTEGER)), 0
        ) AS ultimo
        FROM pedido_proveedor
        WHERE numero_registro ~ '^PP-[0-9]{4}-[0-9]+$'
          AND numero_registro LIKE :patron
        """,
        {"patron": f"PP-{anio}-%"},
    )
    ultimo = int(df["ultimo"].iloc[0]) if not df.empty else 0
    return f"PP-{anio}-{ultimo + 1:04d}"


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTAS DE INTENCIONES DE COMPRA (para el formulario de creación)
# ─────────────────────────────────────────────────────────────────────────────

def get_intenciones_con_saldo() -> pd.DataFrame:
    """ICs con saldo de pares disponible para comprometer."""
    return get_dataframe("""
        SELECT
            ic.id,
            ic.numero_registro,
            ic.id_marca,
            ic.id_proveedor,
            mv.descp_marca                          AS marca,
            pi2.nombre                              AS proveedor,
            ic.cantidad_total_pares                 AS pares_aprobados,
            ic.fecha_llegada                        AS fecha_eta,
            COALESCE(SUM(pp.pares_comprometidos), 0) AS comprometidos,
            ic.cantidad_total_pares
                - COALESCE(SUM(pp.pares_comprometidos), 0) AS saldo
        FROM intencion_compra ic
        JOIN marca_v2              mv  ON mv.id_marca  = ic.id_marca
        JOIN proveedor_importacion pi2 ON pi2.id       = ic.id_proveedor
        LEFT JOIN pedido_proveedor pp
               ON pp.id_intencion_compra = ic.id
              AND pp.estado NOT IN ('ANULADO')
        WHERE ic.estado != 'CERRADO'
        GROUP BY ic.id, ic.numero_registro, ic.id_marca, ic.id_proveedor,
                 mv.descp_marca, pi2.nombre,
                 ic.cantidad_total_pares, ic.fecha_llegada
        HAVING ic.cantidad_total_pares
                 - COALESCE(SUM(pp.pares_comprometidos), 0) > 0
        ORDER BY ic.fecha_llegada ASC NULLS LAST, ic.numero_registro
    """)


def get_ic_saldo(id_ic: int) -> dict:
    """Balance completo de una IC específica."""
    df = get_dataframe("""
        SELECT
            ic.id,
            ic.numero_registro,
            ic.id_marca,
            ic.id_proveedor,
            mv.descp_marca                          AS marca,
            pi2.nombre                              AS proveedor,
            ic.cantidad_total_pares                 AS aprobados,
            ic.fecha_llegada                        AS fecha_eta,
            COALESCE(SUM(pp.pares_comprometidos), 0) AS comprometidos
        FROM intencion_compra ic
        JOIN marca_v2              mv  ON mv.id_marca  = ic.id_marca
        JOIN proveedor_importacion pi2 ON pi2.id       = ic.id_proveedor
        LEFT JOIN pedido_proveedor pp
               ON pp.id_intencion_compra = ic.id
              AND pp.estado NOT IN ('ANULADO')
        WHERE ic.id = :id_ic
        GROUP BY ic.id, ic.numero_registro, ic.id_marca, ic.id_proveedor,
                 mv.descp_marca, pi2.nombre, ic.cantidad_total_pares, ic.fecha_llegada
    """, {"id_ic": id_ic})

    if df.empty:
        return {}

    row = df.iloc[0]
    aprobados     = int(row["aprobados"])
    comprometidos = int(row["comprometidos"])
    return {
        "id":              int(row["id"]),
        "numero_registro": str(row["numero_registro"]),
        "id_marca":        int(row["id_marca"]),
        "id_proveedor":    int(row["id_proveedor"]),
        "marca":           str(row["marca"]),
        "proveedor":       str(row["proveedor"]),
        "aprobados":       aprobados,
        "comprometidos":   comprometidos,
        "saldo":           aprobados - comprometidos,
        "fecha_eta":       row["fecha_eta"] if pd.notna(row["fecha_eta"]) else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LISTA DE PEDIDOS PROVEEDOR
# ─────────────────────────────────────────────────────────────────────────────

def get_pedidos_proveedor(filtros: dict | None = None) -> pd.DataFrame:
    """
    Lista de todos los PP NEXUS (estado IN 'ABIERTO'/'CERRADO'/'ANULADO').
    Incluye multi-marca PPs donde id_intencion_compra puede ser NULL.
    Las marcas se derivan del detalle para cubrir ambos casos.
    """
    where_clauses = ["pp.estado IN ('ABIERTO', 'CERRADO', 'ANULADO', 'ENVIADO')"]
    params: dict = {}

    if filtros:
        if filtros.get("estado") and filtros["estado"] != "TODOS":
            where_clauses.append("pp.estado = :estado")
            params["estado"] = filtros["estado"]
        if filtros.get("marca"):
            where_clauses.append("""
                EXISTS (
                    SELECT 1 FROM pedido_proveedor_detalle ppd2
                    JOIN marca_v2 mv2 ON mv2.id_marca = ppd2.id_marca
                    WHERE ppd2.pedido_proveedor_id = pp.id
                      AND mv2.descp_marca = :marca_filtro
                )
            """)
            params["marca_filtro"] = filtros["marca"]

    where = " AND ".join(where_clauses)

    return get_dataframe(f"""
        SELECT
            pp.id,
            pp.numero_registro,
            pp.numero_proforma,
            pp.pares_comprometidos,
            pp.estado,
            pp.fecha_pedido,
            pp.fecha_arribo_estimada                                  AS fecha_eta,
            pp.fecha_arribo_real,
            COALESCE(pi2.nombre, '—')                                 AS proveedor,
            COALESCE(ic.numero_registro, '—')                         AS ic_nro,
            COALESCE(
                (SELECT STRING_AGG(DISTINCT mv2.descp_marca, ' / '
                                   ORDER BY mv2.descp_marca)
                 FROM pedido_proveedor_detalle ppd2
                 JOIN marca_v2 mv2 ON mv2.id_marca = ppd2.id_marca
                 WHERE ppd2.pedido_proveedor_id = pp.id
                   AND ppd2.linea IS NOT NULL),
                '—'
            )                                                         AS marcas,
            COALESCE(
                (SELECT SUM(vt2.cantidad_vendida)
                 FROM venta_transito vt2
                 WHERE vt2.pedido_proveedor_id = pp.id),
                0
            )                                                         AS total_vendido
        FROM pedido_proveedor pp
        LEFT JOIN proveedor_importacion pi2 ON pi2.id = pp.proveedor_importacion_id
        LEFT JOIN intencion_compra      ic  ON ic.id  = pp.id_intencion_compra
        WHERE {where}
        ORDER BY pp.numero_registro ASC
    """, params or None)


# ─────────────────────────────────────────────────────────────────────────────
# CABECERA (PADRE) — vista de detalle
# ─────────────────────────────────────────────────────────────────────────────

def get_pp_header(id_pp: int) -> dict:
    """
    Cabecera completa de un PP para la vista master-detail.
    Incluye: id, numero_registro, proforma, proveedor, marcas, estado,
             fechas, totales (artículos, pares, vendido, saldo), ic vinculada.
    """
    # Subconsultas correlacionadas para total_articulos, total_vendido y marcas.
    # Motivo: JOIN simultáneo a ppd (N filas) y vt (M filas) genera producto cartesiano
    # N×M, inflando SUM(vt.cantidad_vendida) por el factor N. Bug crítico.
    df = get_dataframe("""
        SELECT
            pp.id,
            pp.numero_registro,
            pp.numero_proforma,
            pp.pares_comprometidos              AS total_pares,
            pp.estado,
            pp.fecha_pedido,
            pp.fecha_arribo_estimada            AS fecha_promesa,
            pp.fecha_arribo_real,
            pp.notas,
            COALESCE(pi2.nombre, '—')           AS proveedor,
            COALESCE(ic.numero_registro, '—')   AS ic_nro,
            COALESCE(
                (SELECT STRING_AGG(DISTINCT mv2.descp_marca, ' / '
                                   ORDER BY mv2.descp_marca)
                 FROM pedido_proveedor_detalle ppd2
                 JOIN marca_v2 mv2 ON mv2.id_marca = ppd2.id_marca
                 WHERE ppd2.pedido_proveedor_id = pp.id
                   AND ppd2.linea IS NOT NULL),
                '—'
            )                                   AS marcas,
            (SELECT COUNT(*)
             FROM pedido_proveedor_detalle ppd2
             WHERE ppd2.pedido_proveedor_id = pp.id
               AND ppd2.linea IS NOT NULL)      AS total_articulos,
            COALESCE(
                (SELECT SUM(vt2.cantidad_vendida)
                 FROM venta_transito vt2
                 WHERE vt2.pedido_proveedor_id = pp.id),
                0
            )                                   AS total_vendido
        FROM pedido_proveedor pp
        LEFT JOIN proveedor_importacion pi2 ON pi2.id = pp.proveedor_importacion_id
        LEFT JOIN intencion_compra       ic  ON ic.id  = pp.id_intencion_compra
        WHERE pp.id = :id_pp
    """, {"id_pp": id_pp})

    if df.empty:
        return {}

    row           = df.iloc[0]
    total_pares   = int(row["total_pares"]   or 0)
    total_vendido = int(row["total_vendido"] or 0)
    return {
        "id":               int(row["id"]),
        "numero_registro":  str(row["numero_registro"]),
        "numero_proforma":  str(row["numero_proforma"] or "—"),
        "total_pares":      total_pares,
        "estado":           str(row["estado"]),
        "fecha_pedido":     row["fecha_pedido"],
        "fecha_promesa":    row["fecha_promesa"],
        "fecha_arribo_real": row["fecha_arribo_real"],
        "notas":            str(row["notas"] or ""),
        "proveedor":        str(row["proveedor"]),
        "ic_nro":           str(row["ic_nro"]),
        "marcas":           str(row["marcas"]),
        "total_articulos":  int(row["total_articulos"] or 0),
        "total_vendido":    total_vendido,
        "saldo":            total_pares - total_vendido,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ALA NORTE — artículos del F9 con saldo disponible
# ─────────────────────────────────────────────────────────────────────────────

def get_pp_ala_norte(id_pp: int) -> pd.DataFrame:
    """
    Retorna los artículos del F9 para un PP con cálculo en tiempo real de
    vendido (SUM venta_transito) y saldo disponible por SKU.

    Columnas: id, marca, linea, referencia, material, color, grada,
              t33-t40, cantidad_inicial, vendido, saldo
    """
    return get_dataframe("""
        SELECT
            ppd.id,
            COALESCE(mv.descp_marca, '—')                               AS marca,
            ppd.linea,
            ppd.referencia,
            ppd.descp_material                                           AS material,
            ppd.descp_color                                              AS color,
            ppd.grada,
            ppd.t33, ppd.t34, ppd.t35, ppd.t36,
            ppd.t37, ppd.t38, ppd.t39, ppd.t40,
            ppd.cantidad_pares                                           AS cantidad_inicial,
            COALESCE(SUM(vt.cantidad_vendida), 0)                       AS vendido,
            ppd.cantidad_pares - COALESCE(SUM(vt.cantidad_vendida), 0)  AS saldo
        FROM pedido_proveedor_detalle ppd
        LEFT JOIN marca_v2       mv ON mv.id_marca = ppd.id_marca
        LEFT JOIN venta_transito vt ON vt.pedido_proveedor_detalle_id = ppd.id
        WHERE ppd.pedido_proveedor_id = :id_pp
          AND ppd.linea IS NOT NULL
        GROUP BY ppd.id, mv.descp_marca, ppd.linea, ppd.referencia,
                 ppd.descp_material, ppd.descp_color, ppd.grada,
                 ppd.t33, ppd.t34, ppd.t35, ppd.t36,
                 ppd.t37, ppd.t38, ppd.t39, ppd.t40, ppd.cantidad_pares
        ORDER BY ppd.id
    """, {"id_pp": id_pp})


# ─────────────────────────────────────────────────────────────────────────────
# SHOWROOM — quincenas, catálogo visual y escritura de ventas
# ─────────────────────────────────────────────────────────────────────────────

def get_quincenas_disponibles() -> list[dict]:
    """
    Retorna las quincenas de arribo de los PPs ABIERTOS, ordenadas cronológicamente.
    Cada dict: { label, anio, mes, quincena, fecha_ini, fecha_fin }
    """
    import calendar
    from datetime import date as _date
    from core.constants import MES_NOMBRES

    df = get_dataframe("""
        SELECT DISTINCT
            EXTRACT(YEAR  FROM fecha_arribo_estimada)::INT AS anio,
            EXTRACT(MONTH FROM fecha_arribo_estimada)::INT AS mes,
            CASE WHEN EXTRACT(DAY FROM fecha_arribo_estimada) <= 15
                 THEN 1 ELSE 2 END                        AS quincena
        FROM pedido_proveedor
        WHERE estado = 'ABIERTO'
          AND fecha_arribo_estimada IS NOT NULL
        ORDER BY anio, mes, quincena
    """)

    result = []
    for _, row in df.iterrows():
        anio = int(row["anio"])
        mes  = int(row["mes"])
        q    = int(row["quincena"])
        mes_nombre = MES_NOMBRES.get(mes, str(mes))
        q_str      = "1ª" if q == 1 else "2ª"
        label      = f"{q_str} Quincena de {mes_nombre} {anio}"

        if q == 1:
            fecha_ini = _date(anio, mes, 1)
            fecha_fin = _date(anio, mes, 15)
        else:
            ultimo    = calendar.monthrange(anio, mes)[1]
            fecha_ini = _date(anio, mes, 16)
            fecha_fin = _date(anio, mes, ultimo)

        result.append({
            "label":     label,
            "anio":      anio,
            "mes":       mes,
            "quincena":  q,
            "fecha_ini": fecha_ini,
            "fecha_fin": fecha_fin,
        })

    return result


def get_showroom_skus(fecha_ini, fecha_fin) -> pd.DataFrame:
    """
    Retorna todos los SKUs del F9 para PPs con ETA en el rango [fecha_ini, fecha_fin],
    estado ABIERTO, con saldo disponible calculado en tiempo real desde venta_transito.

    Columnas clave:
        id, id_pp, pp_nro, marca, linea, referencia,
        id_material, material, id_color, color, grada,
        cantidad_cajas, t33-t40, cantidad_inicial, vendido, saldo
    """
    return get_dataframe("""
        SELECT
            ppd.id,
            pp.id                                                        AS id_pp,
            pp.numero_registro                                           AS pp_nro,
            pp.fecha_arribo_estimada                                     AS fecha_eta,
            COALESCE(mv.descp_marca, '—')                               AS marca,
            ppd.linea,
            ppd.referencia,
            ppd.id_material,
            ppd.descp_material                                           AS material,
            ppd.id_color,
            ppd.descp_color                                              AS color,
            ppd.grada,
            ppd.cantidad_cajas,
            ppd.t33, ppd.t34, ppd.t35, ppd.t36,
            ppd.t37, ppd.t38, ppd.t39, ppd.t40,
            ppd.cantidad_pares                                           AS cantidad_inicial,
            COALESCE(SUM(vt.cantidad_vendida), 0)                       AS vendido,
            ppd.cantidad_pares - COALESCE(SUM(vt.cantidad_vendida), 0)  AS saldo
        FROM pedido_proveedor_detalle ppd
        JOIN  pedido_proveedor pp  ON pp.id          = ppd.pedido_proveedor_id
        LEFT JOIN marca_v2    mv   ON mv.id_marca    = ppd.id_marca
        LEFT JOIN venta_transito vt ON vt.pedido_proveedor_detalle_id = ppd.id
        WHERE pp.fecha_arribo_estimada BETWEEN :fecha_ini AND :fecha_fin
          AND pp.estado      = 'ABIERTO'
          AND ppd.linea      IS NOT NULL
        GROUP BY ppd.id, pp.id, pp.numero_registro, pp.fecha_arribo_estimada,
                 mv.descp_marca, ppd.linea, ppd.referencia,
                 ppd.id_material, ppd.descp_material,
                 ppd.id_color,   ppd.descp_color,
                 ppd.grada, ppd.cantidad_cajas,
                 ppd.t33, ppd.t34, ppd.t35, ppd.t36,
                 ppd.t37, ppd.t38, ppd.t39, ppd.t40, ppd.cantidad_pares
        ORDER BY mv.descp_marca, ppd.linea, ppd.referencia
    """, {"fecha_ini": str(fecha_ini), "fecha_fin": str(fecha_fin)})


def save_venta_caja(
    id_detalle:    int,
    id_pp:         int,
    n_cajas:       int,
    sku:           dict,
    codigo_cliente: str,
    id_vendedor:   int | None = None,
    numero_factura_interna: str | None = None,
) -> tuple[bool, str]:
    """
    Registra la venta de N cajas de un SKU en tránsito.
    Calcula la distribución por talla proporcionalmente al F9.
    Precio = 0 (valorización diferida al módulo administrativo).

    Returns: (True, descripción) | (False, mensaje_error)
    """
    cajas_f9         = max(int(sku.get("cantidad_cajas") or 1), 1)
    cantidad_inicial = max(int(sku.get("cantidad_inicial") or 0), 0)
    pares_por_caja   = max(math.ceil(cantidad_inicial / cajas_f9), 1)
    pares_a_vender   = pares_por_caja * n_cajas

    # Pesos de distribución proporcional (valores t33-t40 del F9)
    pesos = {f"t{t}": max(int(sku.get(f"t{t}", 0) or 0), 0) for t in range(33, 41)}
    base_total = sum(pesos.values())

    if base_total == 0:
        return False, "La caja no tiene distribución de tallas válida en el F9."

    # Distribuir pares_a_vender proporcionalmente; el residuo va a la talla mayor
    tallas: dict[str, int] = {}
    asignado = 0
    sorted_cols = sorted(pesos.keys(), key=lambda c: pesos[c], reverse=True)
    for i, col in enumerate(sorted_cols):
        if i == len(sorted_cols) - 1:
            qty = max(pares_a_vender - asignado, 0)
        else:
            qty = round(pares_a_vender * pesos[col] / base_total)
            qty = min(qty, max(pares_a_vender - asignado, 0))
        tallas[col] = max(qty, 0)
        asignado += qty

    total_vendido = sum(tallas.values())

    if total_vendido == 0:
        return False, "La caja no tiene distribución de tallas válida en el F9."

    saldo_actual = int(sku.get("saldo", 0) or 0)
    if total_vendido > saldo_actual:
        return False, (
            f"Stock insuficiente: intentás vender {total_vendido} pares "
            f"pero el saldo disponible es {saldo_actual}."
        )

    try:
        with engine.begin() as conn:
            conn.execute(sqlt("""
                INSERT INTO venta_transito (
                    pedido_proveedor_id,
                    pedido_proveedor_detalle_id,
                    codigo_cliente, id_vendedor,
                    fecha_operacion,
                    t33, t34, t35, t36, t37, t38, t39, t40,
                    cantidad_vendida,
                    numero_factura_interna
                ) VALUES (
                    :pp_id, :det_id,
                    :cliente, :vendedor,
                    CURRENT_DATE,
                    :t33, :t34, :t35, :t36, :t37, :t38, :t39, :t40,
                    :total, :factura
                )
            """), {
                "pp_id":   id_pp,
                "det_id":  id_detalle,
                "cliente": str(codigo_cliente).strip(),
                "vendedor": int(id_vendedor) if id_vendedor else None,
                **{k: int(v) for k, v in tallas.items()},
                "total":   total_vendido,
                "factura": numero_factura_interna,
            })
        return True, f"{n_cajas} caja(s) — {total_vendido} pares"
    except Exception as e:
        return False, f"Error al registrar: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# ALA SUR — ventas en tránsito registradas
# ─────────────────────────────────────────────────────────────────────────────

def get_marcas_por_quincena(fecha_ini, fecha_fin) -> pd.DataFrame:
    """
    Retorna las marcas que tienen artículos con saldo > 0 en el rango de fechas.
    Usado en el Paso 2 del embudo Showroom.
    """
    return get_dataframe("""
        SELECT
            mv.id_marca,
            mv.descp_marca,
            COUNT(DISTINCT ppd.id)                                      AS articulos,
            SUM(ppd.cantidad_pares) - COALESCE(SUM(vt.cantidad_vendida), 0) AS saldo_total
        FROM pedido_proveedor_detalle ppd
        JOIN  pedido_proveedor pp ON pp.id         = ppd.pedido_proveedor_id
        JOIN  marca_v2        mv  ON mv.id_marca   = ppd.id_marca
        LEFT JOIN venta_transito vt ON vt.pedido_proveedor_detalle_id = ppd.id
        WHERE pp.fecha_arribo_estimada BETWEEN :fecha_ini AND :fecha_fin
          AND pp.estado    = 'ABIERTO'
          AND ppd.linea    IS NOT NULL
        GROUP BY mv.id_marca, mv.descp_marca
        HAVING SUM(ppd.cantidad_pares) - COALESCE(SUM(vt.cantidad_vendida), 0) > 0
        ORDER BY mv.descp_marca
    """, {"fecha_ini": str(fecha_ini), "fecha_fin": str(fecha_fin)})


def get_catalog_visual(fecha_ini, fecha_fin, id_marcas: list[int]) -> pd.DataFrame:
    """
    Consulta pesada que se ejecuta solo cuando el usuario confirma quincena + marcas.
    Retorna SKUs del F9 con saldo, filtrados por marca. Incluye datos de imagen.
    """
    if not id_marcas:
        return pd.DataFrame()

    placeholders = ", ".join(f":m{i}" for i in range(len(id_marcas)))
    params: dict = {f"m{i}": v for i, v in enumerate(id_marcas)}
    params["fecha_ini"] = str(fecha_ini)
    params["fecha_fin"] = str(fecha_fin)

    return get_dataframe(f"""
        SELECT
            ppd.id,
            pp.id                                                        AS id_pp,
            pp.numero_registro                                           AS pp_nro,
            pp.numero_proforma,
            pp.fecha_arribo_estimada                                     AS fecha_eta,
            COALESCE(mv.descp_marca, '—')                               AS marca,
            ppd.linea,
            ppd.referencia,
            ppd.id_material,
            ppd.descp_material                                           AS material,
            ppd.id_color,
            ppd.descp_color                                              AS color,
            ppd.grada,
            ppd.cantidad_cajas,
            ppd.t33, ppd.t34, ppd.t35, ppd.t36,
            ppd.t37, ppd.t38, ppd.t39, ppd.t40,
            ppd.cantidad_pares                                           AS cantidad_inicial,
            COALESCE(SUM(vt.cantidad_vendida), 0)                       AS vendido,
            ppd.cantidad_pares - COALESCE(SUM(vt.cantidad_vendida), 0)  AS saldo
        FROM pedido_proveedor_detalle ppd
        JOIN  pedido_proveedor pp  ON pp.id          = ppd.pedido_proveedor_id
        LEFT JOIN marca_v2    mv   ON mv.id_marca    = ppd.id_marca
        LEFT JOIN venta_transito vt ON vt.pedido_proveedor_detalle_id = ppd.id
        WHERE pp.fecha_arribo_estimada BETWEEN :fecha_ini AND :fecha_fin
          AND pp.estado      = 'ABIERTO'
          AND ppd.linea      IS NOT NULL
          AND ppd.id_marca   IN ({placeholders})
        GROUP BY ppd.id, pp.id, pp.numero_registro, pp.fecha_arribo_estimada,
                 mv.descp_marca, ppd.linea, ppd.referencia,
                 ppd.id_material, ppd.descp_material,
                 ppd.id_color,   ppd.descp_color,
                 ppd.grada, ppd.cantidad_cajas,
                 ppd.t33, ppd.t34, ppd.t35, ppd.t36,
                 ppd.t37, ppd.t38, ppd.t39, ppd.t40, ppd.cantidad_pares
        ORDER BY mv.descp_marca, ppd.linea, ppd.referencia
    """, params)


def save_factura_interna(
    cart:           dict,           # {det_id (int): n_cajas (int)}
    codigo_cliente: str,
    id_vendedor:    int | None,
    catalog_df:     "pd.DataFrame",
) -> tuple[bool, str, dict]:
    """
    Genera una Factura Interna Provisoria con todos los ítems del carrito.
    Un único numero_factura_interna agrupa todos los renglones.

    Returns:
        (True,  numero_factura, {"articulos": N, "total_pares": M})
        (False, "",             {"error": "..."})
    """
    from datetime import datetime as _dt
    numero_factura = (
        f"FAC-INT-{str(codigo_cliente).strip()}"
        f"-{_dt.now().strftime('%y%m%d%H%M')}"
    )

    # Lookup rápido por id_ppd
    sku_map: dict[int, dict] = {}
    for _, row in catalog_df.iterrows():
        sku_map[int(row["id"])] = row.to_dict()

    total_pares = 0
    insertados  = 0

    try:
        with engine.begin() as conn:
            for det_id_raw, n_cajas in cart.items():
                n_cajas = int(n_cajas)
                if n_cajas <= 0:
                    continue
                sku = sku_map.get(int(det_id_raw))
                if sku is None:
                    continue

                cajas_f9 = max(int(sku.get("cantidad_cajas") or 1), 1)
                tallas: dict[str, int] = {}
                total_v = 0
                for t in range(33, 41):
                    col      = f"t{t}"
                    por_caja = round(int(sku.get(col, 0) or 0) / cajas_f9)
                    sold     = por_caja * n_cajas
                    tallas[col] = sold
                    total_v    += sold

                if total_v == 0:
                    continue

                conn.execute(sqlt("""
                    INSERT INTO venta_transito (
                        pedido_proveedor_id,
                        pedido_proveedor_detalle_id,
                        codigo_cliente, id_vendedor,
                        fecha_operacion,
                        t33, t34, t35, t36, t37, t38, t39, t40,
                        cantidad_vendida,
                        numero_factura_interna
                    ) VALUES (
                        :pp_id, :det_id,
                        :cliente, :vendedor,
                        CURRENT_DATE,
                        :t33, :t34, :t35, :t36, :t37, :t38, :t39, :t40,
                        :total, :factura
                    )
                """), {
                    "pp_id":   int(sku["id_pp"]),
                    "det_id":  int(det_id_raw),
                    "cliente": str(codigo_cliente).strip(),
                    "vendedor": int(id_vendedor) if id_vendedor else None,
                    **{k: int(v) for k, v in tallas.items()},
                    "total":   total_v,
                    "factura": numero_factura,
                })
                total_pares += total_v
                insertados  += 1

        return True, numero_factura, {"articulos": insertados, "total_pares": total_pares}

    except Exception as e:
        return False, "", {"error": str(e)}


def get_ventas_transito(id_pp: int) -> pd.DataFrame:
    """
    Retorna todas las ventas en tránsito de un PP con el SKU vinculado.
    """
    return get_dataframe("""
        SELECT
            vt.id,
            vt.fecha_operacion,
            vt.codigo_cliente,
            vt.plazo,
            ppd.linea,
            ppd.referencia,
            ppd.descp_material  AS material,
            ppd.descp_color     AS color,
            ppd.grada,
            vt.t33, vt.t34, vt.t35, vt.t36,
            vt.t37, vt.t38, vt.t39, vt.t40,
            vt.cantidad_vendida,
            vt.notas
        FROM venta_transito vt
        JOIN pedido_proveedor_detalle ppd ON ppd.id = vt.pedido_proveedor_detalle_id
        WHERE vt.pedido_proveedor_id = :id_pp
        ORDER BY vt.fecha_operacion DESC, vt.id DESC
    """, {"id_pp": id_pp})


def get_ala_sur_facturas(id_pp: int) -> pd.DataFrame:
    """
    Facturas Internas del PP con detalle a nivel SKU (5 Pilares + Tallas).
    Columnas: marca, factura, fecha, cod_cliente, cliente, vendedor,
              linea, referencia, material, color, grada, t33-t40, pares.
    """
    return get_dataframe("""
        SELECT
            COALESCE(mv.descp_marca, '—')                    AS marca,
            COALESCE(vt.numero_factura_interna, '—')         AS factura,
            MIN(vt.fecha_operacion)                          AS fecha,
            vt.codigo_cliente                                AS cod_cliente,
            COALESCE(cv.descp_cliente, vt.codigo_cliente)    AS cliente,
            COALESCE(vv.descp_vendedor, 'Sin asignar')       AS vendedor,
            ppd.linea,
            ppd.referencia,
            ppd.descp_material                               AS material,
            ppd.descp_color                                  AS color,
            ppd.grada,
            SUM(vt.t33) AS t33, SUM(vt.t34) AS t34,
            SUM(vt.t35) AS t35, SUM(vt.t36) AS t36,
            SUM(vt.t37) AS t37, SUM(vt.t38) AS t38,
            SUM(vt.t39) AS t39, SUM(vt.t40) AS t40,
            SUM(vt.cantidad_vendida)                         AS pares
        FROM venta_transito vt
        JOIN  pedido_proveedor_detalle ppd ON ppd.id           = vt.pedido_proveedor_detalle_id
        LEFT JOIN marca_v2    mv  ON mv.id_marca                = ppd.id_marca
        LEFT JOIN cliente_v2  cv  ON cv.id_cliente::text        = vt.codigo_cliente
        LEFT JOIN vendedor_v2 vv  ON vv.id_vendedor             = vt.id_vendedor
        WHERE vt.pedido_proveedor_id = :id_pp
        GROUP BY mv.descp_marca, vt.numero_factura_interna, vt.codigo_cliente,
                 cv.descp_cliente, vv.descp_vendedor,
                 ppd.linea, ppd.referencia, ppd.descp_material, ppd.descp_color, ppd.grada
        ORDER BY mv.descp_marca, vt.numero_factura_interna, ppd.linea, ppd.referencia
    """, {"id_pp": id_pp})


def get_auditoria_global() -> pd.DataFrame:
    """
    Resumen de ejecución por marca a través de todos los PPs NEXUS.
    Columnas: marca, num_pps, pares_f9, pares_facturados, saldo, pct_ejecucion
    """
    return get_dataframe("""
        SELECT
            COALESCE(mv.descp_marca, '—')              AS marca,
            COUNT(DISTINCT pp.id)                      AS num_pps,
            SUM(ppd.cantidad_pares)                    AS pares_f9,
            COALESCE(SUM(vt_agg.vendido), 0)           AS pares_facturados,
            SUM(ppd.cantidad_pares)
                - COALESCE(SUM(vt_agg.vendido), 0)     AS saldo,
            ROUND(
                COALESCE(SUM(vt_agg.vendido), 0)::numeric
                / NULLIF(SUM(ppd.cantidad_pares), 0) * 100, 1
            )                                          AS pct_ejecucion
        FROM pedido_proveedor_detalle ppd
        JOIN  pedido_proveedor pp  ON pp.id         = ppd.pedido_proveedor_id
        LEFT JOIN marca_v2     mv  ON mv.id_marca   = ppd.id_marca
        LEFT JOIN (
            SELECT pedido_proveedor_detalle_id, SUM(cantidad_vendida) AS vendido
            FROM venta_transito
            GROUP BY pedido_proveedor_detalle_id
        ) vt_agg ON vt_agg.pedido_proveedor_detalle_id = ppd.id
        WHERE pp.estado IN ('ABIERTO', 'CERRADO', 'ANULADO')
          AND ppd.linea IS NOT NULL
        GROUP BY mv.descp_marca
        ORDER BY pct_ejecucion DESC NULLS LAST
    """)


# ─────────────────────────────────────────────────────────────────────────────
# FACTURAS MANUALES — helpers para el formulario de creación en Ala Sur
# ─────────────────────────────────────────────────────────────────────────────

def get_plazos() -> pd.DataFrame:
    """Plazos de pago disponibles (tabla maestra plazo_v2)."""
    return get_dataframe("SELECT id_plazo, descp_plazo FROM plazo_v2 ORDER BY id_plazo")


def buscar_cliente_pp(id_cliente: int) -> str | None:
    """Retorna descp_cliente dado un id_cliente, o None si no existe."""
    df = get_dataframe(
        "SELECT descp_cliente FROM cliente_v2 WHERE id_cliente = :id",
        {"id": id_cliente},
    )
    if df.empty:
        return None
    return str(df["descp_cliente"].iloc[0])


def get_vendedores_pp() -> pd.DataFrame:
    """Lista de vendedores para el selectbox opcional de nueva factura."""
    return get_dataframe(
        "SELECT id_vendedor, descp_vendedor FROM vendedor_v2 ORDER BY descp_vendedor"
    )


def get_marcas_de_pp(id_pp: int) -> pd.DataFrame:
    """DISTINCT marcas presentes en un PP (para multiselect de nueva factura)."""
    return get_dataframe("""
        SELECT DISTINCT ppd.id_marca, mv.descp_marca
        FROM pedido_proveedor_detalle ppd
        JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
        WHERE ppd.pedido_proveedor_id = :id_pp
          AND ppd.linea IS NOT NULL
        ORDER BY mv.descp_marca
    """, {"id_pp": id_pp})


def get_skus_por_marcas(id_pp: int, id_marcas: list[int]) -> pd.DataFrame:
    """
    SKUs de un PP filtrados por marcas con saldo real disponible.
    Incluye cantidad_cajas para calcular pares_por_caja en Phase B.
    """
    if not id_marcas:
        return pd.DataFrame()

    placeholders = ", ".join(f":m{i}" for i in range(len(id_marcas)))
    params: dict = {f"m{i}": v for i, v in enumerate(id_marcas)}
    params["id_pp"] = id_pp

    return get_dataframe(f"""
        SELECT
            ppd.id,
            ppd.id_marca,
            COALESCE(mv.descp_marca, '—')                               AS marca,
            ppd.linea,
            ppd.referencia,
            ppd.descp_material                                           AS material,
            ppd.descp_color                                              AS color,
            ppd.grada,
            ppd.cantidad_cajas,
            ppd.t33, ppd.t34, ppd.t35, ppd.t36,
            ppd.t37, ppd.t38, ppd.t39, ppd.t40,
            ppd.cantidad_pares                                           AS cantidad_inicial,
            COALESCE(SUM(vt.cantidad_vendida), 0)                       AS vendido,
            ppd.cantidad_pares - COALESCE(SUM(vt.cantidad_vendida), 0)  AS saldo
        FROM pedido_proveedor_detalle ppd
        LEFT JOIN marca_v2      mv ON mv.id_marca  = ppd.id_marca
        LEFT JOIN venta_transito vt ON vt.pedido_proveedor_detalle_id = ppd.id
        WHERE ppd.pedido_proveedor_id = :id_pp
          AND ppd.id_marca IN ({placeholders})
          AND ppd.linea IS NOT NULL
        GROUP BY ppd.id, ppd.id_marca, mv.descp_marca, ppd.linea, ppd.referencia,
                 ppd.descp_material, ppd.descp_color, ppd.grada, ppd.cantidad_cajas,
                 ppd.t33, ppd.t34, ppd.t35, ppd.t36,
                 ppd.t37, ppd.t38, ppd.t39, ppd.t40, ppd.cantidad_pares
        ORDER BY mv.descp_marca, ppd.linea, ppd.referencia
    """, params)


def save_factura_manual(
    id_pp:       int,
    id_marca:    int,
    cod_cliente: str,
    id_plazo:    int,
    id_vendedor: int | None,
    items:       list[dict],   # [{"det_id": int, "n_cajas": int, "sku": dict}]
) -> tuple[bool, str]:
    """
    Inserta una FAC-INT para una (PP, marca) de forma atómica.
    Correlativo calculado dentro de la TX para evitar colisiones concurrentes.
    numero_factura = FAC-INT-{id_pp}-{id_marca}-{NNNN:04d}

    Returns: (True, numero_factura) | (False, error_msg)
    """
    if not items:
        return False, "No hay artículos seleccionados."

    try:
        with engine.begin() as conn:
            # Correlativo atómico dentro de la transacción
            patron = f"FAC-INT-{id_pp}-{id_marca}-%"
            result = conn.execute(sqlt("""
                SELECT COALESCE(
                    MAX(CAST(SPLIT_PART(numero_factura_interna, '-', 5) AS INTEGER)),
                    0
                ) AS ultimo
                FROM venta_transito
                WHERE numero_factura_interna LIKE :patron
            """), {"patron": patron}).fetchone()

            correlativo    = (int(result[0]) if result and result[0] is not None else 0) + 1
            numero_factura = f"FAC-INT-{id_pp}-{id_marca}-{correlativo:04d}"

            for item in items:
                det_id         = int(item["det_id"])
                n_cajas        = int(item["n_cajas"])
                sku            = item["sku"]

                if n_cajas <= 0:
                    continue

                # cantidad_cajas = Column U = pares por caja (directo del F9)
                pares_por_caja = max(int(sku.get("cantidad_cajas") or 1), 1)
                pares_a_vender = pares_por_caja * n_cajas

                pesos = {
                    f"t{t}": max(int(sku.get(f"t{t}", 0) or 0), 0)
                    for t in range(33, 41)
                }
                base_total = sum(pesos.values())

                if base_total == 0:
                    return False, (
                        f"SKU línea {sku.get('linea', '?')} sin distribución de tallas válida."
                    )

                tallas: dict[str, int] = {}
                asignado = 0
                sorted_cols = sorted(pesos.keys(), key=lambda c: pesos[c], reverse=True)
                for i, col in enumerate(sorted_cols):
                    if i == len(sorted_cols) - 1:
                        qty = max(pares_a_vender - asignado, 0)
                    else:
                        qty = round(pares_a_vender * pesos[col] / base_total)
                        qty = min(qty, max(pares_a_vender - asignado, 0))
                    tallas[col] = max(qty, 0)
                    asignado += qty

                total_vendido = sum(tallas.values())

                # Rule of Zero Oversell: validar saldo real dentro de la TX.
                saldo_row = conn.execute(sqlt("""
                    SELECT ppd2.cantidad_pares
                           - COALESCE(
                               (SELECT SUM(vt2.cantidad_vendida)
                                FROM venta_transito vt2
                                WHERE vt2.pedido_proveedor_detalle_id = ppd2.id),
                               0
                             ) AS saldo_real
                    FROM pedido_proveedor_detalle ppd2
                    WHERE ppd2.id = :det_id
                    FOR UPDATE
                """), {"det_id": det_id}).fetchone()

                saldo_real = int(saldo_row[0]) if saldo_row and saldo_row[0] is not None else 0
                if total_vendido > saldo_real:
                    return False, (
                        f"Stock insuficiente línea {sku.get('linea', '?')}: "
                        f"intentás registrar {total_vendido} pares "
                        f"pero el saldo real en BD es {saldo_real}."
                    )

                conn.execute(sqlt("""
                    INSERT INTO venta_transito (
                        pedido_proveedor_id,
                        pedido_proveedor_detalle_id,
                        codigo_cliente, id_vendedor, plazo,
                        fecha_operacion,
                        t33, t34, t35, t36, t37, t38, t39, t40,
                        cantidad_vendida,
                        numero_factura_interna
                    ) VALUES (
                        :pp_id, :det_id,
                        :cliente, :vendedor, :plazo,
                        CURRENT_DATE,
                        :t33, :t34, :t35, :t36, :t37, :t38, :t39, :t40,
                        :total, :factura
                    )
                """), {
                    "pp_id":    id_pp,
                    "det_id":   det_id,
                    "cliente":  str(cod_cliente).strip(),
                    "vendedor": int(id_vendedor) if id_vendedor else None,
                    "plazo":    int(id_plazo),
                    **{k: int(v) for k, v in tallas.items()},
                    "total":    total_vendido,
                    "factura":  numero_factura,
                })

        return True, numero_factura

    except Exception as e:
        return False, f"Error al guardar: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# PARSER F9
# ─────────────────────────────────────────────────────────────────────────────

def parse_f9(
    file_source,
    numero_proforma: str,
    id_marca: int,
) -> tuple[pd.DataFrame, int, str | None]:
    """
    Lee un archivo F9 (.xlsx) y extrae las filas que coinciden con
    numero_proforma e id_marca.

    Returns:
        (df_detalle, total_pares, error_msg)
    """
    if isinstance(file_source, bytes):
        file_source = io.BytesIO(file_source)

    df = None
    for sheet in [0, "23956332"]:
        try:
            df = pd.read_excel(file_source, sheet_name=sheet, header=0)
            if hasattr(file_source, "seek"):
                file_source.seek(0)
            if not df.empty:
                break
        except Exception:
            if hasattr(file_source, "seek"):
                file_source.seek(0)
            continue

    if df is None or df.empty:
        return pd.DataFrame(), 0, "No se pudo leer el archivo o está vacío."

    col_proforma = _find_col(df, "PROFORMA", "Proforma", "proforma")
    col_marca    = _find_col(df, "id_marca", "ID_MARCA", "Id_marca")
    col_linea    = _find_col(df, "Linhea", "LINHEA", "Linea", "LINEA")
    col_ref      = _find_col(df, "Referencia", "REFERENCIA", "referencia")
    col_idmat    = _find_col(df, "id_material", "ID_MATERIAL")
    col_dmat     = _find_col(df, "descp_material", "Descp_material", "DESCP_MATERIAL")
    col_idcol    = _find_col(df, "id_color", "ID_COLOR")
    col_dcol     = _find_col(df, "descp_color", "Descp_color", "DESCP_COLOR")
    col_grada    = _find_col(df, "GRADA", "Grada", "grada")
    col_cajas    = _find_col(df, "Cantidad_por cajas", "Cantidad_por_cajas", "CANTIDAD_CAJAS")
    col_pares    = _find_col(df, "Compra_inicial", "COMPRA_INICIAL", "compra_inicial")

    faltantes = [n for n, c in [
        ("PROFORMA", col_proforma), ("id_marca", col_marca),
        ("Linhea", col_linea),      ("Referencia", col_ref),
        ("Compra_inicial", col_pares),
    ] if c is None]
    if faltantes:
        return pd.DataFrame(), 0, f"Columnas no encontradas en el F9: {', '.join(faltantes)}"

    df[col_proforma] = df[col_proforma].astype(str).str.strip()
    df[col_marca]    = df[col_marca].apply(_safe_int)

    mascara = (
        (df[col_proforma] == str(numero_proforma).strip()) &
        (df[col_marca]    == int(id_marca))
    )
    df_f = df[mascara].reset_index(drop=False)

    if df_f.empty:
        return (
            pd.DataFrame(), 0,
            f"No se encontraron filas para Proforma={numero_proforma} / Marca={id_marca}. "
            f"Proformas disponibles: {sorted(df[col_proforma].unique().tolist())}",
        )

    talla_cols = [c for c in df.columns if isinstance(c, (int, float)) and 33 <= int(c) <= 40]

    rows = []
    for _, row in df_f.iterrows():
        t_vals = {f"t{int(c)}": _safe_int(row.get(c, 0)) for c in talla_cols}
        for t in range(33, 41):
            t_vals.setdefault(f"t{t}", 0)

        rows.append({
            "linea":          str(row[col_linea]  if col_linea  else "").strip(),
            "referencia":     str(row[col_ref]    if col_ref    else "").strip(),
            "id_material":    _safe_int(row[col_idmat]) if col_idmat else None,
            "descp_material": str(row[col_dmat]   if col_dmat   else "").strip(),
            "id_color":       _safe_int(row[col_idcol]) if col_idcol else None,
            "descp_color":    str(row[col_dcol]   if col_dcol   else "").strip(),
            "id_marca":       int(id_marca),
            "grada":          str(row[col_grada]  if col_grada  else "").strip(),
            **t_vals,
            "cantidad_cajas": _safe_int(row[col_cajas]) if col_cajas else 0,
            "cantidad_pares": _safe_int(row[col_pares]),
            "fila_origen_f9": int(row.get("index", 0)) + 2,
        })

    df_result   = pd.DataFrame(rows)
    total_pares = int(df_result["cantidad_pares"].sum())
    return df_result, total_pares, None


# ─────────────────────────────────────────────────────────────────────────────
# ESCRITURA — crear nuevo PP desde el formulario
# ─────────────────────────────────────────────────────────────────────────────

def save_pp(header: dict, detalle_rows: list[dict]) -> tuple[bool, str]:
    """
    Inserta un Pedido Proveedor NEXUS completo (cabecera + detalle F9 + update IC).
    Retorna (True, numero_pp) o (False, mensaje_error).
    """
    numero      = get_next_numero_pp()
    total_pares = sum(_safe_int(r.get("cantidad_pares", 0)) for r in detalle_rows)

    try:
        with engine.begin() as conn:

            row = conn.execute(sqlt("""
                INSERT INTO pedido_proveedor (
                    numero_registro,    anio_fiscal,
                    id_intencion_compra, proveedor_importacion_id,
                    numero_proforma,    entidad_comercial,
                    fecha_pedido,       fecha_arribo_estimada,
                    estado,             pares_comprometidos,
                    notas
                ) VALUES (
                    :numero,    :anio,
                    :id_ic,     :id_prov,
                    :proforma,  'COMPRA_PREVIA',
                    :fecha_ped, :fecha_eta,
                    'ABIERTO',  :pares,
                    :notas
                )
                RETURNING id
            """), {
                "numero":    numero,
                "anio":      date.today().year,
                "id_ic":     int(header["id_intencion_compra"]),
                "id_prov":   int(header["id_proveedor"]),
                "proforma":  str(header["numero_proforma"]).strip(),
                "fecha_ped": header.get("fecha_pedido")           or date.today(),
                "fecha_eta": header.get("fecha_arribo_estimada")  or None,
                "pares":     total_pares,
                "notas":     header.get("observaciones")          or None,
            })
            id_pp = row.fetchone()[0]

            for r in detalle_rows:
                conn.execute(sqlt("""
                    INSERT INTO pedido_proveedor_detalle (
                        pedido_proveedor_id,
                        linea,       referencia,
                        id_material, descp_material,
                        id_color,    descp_color,
                        id_marca,    grada,
                        t33, t34, t35, t36, t37, t38, t39, t40,
                        cantidad_cajas, cantidad_pares, cantidad,
                        fila_origen_f9
                    ) VALUES (
                        :pp_id,
                        :linea,  :ref,
                        :id_mat, :dmat,
                        :id_col, :dcol,
                        :id_marca, :grada,
                        :t33, :t34, :t35, :t36, :t37, :t38, :t39, :t40,
                        :cajas, :pares, :pares,
                        :fila
                    )
                """), {
                    "pp_id":    id_pp,
                    "linea":    str(r.get("linea",  "") or ""),
                    "ref":      str(r.get("referencia", "") or ""),
                    "id_mat":   int(r["id_material"]) if r.get("id_material") else None,
                    "dmat":     str(r.get("descp_material", "") or ""),
                    "id_col":   int(r["id_color"])    if r.get("id_color")    else None,
                    "dcol":     str(r.get("descp_color", "") or ""),
                    "id_marca": int(r["id_marca"])    if r.get("id_marca")    else None,
                    "grada":    str(r.get("grada", "") or ""),
                    "t33": int(r.get("t33", 0) or 0),
                    "t34": int(r.get("t34", 0) or 0),
                    "t35": int(r.get("t35", 0) or 0),
                    "t36": int(r.get("t36", 0) or 0),
                    "t37": int(r.get("t37", 0) or 0),
                    "t38": int(r.get("t38", 0) or 0),
                    "t39": int(r.get("t39", 0) or 0),
                    "t40": int(r.get("t40", 0) or 0),
                    "cajas": int(r.get("cantidad_cajas", 0) or 0),
                    "pares": int(r.get("cantidad_pares", 0) or 0),
                    "fila":  int(r.get("fila_origen_f9", 0) or 0) or None,
                })

            conn.execute(sqlt("""
                UPDATE intencion_compra
                SET estado = 'VINCULADO_PP'
                WHERE id = :id_ic
                  AND estado = 'PENDIENTE_OPERATIVO'
            """), {"id_ic": int(header["id_intencion_compra"])})

        return True, numero

    except Exception as e:
        return False, f"Error en transacción: {e}"
