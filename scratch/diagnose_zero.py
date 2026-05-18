import psycopg2

conn_params = {
    "host": "aws-1-sa-east-1.pooler.supabase.com",
    "port": 6543,
    "database": "postgres",
    "user": "postgres.extrlcvcgypwazxipvqm",
    "password": "IJoFJbT8Qj0Q0w5m"
}

try:
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()
    
    print("--- PEDIDO_PROVEEDOR STATES ---")
    cur.execute("SELECT estado, count(*) FROM pedido_proveedor GROUP BY estado")
    print(cur.fetchall())
    
    print("\n--- PEDIDO_PROVEEDOR_DETALLE SAMPLE ---")
    cur.execute("SELECT id, pedido_proveedor_id, linea, referencia, cantidad_pares FROM pedido_proveedor_detalle LIMIT 5")
    print(cur.fetchall())
    
    print("\n--- CHECKING JOIN ---")
    cur.execute("SELECT count(*) FROM pedido_proveedor_detalle ppd JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id")
    print(f"Total rows with valid join: {cur.fetchone()[0]}")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
