"""
OT-006 Paso 4: Aplicar NOT NULL constraints
"""

import psycopg2

conn = psycopg2.connect(
    host='aws-1-sa-east-1.pooler.supabase.com',
    port=6543,
    dbname='postgres',
    user='postgres.extrlcvcgypwazxipvqm',
    password='IJoFJbT8Qj0Q0w5m'
)
conn.autocommit = False
cur = conn.cursor()

print("="*70)
print("OT-006 PASO 4: Aplicar NOT NULL Constraints")
print("="*70)
print()

# Paso 4.0 - Inspección previa
print("Paso 4.0: Inspeccion de columnas...")
cur.execute("""
    SELECT column_name, is_nullable, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'pedido_venta_rimec'
      AND column_name IN ('cliente_id','vendedor_id','plazo_id','lista_precio_id')
    ORDER BY column_name
""")

print("\nTabla: pedido_venta_rimec")
for row in cur.fetchall():
    col, nullable, dtype = row
    print(f"  {col}: {dtype} - nullable={nullable}")

cur.execute("""
    SELECT column_name, is_nullable, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'factura_interna'
      AND column_name IN ('cliente_id','vendedor_id','plazo_id','lista_precio_id')
    ORDER BY column_name
""")

print("\nTabla: factura_interna")
for row in cur.fetchall():
    col, nullable, dtype = row
    print(f"  {col}: {dtype} - nullable={nullable}")

print()

# Verificar que no hay registros con vendedor_id NULL
print("Verificando que no hay registros con vendedor_id NULL...")
cur.execute("SELECT COUNT(*) FROM public.pedido_venta_rimec WHERE vendedor_id IS NULL")
pedidos_null = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM public.factura_interna WHERE vendedor_id IS NULL")
facturas_null = cur.fetchone()[0]

print(f"  Pedidos con vendedor NULL: {pedidos_null}")
print(f"  Facturas con vendedor NULL: {facturas_null}")
print()

if pedidos_null > 0 or facturas_null > 0:
    print("ERROR: Aun hay registros con vendedor_id NULL")
    print("       No se puede aplicar NOT NULL constraint")
    print("       Ejecutar primero Paso 2 (reasignar)")
    conn.close()
    exit(1)

print("OK: No hay registros con vendedor NULL")
print()

# Aplicar NOT NULL
try:
    print("Aplicando ALTER COLUMN SET NOT NULL...")
    print()

    print("  1. pedido_venta_rimec.vendedor_id...")
    cur.execute("""
        ALTER TABLE public.pedido_venta_rimec
          ALTER COLUMN vendedor_id SET NOT NULL
    """)
    print("     OK")

    print("  2. factura_interna.vendedor_id...")
    cur.execute("""
        ALTER TABLE public.factura_interna
          ALTER COLUMN vendedor_id SET NOT NULL
    """)
    print("     OK")
    print()

    # Commit
    conn.commit()
    print("COMMIT EXITOSO")
    print()

    # Verificacion
    print("Verificacion post-constraint...")
    cur.execute("""
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name IN ('pedido_venta_rimec', 'factura_interna')
          AND column_name = 'vendedor_id'
        ORDER BY table_name
    """)

    for row in cur.fetchall():
        print(f"  {row[0]}: nullable={row[1]}")

    print()
    print("Constraint NOT NULL aplicado exitosamente")
    print("Sistema blindado: vendedor_id es obligatorio")

except Exception as e:
    print(f"ERROR: {e}")
    print("ROLLBACK ejecutado")
    conn.rollback()
    raise
finally:
    conn.close()
