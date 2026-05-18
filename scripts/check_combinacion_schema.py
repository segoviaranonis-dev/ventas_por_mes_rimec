"""Check combinacion table schema"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'combinacion'
    ORDER BY ordinal_position
""")

cols = cur.fetchall()
print("Combinacion columns:")
for c in cols:
    print(f"  {c[0]}: {c[1]}")

# Check if there are any combinaciones at all
cur.execute("SELECT COUNT(*) FROM combinacion")
count = cur.fetchone()[0]
print(f"\nTotal combinaciones in DB: {count}")

# Check a sample
cur.execute("SELECT * FROM combinacion LIMIT 1")
if cur.description:
    col_names = [desc[0] for desc in cur.description]
    print(f"\nSample combinacion (columns: {col_names}):")
    row = cur.fetchone()
    if row:
        for i, val in enumerate(row):
            print(f"  {col_names[i]}: {val}")

conn.close()
