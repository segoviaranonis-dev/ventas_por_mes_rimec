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
    
    print("--- GENEROS ---")
    cur.execute("SELECT id, codigo, descripcion FROM genero")
    print(cur.fetchall())
    
    print("\n--- LINEA TABLE (Samples) ---")
    cur.execute("SELECT id, codigo_proveedor, genero_id FROM linea LIMIT 5")
    print(cur.fetchall())
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
