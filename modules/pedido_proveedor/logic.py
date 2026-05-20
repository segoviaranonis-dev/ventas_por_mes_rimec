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

from core.database import get_dataframe, engine, DBInspector
from core.auditoria import log_flujo, A


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
            ) + COALESCE(
                (SELECT SUM(ppd3.pares_vendidos)
                 FROM pedido_proveedor_detalle ppd3
                 WHERE ppd3.pedido_proveedor_id = pp.id),
                0
            )                                                         AS total_vendido,
            COALESCE(
                c.descp_cliente,
                (SELECT c2.descp_cliente
                 FROM intencion_compra_pedido icp2
                 JOIN intencion_compra ic2 ON ic2.id = icp2.intencion_compra_id
                 JOIN cliente_v2 c2         ON c2.id_cliente = ic2.id_cliente
                 WHERE icp2.pedido_proveedor_id = pp.id
                 LIMIT 1),
                '—'
            )                                                         AS cliente,
            COALESCE(
                v.descp_vendedor,
                (SELECT v2.descp_vendedor
                 FROM intencion_compra_pedido icp3
                 JOIN intencion_compra ic3  ON ic3.id = icp3.intencion_compra_id
                 JOIN vendedor_v2 v2        ON v2.id_vendedor = ic3.id_vendedor
                 WHERE icp3.pedido_proveedor_id = pp.id
                 LIMIT 1),
                '—'
            )                                                         AS vendedor
        FROM pedido_proveedor pp
        LEFT JOIN proveedor_importacion pi2 ON pi2.id          = pp.proveedor_importacion_id
        LEFT JOIN intencion_compra      ic  ON ic.id           = pp.id_intencion_compra
        LEFT JOIN cliente_v2            c   ON c.id_cliente    = ic.id_cliente
        LEFT JOIN vendedor_v2           v   ON v.id_vendedor   = ic.id_vendedor
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
            pp.categoria_id,
            pp.fecha_pedido,
            pp.fecha_arribo_estimada            AS fecha_promesa,
            pp.fecha_arribo_real,
            pp.estado_arribo,
            pp.fecha_arribo,
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
            ) + COALESCE(
                (SELECT SUM(ppd3.pares_vendidos)
                 FROM pedido_proveedor_detalle ppd3
                 WHERE ppd3.pedido_proveedor_id = pp.id),
                0
            )                                   AS total_vendido,
            COALESCE(
                c.descp_cliente,
                (SELECT c2.descp_cliente
                 FROM intencion_compra_pedido icp2
                 JOIN intencion_compra ic2 ON ic2.id = icp2.intencion_compra_id
                 JOIN cliente_v2 c2         ON c2.id_cliente = ic2.id_cliente
                 WHERE icp2.pedido_proveedor_id = pp.id LIMIT 1),
                '—'
            )                                   AS cliente,
            COALESCE(
                v.descp_vendedor,
                (SELECT v2.descp_vendedor
                 FROM intencion_compra_pedido icp3
                 JOIN intencion_compra ic3  ON ic3.id = icp3.intencion_compra_id
                 JOIN vendedor_v2 v2        ON v2.id_vendedor = ic3.id_vendedor
                 WHERE icp3.pedido_proveedor_id = pp.id LIMIT 1),
                '—'
            )                                   AS vendedor
        FROM pedido_proveedor pp
        LEFT JOIN proveedor_importacion pi2 ON pi2.id          = pp.proveedor_importacion_id
        LEFT JOIN intencion_compra       ic  ON ic.id           = pp.id_intencion_compra
        LEFT JOIN cliente_v2             c   ON c.id_cliente    = ic.id_cliente
        LEFT JOIN vendedor_v2            v   ON v.id_vendedor   = ic.id_vendedor
        WHERE pp.id = :id_pp
    """, {"id_pp": id_pp})

    if df.empty:
        return {}

    def _si(v) -> int:
        """Convierte valor de BD (puede ser None, nan, 'None') a int."""
        if v is None:
            return 0
        try:
            import math
            if isinstance(v, float) and math.isnan(v):
                return 0
        except Exception:
            pass
        s = str(v).strip()
        if s in ("", "None", "nan", "NaN", "NULL"):
            return 0
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return 0

    def _si_nullable(v) -> int | None:
        s = str(v).strip() if v is not None else ""
        if v is None or s in ("", "None", "nan", "NaN", "NULL"):
            return None
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return None

    row           = df.iloc[0]
    total_pares   = _si(row["total_pares"])
    total_vendido = _si(row["total_vendido"])
    return {
        "id":               _si(row["id"]),
        "numero_registro":  str(row["numero_registro"]),
        "numero_proforma":  str(row["numero_proforma"] or "—"),
        "total_pares":      total_pares,
        "estado":           str(row["estado"]),
        "categoria_id":     _si_nullable(row["categoria_id"]),
        "fecha_pedido":     row["fecha_pedido"],
        "fecha_promesa":    row["fecha_promesa"],
        "fecha_arribo_real": row["fecha_arribo_real"],
        "notas":            str(row["notas"] or ""),
        "proveedor":        str(row["proveedor"]),
        "ic_nro":           str(row["ic_nro"]),
        "marcas":           str(row["marcas"]),
        "total_articulos":  _si(row["total_articulos"]),
        "total_vendido":    total_vendido,
        "saldo":            total_pares - total_vendido,
        "cliente":          str(row["cliente"] or "—"),
        "vendedor":         str(row["vendedor"] or "—"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ALA NORTE — artículos del F9 con saldo disponible
# ─────────────────────────────────────────────────────────────────────────────

def get_pp_ala_norte(id_pp: int) -> pd.DataFrame:
    """
    Retorna los artículos de la proforma para un PP.
    Columnas: id, marca, linea, referencia, style_code,
              material_code, material, color_code, color, grada,
              grades_json, cantidad_inicial, vendido, saldo
    """
    return get_dataframe("""
        SELECT
            ppd.id,
            COALESCE(mv.descp_marca, '—')                               AS marca,
            ppd.linea,
            ppd.referencia,
            ppd.style_code,
            ppd.material_code,
            ppd.descp_material                                           AS material,
            ppd.color_code,
            ppd.descp_color                                              AS color,
            ppd.grada,
            ppd.grades_json::text                                        AS grades_json,
            ppd.cantidad_cajas,
            ppd.cantidad_pares                                           AS cantidad_inicial,
            COALESCE(SUM(vt.cantidad_vendida), 0)                       AS vendido,
            ppd.cantidad_pares - COALESCE(SUM(vt.cantidad_vendida), 0)  AS saldo
        FROM pedido_proveedor_detalle ppd
        LEFT JOIN marca_v2       mv ON mv.id_marca = ppd.id_marca
        LEFT JOIN venta_transito vt ON vt.pedido_proveedor_detalle_id = ppd.id
        WHERE ppd.pedido_proveedor_id = :id_pp
          AND ppd.referencia IS NOT NULL
        GROUP BY ppd.id, mv.descp_marca, ppd.linea, ppd.referencia,
                 ppd.style_code, ppd.material_code, ppd.descp_material,
                 ppd.color_code, ppd.descp_color, ppd.grada,
                 ppd.grades_json, ppd.cantidad_cajas, ppd.cantidad_pares
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

            # ── Header financiero en factura_interna ──────────────────────────
            cliente_row = conn.execute(sqlt(
                "SELECT id_cliente FROM cliente_v2 WHERE id_cliente::text = :cod"
            ), {"cod": str(cod_cliente).strip()}).fetchone()
            id_cliente_int = int(cliente_row[0]) if cliente_row else None

            det_ids_fi = [int(i["det_id"]) for i in items if int(i["n_cajas"]) > 0]
            prices_fi: dict[int, float] = {}
            if det_ids_fi:
                ph = ", ".join(f":d{k}" for k in range(len(det_ids_fi)))
                pr: dict = {f"d{k}": v for k, v in enumerate(det_ids_fi)}
                price_rows = conn.execute(sqlt(f"""
                    SELECT ppd.id, pl.lpn
                    FROM pedido_proveedor_detalle ppd
                    LEFT JOIN linea    l ON l.codigo_proveedor::text  = ppd.linea
                    LEFT JOIN material m ON m.codigo_proveedor::text  = ppd.material_code
                    LEFT JOIN LATERAL (
                        SELECT lpn FROM precio_lista
                        WHERE evento_id = COALESCE(
                            (SELECT ic2.precio_evento_id
                             FROM intencion_compra ic2
                             JOIN pedido_proveedor pp2 ON pp2.id_intencion_compra = ic2.id
                             WHERE pp2.id = ppd.pedido_proveedor_id LIMIT 1),
                            (SELECT id FROM precio_evento
                             WHERE estado = 'cerrado' ORDER BY created_at DESC LIMIT 1)
                        )
                        AND linea_id              = l.id
                        AND material_id           = m.id
                        LIMIT 1
                    ) pl ON true
                    WHERE ppd.id IN ({ph})
                """), pr).fetchall()
                prices_fi = {int(r[0]): (float(r[1]) if r[1] else 0.0) for r in price_rows}

            total_pares_fi = 0
            total_monto_fi = 0.0
            fi_detalles: list[dict] = []
            for item in items:
                det_id_i       = int(item["det_id"])
                n_cajas_i      = int(item["n_cajas"])
                if n_cajas_i <= 0:
                    continue
                pares_x_caja_i = max(int(item["sku"].get("cantidad_cajas") or 1), 1)
                pares_fi_i     = pares_x_caja_i * n_cajas_i
                lpn_fi         = prices_fi.get(det_id_i, 0.0)
                subtotal_fi    = pares_fi_i * lpn_fi
                total_pares_fi += pares_fi_i
                total_monto_fi += subtotal_fi
                fi_detalles.append({
                    "ppd_id":      det_id_i,
                    "cajas":       n_cajas_i,
                    "pares":       pares_fi_i,
                    "precio_unit": lpn_fi,
                    "subtotal":    subtotal_fi,
                })

            fi_row = conn.execute(sqlt("""
                INSERT INTO factura_interna
                    (pp_id, nro_factura, categoria_id, cliente_id, vendedor_id,
                     total_pares, total_monto, estado)
                VALUES (:pp, :nro, 2, :cli, :vend, :tp, :tm, 'RESERVADA')
                RETURNING id
            """), {
                "pp":   id_pp,
                "nro":  numero_factura,
                "cli":  id_cliente_int,
                "vend": int(id_vendedor) if id_vendedor else None,
                "tp":   total_pares_fi,
                "tm":   total_monto_fi,
            }).fetchone()
            fi_id = int(fi_row[0])

            for fd in fi_detalles:
                conn.execute(sqlt("""
                    INSERT INTO factura_interna_detalle
                        (factura_id, ppd_id, cajas, pares, precio_unit, subtotal)
                    VALUES (:fac, :ppd, :cajas, :pares, :pu, :sub)
                """), {
                    "fac":   fi_id,
                    "ppd":   fd["ppd_id"],
                    "cajas": fd["cajas"],
                    "pares": fd["pares"],
                    "pu":    fd["precio_unit"],
                    "sub":   fd["subtotal"],
                })

        return True, numero_factura

    except Exception as e:
        return False, f"Error al guardar: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# PARSER F9
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# PARSER DE PROFORMA COMERCIAL (reemplaza F9 para PPs creados por Digitación)
# ─────────────────────────────────────────────────────────────────────────────

def parse_proforma(file_bytes: bytes) -> tuple[pd.DataFrame, int, str | None]:
    """
    Parser oficial de Fatura Proforma Beira Rio (Momento Cero).

    Columnas fijas:
      A(0)=ITEM  B(1)=NCM  C(2)=STYLE  D(3)=NAME
      E(4)=MATERIAL CODE  F(5)=MATERIAL  G(6)=COLOR CODE  H(7)=COLOR
      I(8)=BRAND  J(9)=SHOP  K(10)=BOXES  L(11)=PAIRS  M(12)=UNIT  N(13)=AMOUNT
      O(14+) = cantidades por talla (dinámicas)

    Tres tipos de fila:
      1. Cabecera de tallas: col A=None, cols O+ = números de talla
      2. Fila de datos:      col A = número entero
      3. Fila de totales:    col L (PAIRS) = 'TOTAL'  →  fin

    STYLE '2133.182' → linea 2133, ref 100 (pillar_parse; leer celda como texto)
    """
    from modules.rimec_engine.pillar_parse import parsear_linea_referencia

    GRADE_START = 14

    try:
        try:
            df_raw = pd.read_excel(
                io.BytesIO(file_bytes),
                header=None,
                engine="openpyxl",
                dtype=object,
            )
        except Exception:
            df_raw = pd.read_excel(
                io.BytesIO(file_bytes),
                header=None,
                engine="xlrd",
                dtype=object,
            )
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

    def _safe_int(v) -> int:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return 0
        try:
            return int(float(v))
        except Exception:
            return 0

    def _safe_float(v) -> float:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return 0.0
        try:
            return float(v)
        except Exception:
            return 0.0

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

    # Leer cabecera de tallas inicial de la fila donde está el encabezado
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

        # ── Fila de TOTALES → fin de datos ──────────────────────────────
        col_pairs_idx = 11 + offset
        col_style_idx = 2 + offset

        pairs_str = str(row.iloc[col_pairs_idx]).strip().upper() if len(row) > col_pairs_idx else ""
        col2_str  = str(row.iloc[col_style_idx]).strip().upper()  if len(row) > col_style_idx  else ""
        if pairs_str == "TOTAL" or col2_str == "TOTAL":
            break

        item_null = item_val is None or (
            isinstance(item_val, float) and math.isnan(item_val)
        )

        # ── Fila SEPARADORA (col A nula, cols O+ con tallas) ────────────
        if item_null:
            new_grades: list[str] = []
            for col_i in range(grade_start, df_raw.shape[1]):
                lbl = _grade_label(row.iloc[col_i])
                if lbl:
                    new_grades.append(lbl)
            if new_grades:
                current_grades = new_grades
            continue

        # ── Fila de DATOS ────────────────────────────────────────────────
        style_raw = ""
        if len(row) > col_style_idx and pd.notna(row.iloc[col_style_idx]):
            sv = row.iloc[col_style_idx]
            if isinstance(sv, float):
                style_raw = f"{sv:.10f}".rstrip("0").rstrip(".")
            else:
                style_raw = str(sv).strip()
        if style_raw.lower() in ("nan", "none", ""):
            continue
        try:
            linea_cod, ref_cod = parsear_linea_referencia(style_raw)
        except ValueError:
            continue  # fila mal formada, saltar
        if ref_cod is None:
            continue  # STYLE sin referencia — no importar fila incompleta

        # Curva de tallas: {talla_label: cantidad}
        grades_json: dict[str, int] = {}
        for g_i, grade in enumerate(current_grades):
            col_i = grade_start + g_i
            if col_i < len(row):
                qty = _safe_int(row.iloc[col_i])
                if qty > 0:
                    grades_json[grade] = qty

        # Rango compacto: "19-26" (usando el primer y último grado activo)
        active = sorted(grades_json.keys(),
                        key=lambda x: float(x.split("/")[0]))
        grade_range = f"{active[0]}-{active[-1]}" if active else ""

        rows.append({
            "item":          str(_safe_int(item_val)),
            "ncm":           str(row.iloc[1 + offset]).strip() if len(row) > 1 + offset and pd.notna(row.iloc[1 + offset]) else "",
            "style_code":    style_raw,                        # "2133.182" completo
            "linea_codigo_proveedor":     str(linea_cod),
            "referencia_codigo_proveedor": str(ref_cod),
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
            "grade_range":   grade_range,                      # "19-26"
            "grades_json":   grades_json,
        })

    if not rows:
        return pd.DataFrame(), 0, "No se encontraron artículos en la proforma."

    df_result = pd.DataFrame(rows)
    total_pares = int(df_result["pairs"].sum())
    return df_result, total_pares, None


def get_estado_borrado_importacion_pp(pp_id: int) -> dict:
    """
    Resume ventas del stock importado. Borrado total solo si vendido = 0.
    """
    try:
        with engine.connect() as conn:
            row = conn.execute(sqlt("""
                SELECT
                    COUNT(ppd.id)::int AS n_articulos,
                    COALESCE(SUM(ppd.cantidad_pares), 0)::bigint AS pares_total,
                    COALESCE(SUM(ppd.pares_vendidos), 0)::bigint AS vendido_ppd,
                    COALESCE((
                        SELECT SUM(vt.cantidad_vendida)
                        FROM venta_transito vt
                        JOIN pedido_proveedor_detalle d
                          ON d.id = vt.pedido_proveedor_detalle_id
                        WHERE d.pedido_proveedor_id = :pp_id
                    ), 0)::bigint AS vendido_vt,
                    (SELECT COUNT(*)::int FROM factura_interna fi
                     WHERE fi.pp_id = :pp_id) AS n_facturas
                FROM pedido_proveedor_detalle ppd
                WHERE ppd.pedido_proveedor_id = :pp_id
            """), {"pp_id": pp_id}).fetchone()
        if not row or int(row.n_articulos or 0) == 0:
            return {
                "n_articulos": 0,
                "pares_total": 0,
                "vendido": 0,
                "n_facturas": 0,
                "puede_borrar": False,
                "motivo": "No hay importación cargada.",
            }
        vendido_vt = int(row.vendido_vt or 0)
        vendido_ppd = int(row.vendido_ppd or 0)
        vendido = max(vendido_vt, vendido_ppd)
        n_fi = int(row.n_facturas or 0)
        puede = vendido == 0
        motivo = ""
        if not puede:
            motivo = (
                f"Ya hay **{vendido:,} pares vendidos** en este PP. "
                "No se puede borrar la importación."
            )
        return {
            "n_articulos": int(row.n_articulos),
            "pares_total": int(row.pares_total),
            "vendido": vendido,
            "n_facturas": n_fi,
            "puede_borrar": puede,
            "motivo": motivo,
        }
    except Exception as e:
        DBInspector.log(f"[PP] get_estado_borrado_importacion_pp: {e}", "ERROR")
        return {
            "n_articulos": 0,
            "pares_total": 0,
            "vendido": 0,
            "n_facturas": 0,
            "puede_borrar": False,
            "motivo": str(e),
        }


def borrar_importacion_pp(pp_id: int) -> tuple[bool, str]:
    """
    Elimina por completo el detalle importado (proforma/F9) del PP.
    Sin archivo de borrado — una sola transacción rápida.
    Solo permitido si ventas = 0 y sin facturas internas.
    """
    estado = get_estado_borrado_importacion_pp(pp_id)
    if estado["n_articulos"] == 0:
        return False, "No hay artículos importados."
    if not estado["puede_borrar"]:
        return False, estado.get("motivo") or "No se puede borrar esta importación."

    try:
        with engine.begin() as conn:
            conn.execute(sqlt("""
                DELETE FROM venta_transito vt
                USING pedido_proveedor_detalle ppd
                WHERE vt.pedido_proveedor_detalle_id = ppd.id
                  AND ppd.pedido_proveedor_id = :pp_id
            """), {"pp_id": pp_id})

            conn.execute(sqlt("""
                DELETE FROM factura_interna_detalle fid
                USING factura_interna fi
                WHERE fid.factura_id = fi.id
                  AND fi.pp_id = :pp_id
            """), {"pp_id": pp_id})

            conn.execute(sqlt(
                "DELETE FROM factura_interna WHERE pp_id = :pp_id"
            ), {"pp_id": pp_id})

            conn.execute(sqlt(
                "DELETE FROM snapshot_costos WHERE pp_id = :pp_id"
            ), {"pp_id": pp_id})

            del_row = conn.execute(sqlt("""
                DELETE FROM pedido_proveedor_detalle
                WHERE pedido_proveedor_id = :pp_id
                RETURNING id
            """), {"pp_id": pp_id})
            n_del = len(del_row.fetchall())

            conn.execute(sqlt("""
                UPDATE pedido_proveedor
                SET pares_comprometidos = 0
                WHERE id = :pp_id
            """), {"pp_id": pp_id})

        DBInspector.log(
            f"[PP] Importación borrada pp_id={pp_id}: {n_del} SKUs", "WARNING"
        )
        return True, f"Importación eliminada ({n_del} artículos). Podés cargar la proforma de nuevo."

    except Exception as e:
        DBInspector.log(f"[PP] borrar_importacion_pp {pp_id}: {e}", "ERROR")
        return False, f"Error al borrar: {e}"


def _calcular_fob_ajustado(fob: float, d1: float, d2: float,
                            d3: float, d4: float) -> float:
    """Aplica descuentos comerciales escalados al precio FOB unitario."""
    result = fob
    for d in (d1, d2, d3, d4):
        if d and d > 0:
            result *= (1 - float(d))
    return round(result, 4)


def populate_pp_from_proforma(
    pp_id:        int,
    proforma:     str,
    nro_externo:  str,
    descuento_1:  float,
    descuento_2:  float,
    descuento_3:  float,
    descuento_4:  float,
    fecha_eta,
    categoria_id: int | None,
    detalle_rows: list[dict],
    usuario_id:   int | None = None,
) -> tuple[bool, str]:
    """
    Persiste la proforma en un PP vacío (creado por Digitación).

    - Actualiza cabecera: proforma, nro_externo, descuentos, eta
    - Inserta filas en pedido_proveedor_detalle con FOB ajustado y grades_json
    - Registra en flujo_auditoria
    - Regla 2.2: si el pilar color/material tiene nombre/descripcion NULL y la proforma
      trae texto, ejecuta UPDATE en ``public.color`` / ``public.material`` (mismo proveedor).
    """
    import json

    total_pares = sum(int(r.get("pairs", 0)) for r in detalle_rows)
    total_fob   = round(sum(float(r.get("amount_fob", 0)) for r in detalle_rows), 2)

    try:
        with engine.begin() as conn:
            # ── Actualizar cabecera ───────────────────────────────────────
            conn.execute(sqlt("""
                UPDATE pedido_proveedor
                SET numero_proforma       = :pf,
                    nro_pedido_externo    = :ext,
                    descuento_1           = :d1,
                    descuento_2           = :d2,
                    descuento_3           = :d3,
                    descuento_4           = :d4,
                    fecha_arribo_estimada = :eta,
                    pares_comprometidos   = :pares,
                    categoria_id          = COALESCE(categoria_id, :cat),
                    fecha_pedido          = CURRENT_DATE
                WHERE id = :pp_id
            """), {
                "pf":    proforma.strip() or None,
                "ext":   nro_externo.strip() or None,
                "d1":    descuento_1,
                "d2":    descuento_2,
                "d3":    descuento_3,
                "d4":    descuento_4,
                "eta":   fecha_eta or None,
                "pares": total_pares,
                "cat":   categoria_id,
                "pp_id": pp_id,
            })

            row_pid = conn.execute(
                sqlt(
                    "SELECT proveedor_importacion_id FROM pedido_proveedor WHERE id = :pp_id"
                ),
                {"pp_id": pp_id},
            ).fetchone()
            prov_id = int(row_pid[0]) if row_pid and row_pid[0] is not None else 654

            # ── Lookup de marcas (brand → id_marca) ──────────────────────
            marc_rows = conn.execute(sqlt(
                "SELECT id_marca, UPPER(descp_marca) AS nom FROM marca_v2"
            )).fetchall()
            marca_lookup: dict[str, int] = {
                r2.nom: int(r2.id_marca) for r2 in marc_rows if r2.nom
            }

            # ── Lookup material (codigo_proveedor → (id, descripcion)) ───
            mat_rows = conn.execute(
                sqlt(
                    "SELECT id, codigo_proveedor::text, descripcion FROM material "
                    "WHERE proveedor_id = CAST(:pid AS bigint)"
                ),
                {"pid": prov_id},
            ).fetchall()
            mat_lookup: dict[str, tuple] = {
                r2[1]: (int(r2[0]), str(r2[2] or "")) for r2 in mat_rows
            }

            # ── Lookup color (codigo_proveedor → (id, nombre)) ───────────
            col_rows = conn.execute(
                sqlt(
                    "SELECT id, codigo_proveedor::text, nombre FROM color "
                    "WHERE proveedor_id = CAST(:pid AS bigint)"
                ),
                {"pid": prov_id},
            ).fetchall()
            col_lookup: dict[str, tuple] = {
                r2[1]: (int(r2[0]), str(r2[2] or "")) for r2 in col_rows
            }

            # ── Limpiar detalle previo (re-import) ────────────────────────
            conn.execute(sqlt(
                "DELETE FROM pedido_proveedor_detalle WHERE pedido_proveedor_id = :pp_id"
            ), {"pp_id": pp_id})

            # ── Insertar cada SKU ────────────────────────────────────────
            for r in detalle_rows:
                fob_unit  = float(r.get("unit_fob", 0))
                fob_aj    = _calcular_fob_ajustado(
                    fob_unit, descuento_1, descuento_2,
                    descuento_3, descuento_4
                )
                grades    = r.get("grades_json", {})
                brand_key  = r.get("brand", "").strip().upper()
                id_marca   = marca_lookup.get(brand_key)
                grada_val  = r.get("grade_range", "") or ""
                mat_code_s = str(r.get("material_code", "") or "").strip()
                col_code_s = str(r.get("color_code",   "") or "").strip()
                mat_hit    = mat_lookup.get(mat_code_s)
                col_hit    = col_lookup.get(col_code_s)
                id_mat     = mat_hit[0] if mat_hit else None
                descp_mat  = mat_hit[1] if mat_hit else (r.get("material", "") or "")
                id_col     = col_hit[0] if col_hit else None
                descp_col  = col_hit[1] if col_hit else (r.get("color", "") or "")

                conn.execute(sqlt("""
                    INSERT INTO pedido_proveedor_detalle (
                        pedido_proveedor_id, cantidad,
                        id_marca,       ncm,       style_code,
                        linea,          referencia,
                        nombre,
                        id_material,    descp_material, material_code,
                        id_color,       descp_color,    color_code,
                        grada,
                        t33, t34, t35, t36, t37, t38, t39, t40,
                        cantidad_cajas, cantidad_pares,
                        unit_fob,       unit_fob_ajustado,
                        amount_fob,     grades_json,
                        fila_origen_f9
                    ) VALUES (
                        :pp_id, :pairs,
                        :id_marca, :ncm,   :style,
                        :linea,    :ref,
                        :nombre,
                        :id_mat,   :mat,   :mat_code,
                        :id_col,   :col,   :col_code,
                        :grada,
                        :t33, :t34, :t35, :t36, :t37, :t38, :t39, :t40,
                        :boxes, :pairs,
                        :ufob,  :ufob_aj,
                        :afob,  CAST(:grades AS jsonb),
                        :fila
                    )
                """), {
                    "pp_id":    pp_id,
                    "id_marca": id_marca,
                    "ncm":      r.get("ncm", "") or "",
                    "style":    r.get("style_code", "") or "",
                    "linea":    r.get("linea_codigo_proveedor", "") or "",
                    "ref":      r.get("referencia_codigo_proveedor", "") or "",
                    "nombre":   r.get("name", "") or "",
                    "id_mat":   id_mat,
                    "mat":      descp_mat,
                    "mat_code": mat_code_s,
                    "id_col":   id_col,
                    "col":      descp_col,
                    "col_code": col_code_s,
                    "grada":    grada_val,                         # "19-26"
                    "t33":      grades.get("33", 0),
                    "t34":      grades.get("34", 0),
                    "t35":      grades.get("35", 0),
                    "t36":      grades.get("36", 0),
                    "t37":      grades.get("37", 0),
                    "t38":      grades.get("38", 0),
                    "t39":      grades.get("39", 0),
                    "t40":      grades.get("40", 0),
                    "boxes":    int(r.get("boxes", 0)),
                    "pairs":    int(r.get("pairs", 0)),
                    "ufob":     fob_unit,
                    "ufob_aj":  fob_aj,
                    "afob":     float(r.get("amount_fob", 0)),
                    "grades":   json.dumps(grades, ensure_ascii=False),
                    "fila":     int(r.get("item", 0)),
                })

                # Regla 2.2: enriquecimiento no inverso de pilar color/material (motor compartido).
                # Refactorizado para usar upsert_material/upsert_color (idempotente + regla §6).
                from core.pilares import upsert_material, upsert_color

                heal_col = str(r.get("color", "") or "").strip()
                if col_code_s and heal_col:
                    # Usar motor compartido para aplicar regla no inversa completa
                    upsert_color(
                        conn,
                        col_code_s,
                        prov_id,
                        nombre=heal_col[:2000],
                        fuente="proforma",
                    )

                heal_mat = str(r.get("material", "") or "").strip()
                if mat_code_s and heal_mat:
                    # Usar motor compartido para aplicar regla no inversa completa
                    upsert_material(
                        conn,
                        mat_code_s,
                        prov_id,
                        descripcion=heal_mat[:2000],
                        fuente="proforma",
                    )

        # ── Auditoría ────────────────────────────────────────────────────
        row_pp = get_dataframe(
            "SELECT numero_registro FROM pedido_proveedor WHERE id = :id",
            {"id": pp_id}
        )
        nro = row_pp["numero_registro"].iloc[0] if row_pp is not None and not row_pp.empty else str(pp_id)

        log_flujo(
            entidad="PP", entidad_id=pp_id, nro_registro=nro,
            accion=A.PP_F9_CARGADO,
            snap={
                "proforma":        proforma.strip(),
                "nro_externo":     nro_externo.strip() or None,
                "total_pares":     total_pares,
                "total_fob_usd":   total_fob,
                "descuento_1":     descuento_1,
                "descuento_2":     descuento_2,
                "descuento_3":     descuento_3,
                "descuento_4":     descuento_4,
                "n_skus":          len(detalle_rows),
            },
            usuario_id=usuario_id,
        )
        DBInspector.log(
            f"[PP] Proforma cargada en {nro}: {len(detalle_rows)} SKUs · "
            f"{total_pares:,} pares · USD {total_fob:,.2f}", "SUCCESS"
        )
        return True, f"{total_pares:,} pares · {len(detalle_rows)} SKUs · USD {total_fob:,.2f}"

    except Exception as e:
        DBInspector.log(f"[PP] Error cargando proforma en PP {pp_id}: {e}", "ERROR")
        return False, f"Error al cargar proforma: {e}"


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
# CONSULTA — ICs vinculadas a PP via tabla puente (Digitación)
# ─────────────────────────────────────────────────────────────────────────────

def get_datos_ics_de_pp(pp_id: int) -> pd.DataFrame:
    """
    Retorna las ICs asignadas a un PP por Digitación via intencion_compra_pedido.
    Incluye proveedor, marca y nro_pedido_fabrica.
    """
    return get_dataframe("""
        SELECT
            ic.id                           AS ic_id,
            ic.numero_registro              AS nro_ic,
            ic.id_marca,
            ic.id_proveedor,
            mv.descp_marca                  AS marca,
            COALESCE(pi2.nombre, '—')       AS proveedor,
            ic.cantidad_total_pares         AS pares,
            ic.categoria_id,
            icp.nro_pedido_fabrica,
            icp.precio_evento_id
        FROM intencion_compra_pedido icp
        JOIN intencion_compra    ic  ON ic.id        = icp.intencion_compra_id
        JOIN marca_v2            mv  ON mv.id_marca  = ic.id_marca
        LEFT JOIN proveedor_importacion pi2 ON pi2.id = ic.id_proveedor
        WHERE icp.pedido_proveedor_id = :pp_id
        ORDER BY ic.numero_registro
    """, {"pp_id": pp_id})


def get_evento_precio_pp(pp_id: int) -> int | None:
    """
    Retorna el precio_evento_id vigente del PP.
    Lo busca en la tabla puente intencion_compra_pedido.
    """
    df = get_dataframe("""
        SELECT icp.precio_evento_id
        FROM intencion_compra_pedido icp
        WHERE icp.pedido_proveedor_id = :pp_id
          AND icp.precio_evento_id IS NOT NULL
        LIMIT 1
    """, {"pp_id": pp_id})
    if df is None or df.empty:
        return None
    v = df["precio_evento_id"].iloc[0]
    try:
        return int(v) if v is not None else None
    except Exception:
        return None


def get_precios_stock_pp(pp_id: int, evento_id: int) -> pd.DataFrame:
    """
    Cruza el stock del PP con precio_lista.

    Los códigos del proveedor (ppd.linea, ppd.material_code) se traducen
    a IDs internos via las tablas linea y material del catálogo Bazar:
      ppd.linea        → linea.id (via linea.codigo_proveedor)
      ppd.material_code → material.id (via material.codigo_proveedor)

    precio_lista almacena esos IDs como texto en linea_codigo y
    material_descripcion. La referencia no se cruza porque en este
    proveedor el precio se define por linea + material.
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(sqlt("""
                SELECT
                    ppd.id                                                       AS det_id,
                    COALESCE(mv.descp_marca, '—')                                AS marca,
                    ppd.linea                                                     AS linea_codigo,
                    ppd.referencia                                                AS referencia_codigo,
                    ppd.material_code                                             AS cod_material,
                    ppd.descp_material                                            AS material,
                    ppd.descp_color                                               AS color,
                    ppd.grada,
                    ppd.cantidad_pares                                            AS inicial,
                    COALESCE(SUM(vt.cantidad_vendida), 0)                         AS vendido,
                    ppd.cantidad_pares - COALESCE(SUM(vt.cantidad_vendida), 0)    AS saldo,
                    pl.lpn,
                    pl.lpc02,
                    pl.lpc03,
                    pl.lpc04,
                    pl.nombre_caso_aplicado                                       AS caso_precio,
                    pl.dolar_aplicado,
                    pl.indice_aplicado
                FROM pedido_proveedor_detalle ppd
                JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
                LEFT JOIN marca_v2  mv ON mv.id_marca = ppd.id_marca
                LEFT JOIN venta_transito vt ON vt.pedido_proveedor_detalle_id = ppd.id
                LEFT JOIN linea l ON l.proveedor_id = pp.proveedor_importacion_id
                                 AND l.codigo_proveedor::text = NULLIF(TRIM(ppd.linea), '')
                LEFT JOIN referencia ref ON ref.linea_id = l.id
                                 AND ref.codigo_proveedor::text = NULLIF(TRIM(ppd.referencia), '')
                LEFT JOIN material m ON m.proveedor_id = pp.proveedor_importacion_id
                                 AND m.codigo_proveedor::text = NULLIF(TRIM(ppd.material_code), '')
                LEFT JOIN precio_lista pl ON pl.evento_id = :evento_id
                                         AND pl.linea_id = l.id
                                         AND pl.referencia_id = ref.id
                                         AND pl.material_id = m.id
                WHERE ppd.pedido_proveedor_id = :pp_id
                  AND NULLIF(TRIM(ppd.linea), '') IS NOT NULL
                  AND NULLIF(TRIM(ppd.referencia), '') IS NOT NULL
                GROUP BY ppd.id, mv.descp_marca, ppd.linea, ppd.referencia,
                         ppd.material_code, ppd.descp_material, ppd.descp_color,
                         ppd.grada, ppd.cantidad_pares,
                         pl.lpn, pl.lpc02, pl.lpc03, pl.lpc04,
                         pl.nombre_caso_aplicado, pl.dolar_aplicado, pl.indice_aplicado
                ORDER BY ppd.id
            """), {"pp_id": pp_id, "evento_id": evento_id}).fetchall()
        return pd.DataFrame([dict(r._mapping) for r in rows])
    except Exception as e:
        DBInspector.log(f"[PP] get_precios_stock_pp: {e}", "ERROR")
        return pd.DataFrame()


def populate_pp(
    pp_id:        int,
    proforma:     str,
    proveedor_id: int,
    fecha_eta,
    categoria_id: int | None,
    detalle_rows: list[dict],
) -> tuple[bool, str]:
    """
    Carga F9 en un PP vacío creado por Digitación.
    Actualiza la cabecera y agrega las filas de detalle.
    Retorna (True, mensaje) o (False, error).
    """
    total_pares = sum(_safe_int(r.get("cantidad_pares", 0)) for r in detalle_rows)
    try:
        with engine.begin() as conn:
            conn.execute(sqlt("""
                UPDATE pedido_proveedor
                SET numero_proforma          = :proforma,
                    proveedor_importacion_id = :prov,
                    fecha_arribo_estimada    = :eta,
                    pares_comprometidos      = :pares,
                    categoria_id             = :cat,
                    entidad_comercial        = 'COMPRA_PREVIA',
                    fecha_pedido             = CURRENT_DATE
                WHERE id = :pp_id
            """), {
                "proforma": proforma.strip(),
                "prov":     proveedor_id,
                "eta":      fecha_eta or None,
                "pares":    total_pares,
                "cat":      categoria_id,
                "pp_id":    pp_id,
            })

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
                    "pp_id":    pp_id,
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

        # ── Leer datos del PP para snapshot forense ───────────────────────
        pp_snap = get_dataframe("""
            SELECT pp.numero_registro,
                   pi2.nombre AS proveedor,
                   cv.descp_cliente AS cliente,
                   vv.descp_vendedor AS vendedor,
                   STRING_AGG(DISTINCT mv.descp_marca, ' / ') AS marcas,
                   COUNT(DISTINCT ppd.id) AS n_articulos,
                   ic.numero_registro AS nro_ic
            FROM pedido_proveedor pp
            LEFT JOIN proveedor_importacion pi2 ON pi2.id = pp.proveedor_importacion_id
            LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
            LEFT JOIN intencion_compra ic  ON ic.id  = icp.intencion_compra_id
            LEFT JOIN cliente_v2  cv ON cv.id_cliente  = ic.id_cliente
            LEFT JOIN vendedor_v2 vv ON vv.id_vendedor = ic.id_vendedor
            LEFT JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
            LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
            WHERE pp.id = :pp_id
            GROUP BY pp.numero_registro, pi2.nombre,
                     cv.descp_cliente, vv.descp_vendedor, ic.numero_registro
        """, {"pp_id": pp_id})

        snap_row = pp_snap.iloc[0] if pp_snap is not None and not pp_snap.empty else None

        from core.auditoria import log_flujo, A
        log_flujo(
            entidad="PP", entidad_id=pp_id,
            nro_registro=snap_row["numero_registro"] if snap_row is not None else str(pp_id),
            accion=A.PP_F9_CARGADO,
            snap={
                "proforma":    proforma.strip(),
                "proveedor":   snap_row["proveedor"]  if snap_row is not None else None,
                "cliente":     snap_row["cliente"]    if snap_row is not None else None,
                "vendedor":    snap_row["vendedor"]   if snap_row is not None else None,
                "marcas":      snap_row["marcas"]     if snap_row is not None else None,
                "ic_origen":   snap_row["nro_ic"]     if snap_row is not None else None,
                "total_pares": total_pares,
                "n_articulos": int(snap_row["n_articulos"] or 0) if snap_row is not None else 0,
                "fecha_eta":   str(fecha_eta) if fecha_eta else None,
                "categoria_id": categoria_id,
            },
        )

        return True, f"{total_pares:,} pares cargados en {pp_id}"
    except Exception as e:
        return False, f"Error al cargar F9: {e}"


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

            # TRAZABILIDAD DE ORIGEN (MANDATO DE DIRECCIÓN)
            # categoria_id se hereda de la Intención de Compra padre.
            # Valores posibles:
            #   PRE VENTA  → la mercadería tiene cliente asignado antes de llegar.
            #                Al facturar: se convierte en factura directa al cliente.
            #   PROGRAMADO → proyección de compra sin cliente asignado.
            #                Al facturar: intermediación entre Beira Rio y cliente.
            #   STOCK      → saldo no vendido de ambas categorías.
            #                NO se origina en IC. Nace en gestión de ventas mayorista.
            ic_row = conn.execute(sqlt(
                "SELECT categoria_id FROM intencion_compra WHERE id = :id_ic"
            ), {"id_ic": int(header["id_intencion_compra"])}).fetchone()
            categoria_id = ic_row[0] if ic_row and ic_row[0] is not None else None

            row = conn.execute(sqlt("""
                INSERT INTO pedido_proveedor (
                    numero_registro,    anio_fiscal,
                    id_intencion_compra, proveedor_importacion_id,
                    numero_proforma,    entidad_comercial,
                    fecha_pedido,       fecha_arribo_estimada,
                    estado,             pares_comprometidos,
                    categoria_id,       notas
                ) VALUES (
                    :numero,    :anio,
                    :id_ic,     :id_prov,
                    :proforma,  'COMPRA_PREVIA',
                    :fecha_ped, :fecha_eta,
                    'ABIERTO',  :pares,
                    :categoria_id, :notas
                )
                RETURNING id
            """), {
                "numero":       numero,
                "anio":         date.today().year,
                "id_ic":        int(header["id_intencion_compra"]),
                "id_prov":      int(header["id_proveedor"]),
                "proforma":     str(header["numero_proforma"]).strip(),
                "fecha_ped":    header.get("fecha_pedido")          or date.today(),
                "fecha_eta":    header.get("fecha_arribo_estimada") or None,
                "pares":        total_pares,
                "categoria_id": categoria_id,
                "notas":        header.get("observaciones")         or None,
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


# ─────────────────────────────────────────────────────────────────────────────
# LOGÍSTICA — ETA editable y reasignación de ICs
# ─────────────────────────────────────────────────────────────────────────────

def actualizar_eta_pp(pp_id: int, nueva_fecha, usuario_id: int | None = None) -> bool:
    """
    Actualiza la fecha_arribo_estimada del PP y registra en auditoría.
    La ETA es la espina dorsal logística: su cambio puede mover el PP de quincena.
    """
    try:
        with engine.begin() as conn:
            row = conn.execute(sqlt(
                "SELECT numero_registro, fecha_arribo_estimada FROM pedido_proveedor WHERE id=:id"
            ), {"id": pp_id}).fetchone()
            eta_anterior = str(row[1]) if row and row[1] else None

            conn.execute(sqlt("""
                UPDATE pedido_proveedor
                SET fecha_arribo_estimada = :fecha
                WHERE id = :pp_id
            """), {"fecha": nueva_fecha or None, "pp_id": pp_id})

        nro = row[0] if row else str(pp_id)
        log_flujo(
            entidad="PP", entidad_id=pp_id, nro_registro=nro,
            accion=A.PP_ETA_ACTUALIZADA,
            snap={"eta_anterior": eta_anterior, "eta_nueva": str(nueva_fecha) if nueva_fecha else None},
            usuario_id=usuario_id,
        )
        DBInspector.log(f"[PP] ETA actualizada: {nro} → {nueva_fecha}", "SUCCESS")
        return True
    except Exception as e:
        DBInspector.log(f"[PP] Error actualizando ETA {pp_id}: {e}", "ERROR")
        return False


def desasignar_ic_de_pp(ic_id: int, pp_id: int, usuario_id: int | None = None) -> bool:
    """
    Quita una IC del PP: elimina del bridge table, revierte IC→AUTORIZADO,
    descuenta pares del PP. La IC vuelve al pool de Digitación disponible
    para ser asignada a otro PP.
    """
    try:
        with engine.begin() as conn:
            ic_row = conn.execute(sqlt("""
                SELECT ic.numero_registro, ic.cantidad_total_pares, mv.descp_marca
                FROM intencion_compra ic
                JOIN marca_v2 mv ON mv.id_marca = ic.id_marca
                WHERE ic.id = :ic_id
            """), {"ic_id": ic_id}).fetchone()

            pp_row = conn.execute(sqlt(
                "SELECT numero_registro FROM pedido_proveedor WHERE id=:id"
            ), {"id": pp_id}).fetchone()

            # Eliminar del bridge
            conn.execute(sqlt("""
                DELETE FROM intencion_compra_pedido
                WHERE intencion_compra_id = :ic_id
                  AND pedido_proveedor_id = :pp_id
            """), {"ic_id": ic_id, "pp_id": pp_id})

            # IC vuelve a AUTORIZADO
            conn.execute(sqlt("""
                UPDATE intencion_compra
                SET estado = 'AUTORIZADO', precio_evento_id = precio_evento_id
                WHERE id = :ic_id
            """), {"ic_id": ic_id})

            # Descontar pares del PP
            pares_ic = int(ic_row[1] or 0) if ic_row else 0
            if pares_ic > 0:
                conn.execute(sqlt("""
                    UPDATE pedido_proveedor
                    SET pares_comprometidos = GREATEST(COALESCE(pares_comprometidos, 0) - :pares, 0)
                    WHERE id = :pp_id
                """), {"pares": pares_ic, "pp_id": pp_id})

        nro_ic = ic_row[0] if ic_row else str(ic_id)
        nro_pp = pp_row[0] if pp_row else str(pp_id)
        log_flujo(
            entidad="IC", entidad_id=ic_id, nro_registro=nro_ic,
            accion=A.DIG_IC_DESASIGNADA,
            estado_antes="DIGITADO", estado_despues="AUTORIZADO",
            snap={
                "pp_origen":  nro_pp,
                "marca":      ic_row[2] if ic_row else None,
                "pares":      pares_ic,
                "motivo":     "Desasignada manualmente desde PP",
            },
            usuario_id=usuario_id,
        )
        log_flujo(
            entidad="PP", entidad_id=pp_id, nro_registro=nro_pp,
            accion=A.DIG_IC_DESASIGNADA,
            snap={"ic_removida": nro_ic, "pares_descontados": pares_ic},
            usuario_id=usuario_id,
        )
        DBInspector.log(f"[PP] IC {nro_ic} desasignada de {nro_pp}", "SUCCESS")
        return True
    except Exception as e:
        DBInspector.log(f"[PP] Error desasignando IC {ic_id} de PP {pp_id}: {e}", "ERROR")
        return False


def guardar_configuracion_pp(
    pp_id: int,
    proforma: str | None = None,
    evento_id: int | None = None,
    usuario_id: int | None = None,
) -> bool:
    """
    Guarda la proforma y/o el evento de precio sobre el PP.
    - numero_proforma  → pedido_proveedor.numero_proforma
    - evento_id        → intencion_compra_pedido.precio_evento_id (todas las ICs del PP)
    Registra en auditoría.
    """
    try:
        with engine.begin() as conn:
            pp_row = conn.execute(sqlt(
                "SELECT numero_registro, numero_proforma FROM pedido_proveedor WHERE id=:id"
            ), {"id": pp_id}).fetchone()

            if proforma is not None:
                conn.execute(sqlt("""
                    UPDATE pedido_proveedor
                    SET numero_proforma = :pf
                    WHERE id = :pp_id
                """), {"pf": proforma.strip() or None, "pp_id": pp_id})

            if evento_id is not None:
                conn.execute(sqlt("""
                    UPDATE intencion_compra_pedido
                    SET precio_evento_id = :ev
                    WHERE pedido_proveedor_id = :pp_id
                """), {"ev": evento_id, "pp_id": pp_id})
                # También sincronizar en la IC directa (para nuevas ICs compatibles)
                conn.execute(sqlt("""
                    UPDATE intencion_compra ic
                    SET precio_evento_id = :ev
                    FROM intencion_compra_pedido icp
                    WHERE icp.intencion_compra_id = ic.id
                      AND icp.pedido_proveedor_id = :pp_id
                """), {"ev": evento_id, "pp_id": pp_id})

        nro = pp_row[0] if pp_row else str(pp_id)
        snap: dict = {}
        if proforma is not None:
            snap["proforma_anterior"] = pp_row[1] if pp_row else None
            snap["proforma_nueva"]    = proforma.strip() or None
        if evento_id is not None:
            snap["evento_precio_id"]  = evento_id
        log_flujo(
            entidad="PP", entidad_id=pp_id, nro_registro=nro,
            accion="PP_CONFIGURADO",
            snap=snap, usuario_id=usuario_id,
        )
        DBInspector.log(f"[PP] Configurado {nro}: proforma={proforma} evento={evento_id}", "SUCCESS")
        return True
    except Exception as e:
        DBInspector.log(f"[PP] Error configurando PP {pp_id}: {e}", "ERROR")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# LISTADO RIMEC ↔ PP (biblioteca + excel = precio_evento)
# ─────────────────────────────────────────────────────────────────────────────

_ESTADOS_FI_RECALC_DEFECTO = ("RESERVADA",)
_ESTADOS_FI_RECALC_CON_CONFIRMADAS = ("RESERVADA", "CONFIRMADA")
_ESTADOS_FI_NO_TOCAR = frozenset({"ANULADA", "CANCELADA"})


def get_pp_estado(pp_id: int) -> str:
    df = get_dataframe(
        "SELECT estado FROM pedido_proveedor WHERE id = :id",
        {"id": pp_id},
    )
    if df is None or df.empty:
        return ""
    return str(df["estado"].iloc[0] or "").strip().upper()


def pp_listado_precio_editable(pp_id: int) -> bool:
    """False cuando el PP ya pasó a compra legal (ENVIADO)."""
    return get_pp_estado(pp_id) != "ENVIADO"


def get_evento_precio_pp_detalle(pp_id: int) -> dict | None:
    """
    Metadatos del listado RIMEC vigente en el PP (precio_evento + biblioteca).
    """
    evento_id = get_evento_precio_pp(pp_id)
    if not evento_id:
        return None
    df = get_dataframe("""
        SELECT pe.id,
               pe.nombre_evento,
               UPPER(TRIM(pe.estado)) AS estado,
               pe.fecha_vigencia_desde,
               pe.biblioteca_precio_id,
               COUNT(pl.id) AS n_precios
        FROM precio_evento pe
        LEFT JOIN precio_lista pl ON pl.evento_id = pe.id
        WHERE pe.id = :eid
        GROUP BY pe.id, pe.nombre_evento, pe.estado,
                 pe.fecha_vigencia_desde, pe.biblioteca_precio_id
    """, {"eid": evento_id})
    if df is not None and not df.empty:
        bid = df["biblioteca_precio_id"].iloc[0]
        if bid is not None and str(bid) not in ("", "None", "nan"):
            try:
                df_bib = get_dataframe(
                    "SELECT nombre FROM biblioteca_precio WHERE id = :bid LIMIT 1",
                    {"bid": int(bid)},
                )
                if df_bib is not None and not df_bib.empty:
                    df = df.copy()
                    df["biblioteca_nombre"] = df_bib["nombre"].iloc[0]
            except Exception:
                pass
    if df is None or df.empty:
        return {"id": evento_id}
    row = df.iloc[0].to_dict()
    row["id"] = int(row["id"])
    if row.get("n_precios") is not None:
        row["n_precios"] = int(row["n_precios"])
    return row


def _factor_descuentos_fi(d1: float, d2: float, d3: float, d4: float) -> float:
    f = 1.0
    for d in (d1, d2, d3, d4):
        if d and float(d) > 0:
            f *= 1.0 - float(d)
    return f


def _lookup_lpn_evento(
    conn,
    evento_id: int,
    *,
    ppd_id: int | None = None,
    linea_id: int | None = None,
    material_id: int | None = None,
) -> float | None:
    """Resuelve LPN base (sin descuentos FI) desde precio_lista del evento."""
    if ppd_id:
        row = conn.execute(sqlt("""
            SELECT pl.lpn
            FROM pedido_proveedor_detalle ppd
            JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
            LEFT JOIN linea l ON l.proveedor_id = pp.proveedor_importacion_id
                             AND l.codigo_proveedor::text = ppd.linea
            LEFT JOIN material m ON m.proveedor_id = pp.proveedor_importacion_id
                                 AND m.codigo_proveedor::text = ppd.material_code
            LEFT JOIN LATERAL (
                SELECT lpn
                FROM precio_lista
                WHERE evento_id = :eid
                  AND (
                        (linea_id IS NOT NULL AND material_id IS NOT NULL
                         AND linea_id = l.id AND material_id = m.id)
                     OR (linea_codigo = l.id::text
                         AND material_descripcion = m.id::text)
                  )
                  AND lpn IS NOT NULL AND lpn > 0
                ORDER BY CASE WHEN linea_id IS NOT NULL THEN 0 ELSE 1 END
                LIMIT 1
            ) pl ON true
            WHERE ppd.id = :ppd
        """), {"eid": evento_id, "ppd": ppd_id}).fetchone()
        if row and row[0] is not None:
            return float(row[0])

    if linea_id and material_id:
        row = conn.execute(sqlt("""
            SELECT lpn
            FROM precio_lista
            WHERE evento_id = :eid
              AND lpn IS NOT NULL AND lpn > 0
              AND (
                    (linea_id = :lid AND material_id = :mid)
                 OR (linea_codigo = :lid::text AND material_descripcion = :mid::text)
              )
            ORDER BY CASE WHEN linea_id IS NOT NULL THEN 0 ELSE 1 END
            LIMIT 1
        """), {"eid": evento_id, "lid": linea_id, "mid": material_id}).fetchone()
        if row and row[0] is not None:
            return float(row[0])
    return None


def recalcular_facturas_internas_pp(
    pp_id: int,
    evento_id: int,
    *,
    incluir_confirmadas: bool = False,
    usuario_id: int | None = None,
) -> tuple[bool, str, dict]:
    """
    Recalcula precio_unit/subtotal/totales de FI editables del PP usando el evento dado.
    Por defecto solo RESERVADA; opcionalmente CONFIRMADA (flexibilidad operativa).
    """
    stats = {
        "fi_procesadas": 0,
        "fi_actualizadas": 0,
        "lineas_actualizadas": 0,
        "lineas_sin_precio": 0,
    }
    estados = (
        _ESTADOS_FI_RECALC_CON_CONFIRMADAS
        if incluir_confirmadas
        else _ESTADOS_FI_RECALC_DEFECTO
    )
    try:
        with engine.begin() as conn:
            fi_rows = conn.execute(sqlt("""
                SELECT id, nro_factura, estado,
                       COALESCE(descuento_1, 0) AS d1,
                       COALESCE(descuento_2, 0) AS d2,
                       COALESCE(descuento_3, 0) AS d3,
                       COALESCE(descuento_4, 0) AS d4
                FROM factura_interna
                WHERE pp_id = :pp
                  AND UPPER(TRIM(estado)) = ANY(:estados)
            """), {"pp": pp_id, "estados": list(estados)}).fetchall()

            for fi in fi_rows:
                stats["fi_procesadas"] += 1
                fi_id = int(fi.id)
                factor = _factor_descuentos_fi(fi.d1, fi.d2, fi.d3, fi.d4)

                det_rows = conn.execute(sqlt("""
                    SELECT id, pares, cajas, ppd_id,
                           linea_id, referencia_id, material_id,
                           precio_unit
                    FROM factura_interna_detalle
                    WHERE factura_id = :fi
                """), {"fi": fi_id}).fetchall()

                total_pares = 0
                total_monto = 0.0
                lineas_ok = 0
                lineas_sin = 0

                for det in det_rows:
                    pares = int(det.pares or 0)
                    lpn_base = _lookup_lpn_evento(
                        conn,
                        evento_id,
                        ppd_id=int(det.ppd_id) if det.ppd_id else None,
                        linea_id=int(det.linea_id) if det.linea_id else None,
                        material_id=int(det.material_id) if det.material_id else None,
                    )
                    if lpn_base is None or lpn_base <= 0:
                        lineas_sin += 1
                        pu = float(det.precio_unit or 0)
                    else:
                        pu = round(lpn_base * factor)
                        lineas_ok += 1

                    subtotal = round(pares * pu, 2)
                    conn.execute(sqlt("""
                        UPDATE factura_interna_detalle
                        SET precio_unit = :pu,
                            subtotal    = :st,
                            precio_neto = :pu
                        WHERE id = :id
                    """), {"pu": pu, "st": subtotal, "id": int(det.id)})
                    total_pares += pares
                    total_monto += subtotal

                if lineas_ok > 0 or det_rows:
                    conn.execute(sqlt("""
                        UPDATE factura_interna
                        SET lista_precio_id = :ev,
                            total_pares     = :tp,
                            total_monto     = :tm
                        WHERE id = :fi
                    """), {
                        "ev": evento_id,
                        "tp": total_pares,
                        "tm": round(total_monto, 2),
                        "fi": fi_id,
                    })
                    stats["fi_actualizadas"] += 1
                    stats["lineas_actualizadas"] += lineas_ok
                    stats["lineas_sin_precio"] += lineas_sin

            # Sincronizar puntero lista_precio en FI no recalculadas (p. ej. FACTURADA)
            conn.execute(sqlt("""
                UPDATE factura_interna
                SET lista_precio_id = :ev
                WHERE pp_id = :pp
                  AND UPPER(TRIM(estado)) NOT IN ('ANULADA', 'CANCELADA')
            """), {"ev": evento_id, "pp": pp_id})

        msg = (
            f"{stats['fi_actualizadas']} factura(s) recalculada(s), "
            f"{stats['lineas_actualizadas']} línea(s) con precio nuevo."
        )
        if stats["lineas_sin_precio"]:
            msg += f" {stats['lineas_sin_precio']} línea(s) sin LPN en el evento (precio anterior conservado)."

        log_flujo(
            entidad="PP",
            entidad_id=pp_id,
            nro_registro=str(pp_id),
            accion="PP_FI_RECALC_LISTADO",
            snap={"evento_id": evento_id, **stats},
            usuario_id=usuario_id,
        )
        DBInspector.log(f"[PP] Recalc FI pp={pp_id} ev={evento_id}: {stats}", "SUCCESS")
        return True, msg, stats
    except Exception as e:
        DBInspector.log(f"[PP] recalcular_facturas_internas_pp: {e}", "ERROR")
        return False, str(e), stats


def vincular_listado_precio_a_pp(
    pp_id: int,
    evento_id: int,
    *,
    recalcular_fi: bool = True,
    incluir_fi_confirmadas: bool = False,
    usuario_id: int | None = None,
) -> tuple[bool, str, dict]:
    """
    Asigna precio_evento al PP/ICs y opcionalmente recalcula facturas internas abiertas.
    """
    if not pp_listado_precio_editable(pp_id):
        return False, "El PP está en COMPRA (ENVIADO). El listado de precios no se puede cambiar.", {}

    prev = get_evento_precio_pp(pp_id)
    if not guardar_configuracion_pp(pp_id, None, evento_id, usuario_id):
        return False, "No se pudo vincular el evento al PP.", {}

    stats: dict = {"evento_anterior": prev, "evento_nuevo": evento_id}
    if recalcular_fi:
        ok, msg, rstats = recalcular_facturas_internas_pp(
            pp_id,
            evento_id,
            incluir_confirmadas=incluir_fi_confirmadas,
            usuario_id=usuario_id,
        )
        stats.update(rstats)
        if not ok:
            return False, f"Evento vinculado, pero falló el recálculo de FI: {msg}", stats
        return True, f"Listado vinculado. {msg}", stats

    return True, "Listado de precios vinculado al PP y sus ICs.", stats


def get_todos_eventos_precio() -> pd.DataFrame:
    """Todos los eventos de precio disponibles para el explorador de listas."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(sqlt("""
                SELECT pe.id, pe.nombre_evento, pe.estado, pe.fecha_vigencia_desde,
                       COUNT(pl.id) AS n_precios
                FROM precio_evento pe
                LEFT JOIN precio_lista pl ON pl.evento_id = pe.id
                GROUP BY pe.id, pe.nombre_evento, pe.estado, pe.fecha_vigencia_desde
                ORDER BY pe.created_at DESC
            """)).fetchall()
        return pd.DataFrame([dict(r._mapping) for r in rows])
    except Exception as e:
        DBInspector.log(f"[PP] get_todos_eventos_precio: {e}", "ERROR")
        return pd.DataFrame()


def get_lista_precios_completa(evento_id: int) -> pd.DataFrame:
    """
    Lista completa de precios de un evento con todo el detalle forense:
    referencia, material, línea, LPN, LPC02-04, caso aplicado, índice, dólar.
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(sqlt("""
                SELECT
                    COALESCE(l.codigo_proveedor::text, pl.linea_codigo, '—')      AS linea,
                    COALESCE(r.codigo_proveedor::text, pl.referencia_codigo, '—') AS referencia,
                    COALESCE(m.descripcion, pl.material_descripcion, '—')          AS material,
                    pl.lpn,
                    pl.lpc02,
                    pl.lpc03,
                    pl.lpc04,
                    pl.nombre_caso_aplicado AS caso,
                    pl.dolar_aplicado       AS dolar,
                    pl.indice_aplicado      AS indice
                FROM precio_lista pl
                LEFT JOIN linea      l ON l.id = pl.linea_id
                LEFT JOIN referencia r ON r.id = pl.referencia_id
                LEFT JOIN material   m ON m.id = pl.material_id
                WHERE pl.evento_id = :evento_id
                ORDER BY l.codigo_proveedor NULLS LAST,
                         r.codigo_proveedor NULLS LAST,
                         m.descripcion NULLS LAST
            """), {"evento_id": evento_id}).fetchall()
        return pd.DataFrame([dict(r._mapping) for r in rows])
    except Exception as e:
        DBInspector.log(f"[PP] get_lista_precios_completa: {e}", "ERROR")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# FACTURAS INTERNAS
# ─────────────────────────────────────────────────────────────────────────────

def _get_next_nro_fi(pp_id: int) -> str:
    """
    Genera número de Factura Interna con nomenclatura [PP_ID]-PV[NNN].
    El correlativo se resetea por cada Pedido Proveedor.
    Ejemplo: 15-PV001, 15-PV002, 16-PV001...
    """
    df = get_dataframe("""
        SELECT COALESCE(
            MAX(
                CAST(
                    REGEXP_REPLACE(nro_factura, '^[0-9]+-PV', '')
                    AS INTEGER
                )
            ),
            0
        ) + 1 AS correlativo
        FROM factura_interna
        WHERE pp_id = :pp_id
          AND nro_factura ~ '^[0-9]+-PV[0-9]+$'
    """, {"pp_id": pp_id})
    correlativo = int(df["correlativo"].iloc[0]) if df is not None and not df.empty else 1
    return f"{pp_id}-PV{correlativo:03d}"


def get_facturas_interna_de_pp(pp_id: int) -> pd.DataFrame:
    """Facturas internas asociadas a un PP — formato canónico (ver core/fi_card)."""
    return get_dataframe("""
        SELECT
            fi.id, fi.nro_factura, fi.estado, fi.created_at,
            fi.pp_id,
            pp.numero_registro        AS nro_pp,
            fi.marca, fi.marca_id,
            fi.caso,  fi.caso_id,
            cv.descp_cliente          AS cliente,
            cv.descp_cliente          AS cliente_nombre,
            vv.descp_vendedor         AS vendedor,
            vv.descp_vendedor         AS vendedor_nombre,
            fi.total_pares,
            fi.total_monto            AS total_neto,
            fi.total_monto,
            fi.lista_precio_id,
            fi.descuento_1, fi.descuento_2, fi.descuento_3, fi.descuento_4
        FROM factura_interna fi
        LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
        LEFT JOIN cliente_v2  cv ON cv.id_cliente  = fi.cliente_id
        LEFT JOIN vendedor_v2 vv ON vv.id_vendedor = fi.vendedor_id
        WHERE fi.pp_id = :pp_id
        ORDER BY fi.created_at DESC, fi.nro_factura
    """, {"pp_id": pp_id})


def get_fi_detalles_canonico(fi_id: int) -> list[dict]:
    """Detalle de items de una FI con `linea_snapshot` parseado a dict.
    Formato esperado por core/fi_card.render_fi_card()."""
    import ast as _ast
    import json as _json
    df = get_dataframe("""
        SELECT fid.id, fid.pares, fid.cajas, fid.precio_unit,
               fid.subtotal, fid.precio_neto, fid.linea_snapshot
        FROM factura_interna_detalle fid
        WHERE fid.factura_id = :fi_id
        ORDER BY fid.id
    """, {"fi_id": fi_id})
    if df is None or df.empty:
        return []
    rows = df.to_dict("records")
    for r in rows:
        snap = r.get("linea_snapshot")
        if isinstance(snap, str):
            try:
                r["linea_snapshot"] = _json.loads(snap)
            except Exception:
                try:
                    r["linea_snapshot"] = _ast.literal_eval(snap)
                except Exception:
                    r["linea_snapshot"] = {}
        elif not isinstance(snap, dict):
            r["linea_snapshot"] = {}
    return rows


def get_skus_con_precio_para_fi(pp_id: int, evento_id: int) -> pd.DataFrame:
    """
    SKUs del PPD con saldo disponible + LPN del evento de precio.
    Usados para construir el detalle de una Factura Interna.
    """
    return get_dataframe("""
        SELECT
            ppd.id                  AS ppd_id,
            ppd.linea               AS linea_codigo_proveedor,
            ppd.referencia          AS referencia_codigo_proveedor,
            ppd.descp_material      AS material,
            ppd.descp_color         AS color,
            ppd.cantidad_cajas,
            ppd.cantidad_pares      AS pares_inicial,
            COALESCE(SUM(vt.cantidad_vendida), 0) AS vendido,
            ppd.cantidad_pares - COALESCE(SUM(vt.cantidad_vendida), 0) AS saldo,
            l.id                    AS linea_id,
            ref.id                  AS referencia_id,
            m.id                    AS material_id,
            c.id                    AS color_id,
            COALESCE(pl.lpn, 0)     AS lpn
        FROM pedido_proveedor_detalle ppd
        JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        LEFT JOIN venta_transito vt ON vt.pedido_proveedor_detalle_id = ppd.id
        LEFT JOIN linea     l   ON l.proveedor_id = pp.proveedor_importacion_id
                                AND l.codigo_proveedor::TEXT = ppd.linea
        LEFT JOIN referencia ref ON ref.linea_id  = l.id
                                AND ref.codigo_proveedor::TEXT = ppd.referencia
        LEFT JOIN material   m   ON m.proveedor_id = pp.proveedor_importacion_id
                                AND m.codigo_proveedor::TEXT = ppd.material_code
        LEFT JOIN color      c   ON c.codigo_proveedor::TEXT = ppd.color_code
        LEFT JOIN precio_lista pl ON pl.evento_id = :evento_id
                                 AND pl.linea_id = l.id
                                 AND pl.referencia_id = ref.id
                                 AND pl.material_id = m.id
        WHERE ppd.pedido_proveedor_id = :pp_id
          AND ppd.linea IS NOT NULL AND ppd.linea != ''
        GROUP BY ppd.id, ppd.linea, ppd.referencia, ppd.descp_material, ppd.descp_color,
                 ppd.cantidad_cajas, ppd.cantidad_pares,
                 l.id, ref.id, m.id, c.id, pl.lpn
        HAVING ppd.cantidad_pares - COALESCE(SUM(vt.cantidad_vendida), 0) > 0
        ORDER BY ppd.linea, ppd.referencia
    """, {"pp_id": pp_id, "evento_id": evento_id})


def crear_factura_interna(
    pp_id: int,
    cliente_id: int,
    vendedor_id: int | None,
    lista_precio_id: int,
    descuento_1: float,
    descuento_2: float,
    descuento_3: float,
    descuento_4: float,
    items: list[dict],
    usuario_id: int | None = None,
) -> tuple[bool, str]:
    """
    Crea una Factura Interna con estado RESERVADA (soft-discount).
    Nomenclatura: [PP_ID]-PV[NNN] — correlativo reseteado por PP.
    """
    nro  = _get_next_nro_fi(pp_id)
    total_pares = sum(int(i.get("pares", 0)) for i in items)
    total_neto  = round(sum(float(i.get("subtotal", 0)) for i in items), 2)
    try:
        with engine.begin() as conn:
            row = conn.execute(sqlt("""
                INSERT INTO factura_interna
                    (pp_id, nro_factura, cliente_id, vendedor_id,
                     lista_precio_id, descuento_1, descuento_2, descuento_3, descuento_4,
                     total_pares, total_neto, estado)
                VALUES (:pp_id, :nro, :cli, :vend, :lp,
                        :d1, :d2, :d3, :d4, :pares, :neto, 'RESERVADA')
                RETURNING id
            """), {
                "pp_id": pp_id, "nro": nro, "cli": cliente_id,
                "vend": vendedor_id, "lp": lista_precio_id,
                "d1": descuento_1, "d2": descuento_2,
                "d3": descuento_3, "d4": descuento_4,
                "pares": total_pares, "neto": total_neto,
            }).fetchone()
            fi_id = int(row[0])
            for item in items:
                conn.execute(sqlt("""
                    INSERT INTO factura_interna_detalle
                        (factura_id, linea_id, referencia_id, material_id, color_id,
                         cajas, pares, precio_unit, subtotal)
                    VALUES (:fi, :li, :ri, :mi, :ci, :c, :p, :pu, :st)
                """), {
                    "fi": fi_id,
                    "li": item["linea_id"], "ri": item["referencia_id"],
                    "mi": item["material_id"],
                    "ci": item["color_id"] if item.get("color_id") else None,
                    "c": int(item["cajas"]), "p": int(item["pares"]),
                    "pu": float(item["precio_unit"]),
                    "st": float(item["subtotal"]),
                })
        DBInspector.log(f"[FI] Creada {nro}: {total_pares} pares · ${total_neto:,.0f}", "SUCCESS")
        return True, nro
    except Exception as e:
        DBInspector.log(f"[FI] Error creando factura interna: {e}", "ERROR")
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# ARRIBO + STOCK BAZAR
# ─────────────────────────────────────────────────────────────────────────────

def registrar_arribo(
    pp_id: int,
    fecha_arribo,
    usuario_id: int | None = None,
) -> tuple[bool, str]:
    try:
        with engine.begin() as conn:
            pp_row = conn.execute(sqlt("""
                SELECT numero_registro, estado_arribo
                FROM pedido_proveedor WHERE id = :id
            """), {"id": pp_id}).fetchone()
            if not pp_row:
                return False, "PP no encontrado."
            if pp_row.estado_arribo == "ARRIBADO":
                return False, "Este PP ya fue registrado como ARRIBADO."
            conn.execute(sqlt("""
                UPDATE pedido_proveedor
                SET estado_arribo = 'ARRIBADO', fecha_arribo = :fecha
                WHERE id = :pp_id
            """), {"fecha": fecha_arribo, "pp_id": pp_id})

        nro = pp_row.numero_registro
        log_flujo(
            entidad="PP", entidad_id=pp_id, nro_registro=nro,
            accion="PP_ARRIBADO",
            estado_antes="EN_TRANSITO", estado_despues="ARRIBADO",
            snap={"fecha_arribo": str(fecha_arribo)},
            usuario_id=usuario_id,
        )
        ok_sb, msg_sb = generar_stock_bazar(pp_id)
        if not ok_sb:
            return True, f"PP {nro} ARRIBADO — error generando stock_bazar: {msg_sb}"
        DBInspector.log(f"[ARRIBO] {nro} ARRIBADO. {msg_sb}", "SUCCESS")
        return True, f"PP {nro} registrado como ARRIBADO. {msg_sb}"
    except Exception as e:
        DBInspector.log(f"[ARRIBO] Error: {e}", "ERROR")
        return False, str(e)


def generar_stock_bazar(pp_id: int) -> tuple[bool, str]:
    """
    Toma facturas internas CONFIRMADAS del PP y genera/actualiza stock_bazar.
    Solo lo que fue VENDIDO en tránsito va a Bazar.
    Si no hay facturas, copia el PPD completo como fallback.
    """
    # Prioridad 1: desde facturas internas confirmadas (lo vendido)
    df = get_dataframe("""
        SELECT
            l.id                        AS linea_id,
            ref.id                      AS referencia_id,
            m.id                        AS material_id,
            c.id                        AS color_id,
            SUM(fid.pares)              AS pares,
            AVG(fid.precio_unit)        AS precio_venta
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id    = fi.id
        JOIN pedido_proveedor_detalle ppd ON ppd.id           = fid.ppd_id
        JOIN pedido_proveedor pp          ON pp.id            = ppd.pedido_proveedor_id
        JOIN linea      l   ON l.proveedor_id                 = pp.proveedor_importacion_id
                            AND l.codigo_proveedor::TEXT      = ppd.linea
        JOIN referencia ref ON ref.linea_id                   = l.id
                            AND ref.codigo_proveedor::TEXT    = ppd.referencia
        JOIN material   m   ON m.proveedor_id                 = pp.proveedor_importacion_id
                            AND m.codigo_proveedor::TEXT      = ppd.material_code
        LEFT JOIN color c   ON c.codigo_proveedor::TEXT       = ppd.color_code
        WHERE fi.pp_id  = :pp_id
          AND fi.estado = 'CONFIRMADA'
        GROUP BY l.id, ref.id, m.id, c.id
    """, {"pp_id": pp_id})

    # Fallback: si no hay facturas internas, copiar PPD completo
    if df is None or df.empty:
        df = get_dataframe("""
            SELECT
                l.id                    AS linea_id,
                ref.id                  AS referencia_id,
                m.id                    AS material_id,
                c.id                    AS color_id,
                ppd.cantidad_pares      AS pares,
                COALESCE(pl.lpn, 0)     AS precio_venta
            FROM pedido_proveedor_detalle ppd
            JOIN  pedido_proveedor pp  ON pp.id            = ppd.pedido_proveedor_id
            LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
            JOIN  linea      l   ON l.proveedor_id         = pp.proveedor_importacion_id
                                 AND l.codigo_proveedor::TEXT = ppd.linea
            JOIN  referencia ref ON ref.linea_id           = l.id
                                 AND ref.codigo_proveedor::TEXT = ppd.referencia
            JOIN  material   m   ON m.proveedor_id         = pp.proveedor_importacion_id
                                 AND m.codigo_proveedor::TEXT = ppd.material_code
            LEFT JOIN color  c   ON c.codigo_proveedor::TEXT = ppd.color_code
            LEFT JOIN precio_lista pl
                    ON pl.evento_id = icp.precio_evento_id
                   AND pl.linea_id = l.id
                   AND pl.referencia_id = ref.id
                   AND pl.material_id = m.id
            WHERE ppd.pedido_proveedor_id = :pp_id
              AND ppd.linea IS NOT NULL AND ppd.linea != ''
              AND ppd.cantidad_pares > 0
        """, {"pp_id": pp_id})

    if df is None or df.empty:
        return False, "No se encontraron artículos vendidos ni en PPD para este PP."

    insertados = 0
    try:
        with engine.begin() as conn:
            for _, row in df.iterrows():
                if row["linea_id"] is None or row["referencia_id"] is None or row["material_id"] is None:
                    continue
                conn.execute(sqlt("""
                    INSERT INTO stock_bazar
                        (linea_id, referencia_id, material_id, color_id,
                         cantidad, precio_venta, activo, updated_at)
                    VALUES (:li, :ri, :mi, :ci,
                            :qty, :precio, true, now())
                    ON CONFLICT ON CONSTRAINT uq_stock_bazar_pilares
                    DO UPDATE SET
                        cantidad     = stock_bazar.cantidad + EXCLUDED.cantidad,
                        precio_venta = CASE
                            WHEN EXCLUDED.precio_venta > 0 THEN EXCLUDED.precio_venta
                            ELSE stock_bazar.precio_venta
                        END,
                        updated_at   = now()
                """), {
                    "li":     int(row["linea_id"]),
                    "ri":     int(row["referencia_id"]),
                    "mi":     int(row["material_id"]),
                    "ci":     int(row["color_id"]) if row.get("color_id") and not pd.isna(row["color_id"]) else None,
                    "qty":    int(row["pares"]),
                    "precio": float(row["precio_venta"]) if row.get("precio_venta") else None,
                })
                insertados += 1
        return True, f"{insertados} SKUs escritos en stock_bazar."
    except Exception as e:
        DBInspector.log(f"[STOCK_BAZAR] Error: {e}", "ERROR")
        return False, str(e)
