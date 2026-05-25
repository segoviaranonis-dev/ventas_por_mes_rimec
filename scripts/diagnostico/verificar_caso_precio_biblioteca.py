"""
Verificar schema de caso_precio_biblioteca
"""

import psycopg2

conn = psycopg2.connect(
    host='aws-1-sa-east-1.pooler.supabase.com',
    port=6543,
    dbname='postgres',
    user='postgres.extrlcvcgypwazxipvqm',
    password='IJoFJbT8Qj0Q0w5m'
)
cur = conn.cursor()

# Verificar si existe
cur.execute("""
    SELECT COUNT(*)
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name = 'caso_precio_biblioteca'
""")

if cur.fetchone()[0] == 0:
    print("La tabla caso_precio_biblioteca NO EXISTE")
else:
    print("Columnas de caso_precio_biblioteca:\n")
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'caso_precio_biblioteca'
        ORDER BY ordinal_position
    """)

    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]}")

    print("\nFilas en caso_precio_biblioteca:")
    cur.execute("SELECT COUNT(*) FROM caso_precio_biblioteca")
    print(f"  Total: {cur.fetchone()[0]}")

    print("\nMuestra de datos:")
    cur.execute("SELECT * FROM caso_precio_biblioteca LIMIT 5")
    rows = cur.fetchall()
    if rows:
        cols = [desc[0] for desc in cur.description]
        print(f"  Columnas: {cols}")
        for row in rows:
            print(f"  {row}")

conn.close()
