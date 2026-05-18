import json
from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

with engine.begin() as conn:
    # 1. Update the view v_stock_web
    conn.execute(text("""
    CREATE OR REPLACE VIEW v_stock_web_new AS
    SELECT v.*, 
           mat.codigo_proveedor AS material_code, 
           col.codigo_proveedor AS color_code
    FROM v_stock_web v
    JOIN combinacion c ON c.id = v.combinacion_id
    JOIN material mat ON mat.id = c.material_id
    JOIN color col ON col.id = c.color_id;
    """))

print("Created v_stock_web_new view")
