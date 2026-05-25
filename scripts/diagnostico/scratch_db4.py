import sqlalchemy
engine = sqlalchemy.create_engine('postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
with engine.connect() as conn:
    print(conn.execute(sqlalchemy.text("SELECT talla_etiqueta FROM talla WHERE talla_etiqueta IN ('17', '18', '19')")).fetchall())
