import os
import psycopg2
from psycopg2.extras import RealDictCursor
import tomllib

def check_orders():
    try:
        with open(".streamlit/secrets.toml", "rb") as f:
            secrets = tomllib.load(f)
        
        db_cfg = secrets["postgres"]
        conn = psycopg2.connect(
            host=db_cfg["host"],
            port=db_cfg["port"],
            dbname=db_cfg["dbname"],
            user=db_cfg["user"],
            password=db_cfg["password"]
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n--- Order Status Counts ---")
        cur.execute("SELECT estado, count(*) FROM pedido_proveedor GROUP BY estado")
        for row in cur.fetchall():
            print(f"{row['estado']}: {row['count']}")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    check_orders()
