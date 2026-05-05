import pandas as pd
from core.database import get_dataframe

# Candado: solo compras que el usuario finalizó explícitamente
_ESTADOS_DISTRIBUIDOS = ("'DISTRIBUIDA'", "'CERRADA'")
_ESTADOS_SQL = ", ".join(_ESTADOS_DISTRIBUIDOS)


def get_stock_deposito(id_cl: int | None = None) -> pd.DataFrame:
    """
    Stock físico RIMEC: Compra Inicial - Venta Tránsito, por unidad de stock.
    Cada fila = un ppd único (PP + Línea + Ref + Material + Color + Grada).
    Dos cajas del mismo artículo pero diferente gradación aparecen como filas
    separadas — NUNCA se fusionan.
    SOLO muestra artículos cuyo PP pertenece a una Compra ya distribuida.
    """
    params: dict = {}

    if id_cl is not None:
        filtro = """
            AND ppd.pedido_proveedor_id IN (
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
            AND ppd.pedido_proveedor_id IN (
                SELECT clp.pedido_proveedor_id
                FROM compra_legal_pedido clp
                JOIN compra_legal cl ON cl.id = clp.compra_legal_id
                WHERE cl.estado IN ('DISTRIBUIDA', 'CERRADA')
            )
        """

    return get_dataframe(f"""
        SELECT ppd_id, marca, pedido, linea, referencia, material, color, grada,
               cantidad_inicial, vendido, saldo
        FROM (
            SELECT
                ppd.id                          AS ppd_id,
                COALESCE(mv.descp_marca, '—')   AS marca,
                pp.numero_registro               AS pedido,
                ppd.linea,
                ppd.referencia,
                ppd.descp_material               AS material,
                ppd.descp_color                  AS color,
                ppd.grada,
                ppd.cantidad_pares               AS cantidad_inicial,
                COALESCE(
                    (SELECT SUM(vt.cantidad_vendida)
                     FROM venta_transito vt
                     WHERE vt.pedido_proveedor_detalle_id = ppd.id),
                    0
                )                                AS vendido,
                ppd.cantidad_pares - COALESCE(
                    (SELECT SUM(vt.cantidad_vendida)
                     FROM venta_transito vt
                     WHERE vt.pedido_proveedor_detalle_id = ppd.id),
                    0
                )                                AS saldo
            FROM pedido_proveedor_detalle ppd
            JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
            LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
            WHERE ppd.linea IS NOT NULL
              AND ppd.cantidad_pares > 0
              {filtro}
        ) sub
        WHERE saldo > 0
        ORDER BY marca, pedido, linea, referencia, material, color, grada
    """, params if params else None)


def get_stock_deposito_tallas(id_cl: int | None = None) -> pd.DataFrame:
    """
    Stock físico RIMEC a nivel talla (saldo = ppd.tXX - SUM(vt.tXX)).
    Mismos filtros que get_stock_deposito.
    Columnas: marca, pedido, linea, referencia, material, color, grada,
              t33-t40, saldo
    """
    params: dict = {}
    if id_cl is not None:
        filtro = """
            AND ppd.pedido_proveedor_id IN (
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
            AND ppd.pedido_proveedor_id IN (
                SELECT clp.pedido_proveedor_id
                FROM compra_legal_pedido clp
                JOIN compra_legal cl ON cl.id = clp.compra_legal_id
                WHERE cl.estado IN ('DISTRIBUIDA', 'CERRADA')
            )
        """

    return get_dataframe(f"""
        SELECT
            ppd.id                                       AS ppd_id,
            COALESCE(mv.descp_marca, '—')                AS marca,
            pp.numero_registro                            AS pedido,
            ppd.linea,
            ppd.referencia,
            ppd.descp_material                            AS material,
            ppd.descp_color                               AS color,
            ppd.grada,
            GREATEST(ppd.t33 - COALESCE(sv.t33, 0), 0)  AS t33,
            GREATEST(ppd.t34 - COALESCE(sv.t34, 0), 0)  AS t34,
            GREATEST(ppd.t35 - COALESCE(sv.t35, 0), 0)  AS t35,
            GREATEST(ppd.t36 - COALESCE(sv.t36, 0), 0)  AS t36,
            GREATEST(ppd.t37 - COALESCE(sv.t37, 0), 0)  AS t37,
            GREATEST(ppd.t38 - COALESCE(sv.t38, 0), 0)  AS t38,
            GREATEST(ppd.t39 - COALESCE(sv.t39, 0), 0)  AS t39,
            GREATEST(ppd.t40 - COALESCE(sv.t40, 0), 0)  AS t40,
            ppd.cantidad_pares - COALESCE(sv.total, 0)   AS saldo
        FROM pedido_proveedor_detalle ppd
        JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
        LEFT JOIN (
            SELECT pedido_proveedor_detalle_id,
                   SUM(t33) AS t33, SUM(t34) AS t34,
                   SUM(t35) AS t35, SUM(t36) AS t36,
                   SUM(t37) AS t37, SUM(t38) AS t38,
                   SUM(t39) AS t39, SUM(t40) AS t40,
                   SUM(cantidad_vendida) AS total
            FROM venta_transito
            GROUP BY pedido_proveedor_detalle_id
        ) sv ON sv.pedido_proveedor_detalle_id = ppd.id
        WHERE ppd.linea IS NOT NULL
          AND ppd.cantidad_pares > 0
          {filtro}
          AND (ppd.cantidad_pares - COALESCE(sv.total, 0)) > 0
        ORDER BY marca, pedido, ppd.linea, ppd.referencia, ppd.descp_material,
                 ppd.descp_color, ppd.grada, ppd.id
    """, params if params else None)


def get_compras_distribuidas() -> pd.DataFrame:
    """Solo compras ya distribuidas — para el filtro selector del Depósito."""
    return get_dataframe("""
        SELECT id, numero_registro, estado
        FROM compra_legal
        WHERE estado IN ('DISTRIBUIDA', 'CERRADA')
        ORDER BY id DESC
    """)
