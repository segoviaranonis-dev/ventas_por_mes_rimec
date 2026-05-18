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
    
    print("--- venta_transito COUNT ---")
    cur.execute("SELECT count(*) FROM venta_transito")
    print(cur.fetchone()[0])
    
    print("\n--- v_stock_web COUNT ---")
    cur.execute("SELECT count(*) FROM v_stock_web")
    print(cur.fetchone()[0])
    
    print("\n--- v_stock_rimec COUNT ---")
    cur.execute("SELECT count(*) FROM v_stock_rimec")
    print(cur.fetchone()[0])
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
