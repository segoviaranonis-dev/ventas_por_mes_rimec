import sys
import os

from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

with engine.connect() as conn:
    print(conn.execute(text("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'material'")).fetchall())
    print(conn.execute(text("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'color'")).fetchall())
    print(conn.execute(text("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'talla'")).fetchall())
