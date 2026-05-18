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
    
    print("Applying GRANTS to v_stock_rimec...")
    cur.execute("GRANT SELECT ON v_stock_rimec TO anon")
    cur.execute("GRANT SELECT ON v_stock_rimec TO authenticated")
    cur.execute("GRANT SELECT ON v_stock_rimec TO service_role")
    
    print("Checking row count in v_stock_rimec...")
    cur.execute("SELECT count(*) FROM v_stock_rimec")
    count = cur.fetchone()[0]
    print(f"Row count: {count}")
    
    conn.commit()
    cur.close()
    conn.close()
    print("DONE.")
except Exception as e:
    print(f"Error: {e}")
