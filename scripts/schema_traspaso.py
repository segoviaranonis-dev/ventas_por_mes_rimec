import psycopg2

conn = psycopg2.connect("postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres")
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'traspaso'
    ORDER BY ordinal_position
""")
print("Columnas tabla traspaso:")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

print()
print("Columnas tabla movimiento:")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'movimiento'
    ORDER BY ordinal_position
""")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

cur.close()
conn.close()
