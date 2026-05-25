import sys
from sqlalchemy import create_engine, text
import pandas as pd

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

query = """
        SELECT
            td.id,
            l.codigo_proveedor   AS linea,
            r.codigo_proveedor   AS referencia,
            COALESCE(pl.nombre_caso_aplicado, '—') AS caso_nombre
        FROM traspaso_detalle td
        JOIN combinacion c  ON c.id  = td.combinacion_id
        JOIN linea       l  ON l.id  = c.linea_id
        JOIN referencia  r  ON r.id  = c.referencia_id
        JOIN talla       tl ON tl.id = c.talla_id
        LEFT JOIN traspaso t ON t.id = td.traspaso_id
        LEFT JOIN factura_interna fi ON fi.nro_factura = t.documento_ref
        LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
        LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
        LEFT JOIN precio_lista pl ON pl.evento_id = icp.precio_evento_id
            AND pl.linea_codigo = l.codigo_proveedor::text
            AND pl.referencia_codigo = r.codigo_proveedor::text
        WHERE td.traspaso_id = 16
        LIMIT 5
"""

with engine.connect() as conn:
    res = conn.execute(text(query)).fetchall()
    for r in res:
        print(r)
