import sys
from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

with engine.connect() as conn:
    print("Sample from precio_lista:")
    res = conn.execute(text("SELECT id, evento_id, caso_id, linea_codigo, referencia_codigo, nombre_caso_aplicado FROM precio_lista LIMIT 5")).fetchall()
    for r in res:
        print(r)
        
    print("Sample from pedido_proveedor:")
    res = conn.execute(text("SELECT id, id_intencion_compra, numero_registro, numero_proforma FROM pedido_proveedor LIMIT 5")).fetchall()
    for r in res:
        print(r)
