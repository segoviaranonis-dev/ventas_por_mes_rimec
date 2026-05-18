"""
Verificar desvio H1: ppd.id_marca vs linea.marca_id
"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("=" * 80)
print("VERIFICACION DESVIO H1: ppd.id_marca vs linea.marca_id")
print("=" * 80)
print()

# Query: comparar ppd.id_marca con linea.marca_id
cur.execute("""
    SELECT
        ppd.id AS ppd_id,
        ppd.linea AS ppd_linea,
        ppd.referencia AS ppd_ref,
        ppd.id_marca AS ppd_marca_id,
        mv1.descp_marca AS ppd_marca_descp,
        l.id AS linea_id,
        l.marca_id AS linea_marca_id,
        mv2.descp_marca AS linea_marca_descp,
        pp.numero_registro AS pp_nro
    FROM pedido_proveedor_detalle ppd
    JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
    LEFT JOIN marca_v2 mv1 ON mv1.id_marca = ppd.id_marca
    LEFT JOIN linea l
        ON l.codigo_proveedor::text = ppd.linea
       AND l.proveedor_id = pp.proveedor_importacion_id
    LEFT JOIN marca_v2 mv2 ON mv2.id_marca = l.marca_id
    WHERE ppd.id_marca IS NOT NULL
      AND l.marca_id IS NOT NULL
      AND ppd.id_marca != l.marca_id
    ORDER BY ppd.id
    LIMIT 50
""")

desvios = cur.fetchall()

if desvios:
    print(f"[!!] DESVIOS ENCONTRADOS: {len(desvios)} filas con marca diferente")
    print()
    for row in desvios:
        ppd_id, ppd_linea, ppd_ref, ppd_marca_id, ppd_marca_descp, linea_id, linea_marca_id, linea_marca_descp, pp_nro = row
        print(f"ppd.id={ppd_id} | PP={pp_nro} | {ppd_linea}/{ppd_ref}")
        print(f"  ppd.id_marca: {ppd_marca_id} -> '{ppd_marca_descp}'")
        print(f"  linea.marca_id: {linea_marca_id} -> '{linea_marca_descp}'")
        print(f"  [!!] DESVIO CRITICO: marca inconsistente")
        print()
else:
    print("[OK] Sin desvios: ppd.id_marca = linea.marca_id en todas las filas")
    print()

# Count total
cur.execute("""
    SELECT COUNT(*)
    FROM pedido_proveedor_detalle ppd
    JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
    LEFT JOIN linea l
        ON l.codigo_proveedor::text = ppd.linea
       AND l.proveedor_id = pp.proveedor_importacion_id
    WHERE ppd.id_marca IS NOT NULL
      AND l.marca_id IS NOT NULL
""")
total = cur.fetchone()[0]
print(f"Total filas verificadas: {total}")
print(f"Desvios encontrados: {len(desvios)}")
print(f"Porcentaje desvio: {100 * len(desvios) / total if total > 0 else 0:.2f}%")

cur.close()
conn.close()
