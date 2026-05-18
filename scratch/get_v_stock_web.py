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
    cur.execute("SELECT view_definition FROM information_schema.views WHERE table_name = 'v_stock_web'")
    view_def = cur.fetchone()[0]
    print(view_def)
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
