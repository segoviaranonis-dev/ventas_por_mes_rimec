"""
Verificar schema de pedido_proveedor_detalle
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

print("Columnas de pedido_proveedor_detalle:\n")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'pedido_proveedor_detalle'
    ORDER BY ordinal_position
""")

for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n" + "="*50)
print("\nColumnas de pedido_proveedor:\n")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'pedido_proveedor'
    ORDER BY ordinal_position
""")

for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
