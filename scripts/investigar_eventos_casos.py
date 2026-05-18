"""
OT-FI-CASO-508-001: Verificar qué eventos tienen casos poblados.
"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("=" * 80)
print("EVENTOS PRECIO disponibles (últimos 10)")
print("=" * 80)
cur.execute("""
    SELECT pe.id, pe.nombre_evento, pe.proveedor_id
    FROM precio_evento pe
    ORDER BY pe.id DESC
    LIMIT 10
""")

for evento_id, nombre, prov in cur.fetchall():
    print(f"  evento_id={evento_id}: {nombre} (prov={prov})")

print()
print("=" * 80)
print("PRECIO_LISTA con nombre_caso_aplicado (por evento)")
print("=" * 80)
cur.execute("""
    SELECT pl.evento_id, COUNT(*) AS total,
           COUNT(DISTINCT pl.nombre_caso_aplicado) AS casos_distintos,
           STRING_AGG(DISTINCT pl.nombre_caso_aplicado, ', ') AS casos
    FROM precio_lista pl
    WHERE pl.nombre_caso_aplicado IS NOT NULL
    GROUP BY pl.evento_id
    ORDER BY pl.evento_id DESC
    LIMIT 10
""")

result = cur.fetchall()
if result:
    for evento_id, total, casos_dist, casos_str in result:
        print(f"  evento_id={evento_id}: {total} líneas, {casos_dist} casos")
        if len(casos_str) < 100:
            print(f"    Casos: {casos_str}")
        else:
            print(f"    Casos: {casos_str[:100]}...")
else:
    print("  (ningún evento tiene nombre_caso_aplicado poblado)")

print()
print("=" * 80)
print("TOTAL precio_lista SIN nombre_caso_aplicado")
print("=" * 80)
cur.execute("""
    SELECT COUNT(*) FROM precio_lista WHERE nombre_caso_aplicado IS NULL
""")
sin_caso = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM precio_lista")
total_pl = cur.fetchone()[0]

print(f"  Total precio_lista: {total_pl}")
print(f"  Sin caso: {sin_caso} ({100*sin_caso/total_pl:.1f}%)")
print(f"  Con caso: {total_pl - sin_caso} ({100*(total_pl-sin_caso)/total_pl:.1f}%)")

cur.close()
conn.close()
