"""
OT-FI-CASO-508-001: Investigar esquema de factura_interna y precio_lista para caso.
"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("=" * 80)
print("ESQUEMA: factura_interna")
print("=" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'factura_interna'
      AND column_name IN ('caso', 'caso_id', 'marca', 'marca_id', 'lista_precio_id')
    ORDER BY ordinal_position
""")

for col, dtype, nullable in cur.fetchall():
    print(f"  {col}: {dtype} (nullable={nullable})")

print()
print("=" * 80)
print("ESQUEMA: precio_lista")
print("=" * 80)
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'precio_lista'
      AND column_name LIKE '%caso%'
    ORDER BY ordinal_position
""")

cols_caso = cur.fetchall()
if cols_caso:
    for col, dtype in cols_caso:
        print(f"  {col}: {dtype}")
else:
    print("  (sin columnas *caso*)")

print()
print("=" * 80)
print("MUESTRA: factura_interna WHERE nro_factura='1-PV001'")
print("=" * 80)

cur.execute("""
    SELECT id, nro_factura, pp_id, lista_precio_id, caso, caso_id, marca, marca_id
    FROM factura_interna
    WHERE nro_factura = '1-PV001'
""")

row = cur.fetchone()
if row:
    fi_id, nro, pp_id, evento_id, caso, caso_id, marca, marca_id = row
    print(f"  id: {fi_id}")
    print(f"  nro_factura: {nro}")
    print(f"  pp_id: {pp_id}")
    print(f"  lista_precio_id: {evento_id}")
    print(f"  caso: {caso}")
    print(f"  caso_id: {caso_id}")
    print(f"  marca: {marca}")
    print(f"  marca_id: {marca_id}")
else:
    print("  [NO ENCONTRADA]")

print()
print("=" * 80)
print("CASOS EN precio_lista evento_id={0}".format(evento_id if row else "?"))
print("=" * 80)

if row and evento_id:
    cur.execute("""
        SELECT nombre_caso_aplicado, COUNT(*) AS lineas
        FROM precio_lista
        WHERE evento_id = %s
          AND nombre_caso_aplicado IS NOT NULL
        GROUP BY nombre_caso_aplicado
        ORDER BY COUNT(*) DESC
    """, (evento_id,))

    casos = cur.fetchall()
    if casos:
        print(f"  Casos en listado:")
        for caso_nombre, cnt in casos:
            print(f"    {caso_nombre}: {cnt} líneas")
    else:
        print("  (sin casos en precio_lista)")

cur.close()
conn.close()
