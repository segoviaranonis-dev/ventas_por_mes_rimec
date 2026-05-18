import sqlalchemy
engine = sqlalchemy.create_engine('postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
with engine.connect() as conn:
    print(conn.execute(sqlalchemy.text("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'linea'")).fetchall())
