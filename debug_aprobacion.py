import psycopg2

conn = psycopg2.connect(
    host="aws-1-sa-east-1.pooler.supabase.com", port=6543,
    dbname="postgres", user="postgres.extrlcvcgypwazxipvqm",
    password="IJoFJbT8Qj0Q0w5m", sslmode="require"
)
cur = conn.cursor()

# 1. Ver estructura real de PPD
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'pedido_proveedor_detalle'
    ORDER BY ordinal_position
""")
print("=== COLUMNAS PPD ===")
for r in cur.fetchall(): print(f"  {r[0]:30s} {r[1]}")

# 2. Ver primeras filas reales del PP-0001
cur.execute("""
    SELECT * FROM pedido_proveedor_detalle
    WHERE pedido_proveedor_id = 1
    LIMIT 5
""")
cols = [d[0] for d in cur.description]
print(f"\n=== PPD FILAS PP_ID=1 ===")
print("  " + " | ".join(cols))
for r in cur.fetchall(): print(f"  {r}")

# 3. Ver pedido_venta_rimec pendiente
cur.execute("""
    SELECT id, nro_pedido, estado, payload_json::text
    FROM pedido_venta_rimec
    WHERE estado = 'PENDIENTE'
    LIMIT 1
""")
row = cur.fetchone()
if row:
    print(f"\n=== PEDIDO PENDIENTE ===")
    print(f"  id={row[0]} nro={row[1]} estado={row[2]}")
    import json
    payload = json.loads(row[3])
    lotes = payload.get('lotes', [])
    for lote in lotes:
        for marca in lote.get('marcas', []):
            for item in marca.get('items', [])[:2]:
                print(f"  ITEM: {list(item.keys())}")
                print(f"    linea_cod={item.get('linea_cod')} ref_cod={item.get('ref_cod')} pp_id={item.get('pp_id')}")

cur.close(); conn.close()
