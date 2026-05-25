"""
OT-006 Paso 2b: Corregir factura huérfana (pedido_id NULL)
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
print("OT-006 PASO 2b: Corregir Factura Huerfana")
print("="*70)
print()

# Buscar factura con vendedor_id NULL creada al mismo tiempo que el pedido
print("Buscando factura huerfana (nro_factura=1-PV001, ID=16)...")
cur.execute("""
    SELECT id, nro_factura, pp_id, pedido_id, vendedor_id, total_pares, total_monto
    FROM public.factura_interna
    WHERE id = 16
""")

factura = cur.fetchone()

if not factura:
    print("ERROR: Factura ID 16 no encontrada")
    conn.close()
    exit(1)

id_fi, nro_fi, pp_id, ped_id, vend_id, pares, monto = factura

print(f"  ID: {id_fi}")
print(f"  Nro Factura: {nro_fi}")
print(f"  PP ID: {pp_id}")
print(f"  Pedido ID: {ped_id}")
print(f"  Vendedor ID: {vend_id}")
print(f"  Total Pares: {pares}")
print(f"  Total Monto: {monto}")
print()

if vend_id is not None:
    print("Factura ya tiene vendedor asignado. Saliendo.")
    conn.close()
    exit(0)

# Obtener ID del pedido PVR-2026-794967
cur.execute("""
    SELECT id FROM public.pedido_venta_rimec WHERE nro_pedido = 'PVR-2026-794967'
""")

pedido_row = cur.fetchone()
if not pedido_row:
    print("ERROR: Pedido PVR-2026-794967 no encontrado")
    conn.close()
    exit(1)

id_pedido = pedido_row[0]

print(f"Pedido PVR-2026-794967 tiene ID: {id_pedido}")
print()

# UPDATE factura con vendedor_id=10 (BZZP) y pedido_id
print("Actualizando factura...")
try:
    cur.execute("""
        UPDATE public.factura_interna
        SET vendedor_id = 10, pedido_id = %s
        WHERE id = 16
          AND vendedor_id IS NULL
    """, (id_pedido,))

    filas = cur.rowcount
    print(f"  Filas actualizadas: {filas}")
    print()

    # Verificar
    cur.execute("""
        SELECT id, nro_factura, pedido_id, vendedor_id
        FROM public.factura_interna
        WHERE id = 16
    """)

    verificacion = cur.fetchone()
    print("  Verificacion:")
    print(f"    ID: {verificacion[0]}")
    print(f"    Nro Factura: {verificacion[1]}")
    print(f"    Pedido ID: {verificacion[2]}")
    print(f"    Vendedor ID: {verificacion[3]}")
    print()

    conn.commit()
    print("COMMIT EXITOSO")
    print()
    print("Factura 1-PV001 vinculada a pedido y asignada a BZZP")

except Exception as e:
    print(f"ERROR: {e}")
    conn.rollback()
    raise
finally:
    conn.close()
