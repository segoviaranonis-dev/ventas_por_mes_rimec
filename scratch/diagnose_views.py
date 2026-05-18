import os
import psycopg2
from psycopg2.extras import RealDictCursor
import tomllib

def check_views():
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
        
        views = ['v_stock_rimec', 'v_stock_web']
        
        for view in views:
            print(f"\n--- Checking {view} ---")
            try:
                cur.execute(f"SELECT count(*) FROM {view}")
                count = cur.fetchone()['count']
                print(f"Row count: {count}")
                
                cur.execute(f"SELECT * FROM {view} LIMIT 1")
                row = cur.fetchone()
                if row:
                    print(f"Columns: {list(row.keys())}")
                else:
                    print("No rows found.")
            except Exception as e:
                print(f"Error checking {view}: {e}")
                conn.rollback()
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    check_views()
