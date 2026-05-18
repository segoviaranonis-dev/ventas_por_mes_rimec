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
    
    print("--- PROFORMA_DETALLE COUNT ---")
    cur.execute("SELECT count(*) FROM proforma_detalle")
    print(cur.fetchone()[0])
    
    print("\n--- PEDIDO_PROVEEDOR_DETALLE COUNT ---")
    cur.execute("SELECT count(*) FROM pedido_proveedor_detalle")
    print(cur.fetchone()[0])
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
