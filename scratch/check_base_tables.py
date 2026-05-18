import os
import psycopg2
from psycopg2.extras import RealDictCursor
import tomllib

def check_tables():
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
        
        tables = ['linea_referencia', 'proforma_detalle', 'producto_v2', 'linea', 'marca']
        
        for table in tables:
            print(f"\n--- Checking {table} ---")
            try:
                cur.execute(f"SELECT count(*) FROM {table}")
                count = cur.fetchone()['count']
                print(f"Row count: {count}")
                
                cur.execute(f"SELECT * FROM {table} LIMIT 1")
                row = cur.fetchone()
                if row:
                    print(f"Columns: {list(row.keys())}")
            except Exception as e:
                print(f"Error checking {table}: {e}")
                conn.rollback()
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    check_tables()
