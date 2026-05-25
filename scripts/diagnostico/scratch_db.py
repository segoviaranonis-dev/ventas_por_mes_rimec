import sys
from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

with engine.connect() as conn:
    print("Columns for pedido_proveedor:")
    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'pedido_proveedor'")).fetchall()
    print([r[0] for r in res])

    print("\nColumns for precio_lista:")
    res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'precio_lista'")).fetchall()
    print([r[0] for r in res])
