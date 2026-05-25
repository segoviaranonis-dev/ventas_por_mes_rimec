"""
OT-004 Paso 2: Identificar SKUs huérfanos (sin precio)
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

print("="*70)
print("OT-004 PASO 2: Cobertura de Precios en v_stock_rimec")
print("="*70)
print()

cur.execute("""
    WITH cobertura AS (
      SELECT
        COUNT(*)::int                                                AS total,
        COUNT(*) FILTER (WHERE lpn IS NOT NULL AND lpn > 0)::int     AS con_lpn,
        COUNT(*) FILTER (WHERE caso_id IS NOT NULL)::int             AS con_caso,
        COUNT(*) FILTER (WHERE cajas_disponibles > 0)::int           AS con_stock,
        COUNT(*) FILTER (WHERE cajas_disponibles > 0
                           AND (lpn IS NULL OR lpn <= 0))::int       AS con_stock_sin_precio
      FROM v_stock_rimec
    )
    SELECT * FROM cobertura
""")

row = cur.fetchone()
total, con_lpn, con_caso, con_stock, con_stock_sin_precio = row

print("Cobertura General:")
print(f"  Total SKUs en vista: {total:,}")
print(f"  Con LPN (precio): {con_lpn:,}")
print(f"  Con caso_id: {con_caso:,}")
print(f"  Con stock disponible (cajas > 0): {con_stock:,}")
print(f"  Con stock PERO sin precio: {con_stock_sin_precio:,}")
print()

if con_stock > 0:
    porcentaje = (con_stock_sin_precio / con_stock) * 100
    print(f"Porcentaje sin precio: {porcentaje:.1f}%")
    print()

    if porcentaje > 10:
        print("ALERTA: Mas del 10% del stock disponible no tiene precio")
        print("        Requiere atencion operativa")
    else:
        print("OK: Degradacion aceptable (<10%)")
else:
    print("ADVERTENCIA: No hay stock disponible en la vista")

conn.close()
