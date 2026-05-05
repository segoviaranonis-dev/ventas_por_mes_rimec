import pandas as pd
from sqlalchemy import text as sqlt

from core.database import get_dataframe, engine
from modules.compra_legal.logic import crear_traspaso_por_factura

ALM_TRANSITO  = 3
ALM_WEB_BAZAR = 1


# ─────────────────────────────────────────────────────────────────────────────
# FACTURAS INTERNAS — vista principal de Facturación
# ─────────────────────────────────────────────────────────────────────────────

def get_facturas(id_cl: int | None = None) -> pd.DataFrame:
    """
    Lista de FAC-INTs con su estado de traspaso actual.
    Opcional: filtrar por compra_legal_id.
    """
    # Candado: solo FAC-INTs de PPs cuya Compra fue explícitamente distribuida
    params: dict = {}
    if id_cl is not None:
        filtro = """
            AND vt.pedido_proveedor_id IN (
                SELECT clp.pedido_proveedor_id
                FROM compra_legal_pedido clp
                JOIN compra_legal cl ON cl.id = clp.compra_legal_id
                WHERE clp.compra_legal_id = :id_cl
                  AND cl.estado IN ('DISTRIBUIDA', 'CERRADA')
            )
        """
        params["id_cl"] = id_cl
    else:
        filtro = """
            AND vt.pedido_proveedor_id IN (
                SELECT clp.pedido_proveedor_id
                FROM compra_legal_pedido clp
                JOIN compra_legal cl ON cl.id = clp.compra_legal_id
                WHERE cl.estado IN ('DISTRIBUIDA', 'CERRADA')
            )
        """

    return get_dataframe(f"""
        SELECT
            vt.numero_factura_interna                       AS factura,
            pp.numero_registro                              AS pedido,
            pp.numero_proforma                              AS proforma,
            COALESCE(mv.descp_marca, '—')                  AS marca,
            MIN(vt.fecha_operacion)                        AS fecha,
            COALESCE(cv.descp_cliente, vt.codigo_cliente)  AS cliente,
            vt.codigo_cliente,
            SUM(vt.cantidad_vendida)                       AS pares,
            COALESCE(cl.numero_registro, '—')              AS compra,
            COALESCE(cl.id::text, '')                      AS compra_id,
            COALESCE(
                (SELECT t.estado
                 FROM traspaso t
                 WHERE t.documento_ref = vt.numero_factura_interna
                 LIMIT 1),
                'SIN_TRASPASO'
            )                                              AS traspaso_estado,
            COALESCE(
                (SELECT t.id
                 FROM traspaso t
                 WHERE t.documento_ref = vt.numero_factura_interna
                 LIMIT 1),
                NULL
            )                                              AS traspaso_id
        FROM venta_transito vt
        JOIN pedido_proveedor pp
          ON pp.id = vt.pedido_proveedor_id
        JOIN pedido_proveedor_detalle ppd
          ON ppd.id = vt.pedido_proveedor_detalle_id
        LEFT JOIN marca_v2   mv  ON mv.id_marca          = ppd.id_marca
        LEFT JOIN cliente_v2 cv  ON cv.id_cliente::text  = vt.codigo_cliente
        LEFT JOIN compra_legal_pedido clp
          ON clp.pedido_proveedor_id = vt.pedido_proveedor_id
        LEFT JOIN compra_legal cl ON cl.id = clp.compra_legal_id
        WHERE 1=1 {filtro}
        GROUP BY
            vt.numero_factura_interna, pp.numero_registro, pp.numero_proforma,
            mv.descp_marca, vt.codigo_cliente, cv.descp_cliente,
            cl.numero_registro, cl.id
        ORDER BY fecha DESC, vt.numero_factura_interna
    """, params if params else None)


# ─────────────────────────────────────────────────────────────────────────────
# ENVIAR A WEB BAZAR — por factura individual
# ─────────────────────────────────────────────────────────────────────────────

def enviar_factura_a_bazar(numero_factura: str) -> tuple[bool, str]:
    """
    Acción manual "🚀 ENVIAR A WEB BAZAR" por FAC-INT:
      1. Si no existe traspaso → lo crea (BORRADOR) desde los datos de venta_transito.
      2. Cambia traspaso BORRADOR → ENVIADO.
    Después de esto, COMPRA WEB puede confirmar recepción.
    """
    try:
        with engine.begin() as conn:
            # Verificar si ya existe traspaso para esta factura
            trp_row = conn.execute(sqlt("""
                SELECT id, estado FROM traspaso
                WHERE documento_ref = :factura
                LIMIT 1
            """), {"factura": numero_factura}).fetchone()

            if trp_row:
                trp_id, trp_estado = int(trp_row[0]), str(trp_row[1])
                if trp_estado == "ENVIADO":
                    return False, "Ya fue enviado a Web Bazar (estado: ENVIADO)."
                if trp_estado == "CONFIRMADO":
                    return False, "Ya fue confirmado por Web Bazar (estado: CONFIRMADO)."
                # BORRADOR → ENVIADO
                conn.execute(sqlt("""
                    UPDATE traspaso SET estado = 'ENVIADO'
                    WHERE id = :trp_id
                """), {"trp_id": trp_id})
                return True, f"Traspaso {trp_id} enviado a Web Bazar."

            # No existe traspaso — crear desde venta_transito
            rows = conn.execute(sqlt("""
                SELECT
                    ppd.linea, ppd.referencia,
                    ppd.id_material, ppd.id_color,
                    ppd.descp_material, ppd.descp_color,
                    vt.t33, vt.t34, vt.t35, vt.t36,
                    vt.t37, vt.t38, vt.t39, vt.t40,
                    vt.pedido_proveedor_id,
                    ppd.id_marca
                FROM venta_transito vt
                JOIN pedido_proveedor_detalle ppd
                  ON ppd.id = vt.pedido_proveedor_detalle_id
                WHERE vt.numero_factura_interna = :factura
            """), {"factura": numero_factura}).fetchall()

            if not rows:
                return False, "No se encontraron líneas para esta factura."

            id_pp    = int(rows[0][14])
            id_marca = int(rows[0][15] or 0)
            items_tallas = []
            for r in rows:
                tallas = {f"t{t}": int(r[6 + (t - 33)] or 0) for t in range(33, 41)}
                items_tallas.append({
                    "linea":       r[0] or "",
                    "referencia":  r[1] or "",
                    "id_material": int(r[2] or 0),
                    "id_color":    int(r[3] or 0),
                    "material":    r[4] or "",
                    "color":       r[5] or "",
                    "tallas":      {k: v for k, v in tallas.items() if v > 0},
                })

            trp_id = crear_traspaso_por_factura(
                conn, id_pp, id_marca, numero_factura, items_tallas
            )
            conn.execute(sqlt("""
                UPDATE traspaso SET estado = 'ENVIADO' WHERE id = :trp_id
            """), {"trp_id": trp_id})

        return True, f"Traspaso TRP creado y enviado a Web Bazar."
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# DETALLE DE FACTURA — 5 Pilares + Tallas
# ─────────────────────────────────────────────────────────────────────────────

def get_factura_lineas(numero_factura: str) -> pd.DataFrame:
    """
    Detalle completo de una FAC-INT: 5 Pilares (Línea, Ref., Material, Color, Talla)
    + Grada + distribución t33-t40 + total pares.
    """
    return get_dataframe("""
        SELECT
            ppd.linea,
            ppd.referencia,
            ppd.descp_material                  AS material,
            ppd.descp_color                     AS color,
            ppd.grada,
            SUM(vt.t33) AS t33, SUM(vt.t34) AS t34,
            SUM(vt.t35) AS t35, SUM(vt.t36) AS t36,
            SUM(vt.t37) AS t37, SUM(vt.t38) AS t38,
            SUM(vt.t39) AS t39, SUM(vt.t40) AS t40,
            SUM(vt.cantidad_vendida)            AS pares
        FROM venta_transito vt
        JOIN pedido_proveedor_detalle ppd ON ppd.id = vt.pedido_proveedor_detalle_id
        WHERE vt.numero_factura_interna = :factura
        GROUP BY ppd.linea, ppd.referencia, ppd.descp_material,
                 ppd.descp_color, ppd.grada
        ORDER BY ppd.linea, ppd.referencia
    """, {"factura": numero_factura})


# ─────────────────────────────────────────────────────────────────────────────
# CARGA MANUAL — nueva FAC-INT desde saldo depósito para Cliente 5000
# ─────────────────────────────────────────────────────────────────────────────

def get_pps_con_saldo() -> pd.DataFrame:
    """PPs que tienen saldo disponible para Carga Manual."""
    return get_dataframe("""
        SELECT DISTINCT
            pp.id,
            pp.numero_registro,
            pp.numero_proforma,
            COALESCE(mv.descp_marca, '—') AS marcas,
            SUM(ppd.cantidad_pares) - COALESCE(
                (SELECT SUM(vt.cantidad_vendida)
                 FROM venta_transito vt
                 WHERE vt.pedido_proveedor_id = pp.id),
                0
            ) AS saldo_total
        FROM pedido_proveedor pp
        JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
        LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
        WHERE ppd.cantidad_pares > 0
        GROUP BY pp.id, pp.numero_registro, pp.numero_proforma, mv.descp_marca
        HAVING SUM(ppd.cantidad_pares) - COALESCE(
            (SELECT SUM(vt.cantidad_vendida)
             FROM venta_transito vt
             WHERE vt.pedido_proveedor_id = pp.id),
            0
        ) > 0
        ORDER BY pp.id DESC
    """)


def get_skus_con_saldo(id_pp: int) -> pd.DataFrame:
    """SKUs con saldo > 0 para un PP dado (Carga Manual)."""
    return get_dataframe("""
        SELECT
            ppd.id                          AS det_id,
            ppd.linea,
            ppd.referencia,
            ppd.descp_material              AS material,
            ppd.descp_color                 AS color,
            ppd.cantidad_cajas,
            ppd.cantidad_pares              AS cantidad_inicial,
            COALESCE(
                (SELECT SUM(vt.cantidad_vendida)
                 FROM venta_transito vt
                 WHERE vt.pedido_proveedor_detalle_id = ppd.id),
                0
            )                               AS vendido,
            ppd.cantidad_pares - COALESCE(
                (SELECT SUM(vt.cantidad_vendida)
                 FROM venta_transito vt
                 WHERE vt.pedido_proveedor_detalle_id = ppd.id),
                0
            )                               AS saldo,
            ppd.id_marca
        FROM pedido_proveedor_detalle ppd
        WHERE ppd.pedido_proveedor_id = :id_pp
          AND ppd.cantidad_pares > 0
        HAVING ppd.cantidad_pares - COALESCE(
            (SELECT SUM(vt.cantidad_vendida)
             FROM venta_transito vt
             WHERE vt.pedido_proveedor_detalle_id = ppd.id),
            0
        ) > 0
        ORDER BY ppd.linea, ppd.referencia
    """, {"id_pp": id_pp})


def save_carga_manual(
    id_pp:       int,
    id_marca:    int,
    cod_cliente: str,
    items: list[dict],   # [{"det_id": int, "n_pares": int, "sku": dict}]
) -> tuple[bool, str]:
    """
    Crea un FAC-INT en venta_transito desde el Módulo Facturación.
    Lógica idéntica a save_factura_manual del Pedido Proveedor.
    """
    from modules.pedido_proveedor.logic import save_factura_manual
    # Reutilizar: id_vendedor=None, id_plazo fijo=1 (contado)
    items_fmt = [
        {"det_id": it["det_id"], "n_cajas": it["n_cajas"], "sku": it["sku"]}
        for it in items
    ]
    return save_factura_manual(
        id_pp=id_pp,
        id_marca=id_marca,
        cod_cliente=str(cod_cliente).strip(),
        id_vendedor=None,
        id_plazo=1,
        items=items_fmt,
    )
