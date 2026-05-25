"""
OT-004 Paso 1: Verificar MIG-071 en Supabase producción
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
print("OT-004 PASO 1: Verificar MIG-071 en v_stock_rimec")
print("="*70)
print()

# Verificar comentario de la vista
cur.execute("""
    SELECT obj_description('public.v_stock_rimec'::regclass, 'pg_class') AS comentario
""")

comentario = cur.fetchone()[0]

print("Comentario de v_stock_rimec:")
print("-"*70)
if comentario:
    # Replace problematic Unicode characters
    comentario_safe = comentario.replace('→', '->').replace('═', '=')
    print(comentario_safe)
else:
    print("(sin comentario)")
print("-"*70)
print()

# Buscar marca MIG-071 o MIG-070
tiene_mig071 = 'MIG-071' in comentario if comentario else False
tiene_mig070 = 'MIG-070' in comentario if comentario else False

print("Marcas de migración:")
print(f"  MIG-071: {'PRESENTE' if tiene_mig071 else 'AUSENTE'}")
print(f"  MIG-070: {'PRESENTE' if tiene_mig070 else 'AUSENTE'}")
print()

if tiene_mig071 or tiene_mig070:
    print("VEREDICTO: Migración aplicada (vista actualizada)")
else:
    print("VEREDICTO: Migración NO detectada - requiere aplicación")

conn.close()
