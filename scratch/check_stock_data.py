import os
import psycopg2
from psycopg2.extras import RealDictCursor
import tomllib

def check_stock_data():
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
        
        print("\n--- pedido_proveedor_detalle COUNT ---")
        cur.execute("SELECT count(*) FROM pedido_proveedor_detalle")
        print(f"Total: {cur.fetchone()['count']}")
        
        print("\n--- movimiento COUNT (Confirmed) ---")
        cur.execute("SELECT count(*) FROM movimiento WHERE estado = 'CONFIRMADO'")
        print(f"Total: {cur.fetchone()['count']}")

        print("\n--- movimiento_detalle COUNT ---")
        cur.execute("SELECT count(*) FROM movimiento_detalle")
        print(f"Total: {cur.fetchone()['count']}")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    check_stock_data()
