"""
Check PP-2026-0001 current state for smoke test preparation
"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Check PP-2026-0001
cur.execute("""
    SELECT pp.id, pp.numero_registro,
           SUM(ppd.cantidad_pares) AS total_pares,
           SUM(ppd.cantidad_cajas) AS total_cajas
    FROM pedido_proveedor pp
    LEFT JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
    WHERE pp.numero_registro = %s
    GROUP BY pp.id, pp.numero_registro
""", ("PP-2026-0001",))

pp_row = cur.fetchone()
if pp_row:
    print(f"PP: {pp_row[1]}, id={pp_row[0]}")
    print(f"  Total pares: {pp_row[2]}")
    print(f"  Total cajas: {pp_row[3]}")
    pp_id = pp_row[0]

    # Check precio_evento_id
    cur.execute("""
        SELECT precio_evento_id
        FROM intencion_compra_pedido
        WHERE pedido_proveedor_id = %s
        LIMIT 1
    """, (pp_id,))
    ev_row = cur.fetchone()
    print(f"  precio_evento_id: {ev_row[0] if ev_row else None}")

    # Check FI
    cur.execute("""
        SELECT fi.id, fi.nro_factura, fi.estado,
               SUM(fid.pares) AS pares_fi
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        WHERE fi.pp_id = %s
        GROUP BY fi.id, fi.nro_factura, fi.estado
        ORDER BY fi.id
    """, (pp_id,))

    fi_rows = cur.fetchall()
    if fi_rows:
        print(f"  Facturas Internas ({len(fi_rows)}):")
        for fi in fi_rows:
            print(f"    {fi[1]} (id={fi[0]}) - {fi[2]} - {fi[3]} pares")
    else:
        print("  Sin facturas internas")
else:
    print("PP-2026-0001 not found")

cur.close()
conn.close()
