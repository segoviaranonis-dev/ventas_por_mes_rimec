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
    
    print("--- V_STOCK_RIMEC SAMPLES ---")
    cur.execute("SELECT marca_id, marca, linea_id, linea_codigo, grupo_estilo_id, estilo FROM v_stock_rimec LIMIT 10")
    rows = cur.fetchall()
    for r in rows:
        print(r)
        
    print("\n--- LINEAS WITHOUT GENDER ---")
    cur.execute("SELECT id, codigo_proveedor, genero_id FROM linea WHERE id IN (SELECT DISTINCT linea_id FROM v_stock_rimec) AND genero_id IS NULL")
    print(cur.fetchall())
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
