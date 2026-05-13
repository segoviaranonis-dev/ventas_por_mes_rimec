import pandas as pd
from core.database import get_dataframe

ALM_WEB_01 = 1


def get_stock_web() -> pd.DataFrame:
    """
    Stock real en ALM_WEB_01 agrupado por Marca + 5 Pilares + Talla.
    La marca se obtiene desde snapshot_json del traspaso vinculado.
    """
    # OT-2026-020: Usar nombres correctos post-migración 004
    return get_dataframe("""
        SELECT
            COALESCE(mv.descp_marca, '—')        AS marca,
            l.codigo_proveedor                   AS linea,
            r.codigo_proveedor                   AS referencia,
            COALESCE(mat.descripcion, '—')       AS material,
            COALESCE(col.nombre, '—')            AS color,
            tl.talla_etiqueta                    AS talla,
            SUM(md.cantidad * md.signo)          AS stock
        FROM movimiento_detalle md
        JOIN movimiento m   ON m.id = md.movimiento_id
        JOIN traspaso   tr  ON tr.numero_registro = m.documento_ref
        LEFT JOIN marca_v2 mv ON mv.id_marca = (tr.snapshot_json->>'id_marca')::int
        JOIN combinacion c  ON c.id = md.combinacion_id
        JOIN linea       l  ON l.id = c.linea_id
        JOIN referencia  r  ON r.id = c.referencia_id
        LEFT JOIN material  mat ON mat.id = c.material_id
        LEFT JOIN color     col ON col.id = c.color_id
        JOIN talla       tl ON tl.id = c.talla_id
        WHERE m.almacen_destino_id = :alm
          AND m.estado = 'CONFIRMADO'
          AND m.tipo = 'INGRESO_COMPRA'
        GROUP BY mv.descp_marca, l.codigo_proveedor, r.codigo_proveedor, mat.descripcion, col.nombre, tl.talla_etiqueta
        HAVING SUM(md.cantidad * md.signo) > 0
        ORDER BY mv.descp_marca, l.codigo_proveedor, r.codigo_proveedor, tl.talla_etiqueta
    """, {"alm": ALM_WEB_01})


def get_resumen_web() -> pd.DataFrame:
    """Resumen por Marca + Línea + Referencia (sin talla) para vista agrupada."""
    # OT-2026-020: Usar nombres correctos post-migración 004
    return get_dataframe("""
        SELECT
            COALESCE(mv.descp_marca, '—')        AS marca,
            l.codigo_proveedor                   AS linea,
            r.codigo_proveedor                   AS referencia,
            COALESCE(mat.descripcion, '—')       AS material,
            COALESCE(col.nombre, '—')            AS color,
            SUM(md.cantidad * md.signo)          AS stock_total
        FROM movimiento_detalle md
        JOIN movimiento m   ON m.id = md.movimiento_id
        JOIN traspaso   tr  ON tr.numero_registro = m.documento_ref
        LEFT JOIN marca_v2 mv ON mv.id_marca = (tr.snapshot_json->>'id_marca')::int
        JOIN combinacion c  ON c.id = md.combinacion_id
        JOIN linea      l   ON l.id = c.linea_id
        JOIN referencia r   ON r.id = c.referencia_id
        LEFT JOIN material  mat ON mat.id = c.material_id
        LEFT JOIN color     col ON col.id = c.color_id
        WHERE m.almacen_destino_id = :alm
          AND m.estado = 'CONFIRMADO'
          AND m.tipo = 'INGRESO_COMPRA'
        GROUP BY mv.descp_marca, l.codigo_proveedor, r.codigo_proveedor, mat.descripcion, col.nombre
        HAVING SUM(md.cantidad * md.signo) > 0
        ORDER BY mv.descp_marca, l.codigo_proveedor, r.codigo_proveedor
    """, {"alm": ALM_WEB_01})
