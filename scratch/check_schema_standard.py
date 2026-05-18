import psycopg2

conn_params = {
    "host": "aws-1-sa-east-1.pooler.supabase.com",
    "port": 6543,
    "database": "postgres",
    "user": "postgres.extrlcvcgypwazxipvqm",
    "password": "IJoFJbT8Qj0Q0w5m"
}

def get_columns(table_name):
    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'")
        cols = cur.fetchall()
        cur.close()
        conn.close()
        return cols
    except Exception as e:
        return f"Error: {e}"

tables = ['producto_v2', 'linea', 'v_stock_web', 'v_stock_rimec']
for t in tables:
    print(f"--- {t} ---")
    print(get_columns(t))
