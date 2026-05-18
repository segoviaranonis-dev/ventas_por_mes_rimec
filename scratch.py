import psycopg2
import os

try:
    with open('.streamlit/secrets.toml', 'r') as f:
        content = f.read()
        
    url = ""
    for line in content.split('\n'):
        if 'url =' in line or 'url=' in line:
            url = line.split('=')[1].strip().strip('"').strip("'")
            break
            
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'v_stock_rimec'")
    columns = [row[0] for row in cur.fetchall()]
    print("v_stock_rimec columns:", columns)
    
except Exception as e:
    print(e)
