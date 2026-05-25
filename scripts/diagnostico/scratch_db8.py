import sys
from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

with engine.connect() as conn:
    res = conn.execute(text("""
        SELECT t.id, t.numero_registro, t.estado
        FROM traspaso t
        WHERE t.estado = 'CONFIRMADO'
          AND NOT EXISTS (
              SELECT 1 FROM movimiento m
              JOIN movimiento_detalle md ON md.movimiento_id = m.id
              WHERE m.documento_ref = t.numero_registro
          )
    """)).fetchall()
    print("Traspasos CONFIRMADOS sin movimiento_detalle:", res)
    
    # Let's check ENVIADO or BORRADOR with 0 traspaso_detalle
    res = conn.execute(text("""
        SELECT t.id, t.numero_registro, t.estado
        FROM traspaso t
        WHERE NOT EXISTS (
            SELECT 1 FROM traspaso_detalle td WHERE td.traspaso_id = t.id
        )
    """)).fetchall()
    print("Traspasos sin traspaso_detalle:", res)
