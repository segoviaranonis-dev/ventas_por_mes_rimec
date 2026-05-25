"""
Verificar si v_stock_rimec existe y su definición
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

print("Verificando vista v_stock_rimec...\n")

# Verificar si existe
cur.execute("""
    SELECT COUNT(*)
    FROM information_schema.views
    WHERE table_schema = 'public'
    AND table_name = 'v_stock_rimec'
""")

if cur.fetchone()[0] == 0:
    print("La vista v_stock_rimec NO EXISTE en la base de datos")
else:
    print("La vista v_stock_rimec SÍ EXISTE")
    print("\nDefinición de la vista:\n")
    print("="*70)

    # Obtener definición
    cur.execute("""
        SELECT pg_get_viewdef('public.v_stock_rimec'::regclass, true)
    """)

    view_def = cur.fetchone()[0]
    print(view_def)
    print("="*70)

conn.close()
