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
    
    print("--- LINEA TABLE ---")
    cur.execute("SELECT id, codigo_proveedor FROM linea WHERE codigo_proveedor = '2126' OR id = 2126")
    print(cur.fetchall())
    
    print("\n--- LINEA_REFERENCIA TABLE ---")
    cur.execute("SELECT linea_id, referencia_id FROM linea_referencia WHERE linea_id = 2126 OR linea_id IN (SELECT id FROM linea WHERE codigo_proveedor = '2126') LIMIT 5")
    print(cur.fetchall())
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
