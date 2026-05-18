"""Check talla table schema"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Check if talla table exists
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_name LIKE '%tall%'
""")
tables = cur.fetchall()
print("Tables with 'tall' in name:")
for t in tables:
    print(f"  {t[0]}")

# If talla exists, get schema
if any(t[0] == 'talla' for t in tables):
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'talla'
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    print("\nTalla columns:")
    for c in cols:
        print(f"  {c[0]}: {c[1]}")

    # Sample rows
    cur.execute("SELECT * FROM talla LIMIT 5")
    print("\nSample rows:")
    col_names = [desc[0] for desc in cur.description]
    print(f"  Columns: {col_names}")
    for r in cur.fetchall():
        print(f"  {r}")
else:
    print("\n[!!] talla table does NOT exist")

conn.close()
