import sqlalchemy
engine = sqlalchemy.create_engine('postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
with engine.connect() as conn:
    print(conn.execute(sqlalchemy.text("SELECT id FROM linea WHERE codigo_proveedor = '8246'")).fetchall())
    print(conn.execute(sqlalchemy.text("SELECT id FROM referencia WHERE codigo_proveedor = '1176'")).fetchall())
    print(conn.execute(sqlalchemy.text("SELECT id FROM material WHERE descripcion = 'NAPA TURIM'")).fetchall())
    print(conn.execute(sqlalchemy.text("SELECT id FROM color WHERE nombre = 'TAN  1080'")).fetchall())
