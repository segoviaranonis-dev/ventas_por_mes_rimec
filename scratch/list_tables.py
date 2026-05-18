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
    
    print("--- TABLES ---")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = cur.fetchall()
    for t in tables:
        print(t[0])
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
