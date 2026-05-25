"""
OT-006 Paso 1: Auditoría de pedidos y facturas con vendedor_id NULL
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
print("OT-006 PASO 1: Auditoria de Contaminacion (vendedor_id NULL)")
print("="*70)
print()

# Pedidos sin vendedor
print("Pedidos con vendedor_id IS NULL:")
print("-"*70)
cur.execute("""
    SELECT
      id, nro_pedido, cliente_id, total_pares, total_monto, estado,
      created_at::timestamp(0) AS creado
    FROM public.pedido_venta_rimec
    WHERE vendedor_id IS NULL
    ORDER BY id DESC
""")

pedidos_null = cur.fetchall()

if pedidos_null:
    print(f"Total: {len(pedidos_null)}")
    print()
    for row in pedidos_null:
        id_ped, nro, cli_id, pares, monto, estado, creado = row
        print(f"  ID: {id_ped}")
        print(f"  Nro Pedido: {nro}")
        print(f"  Cliente ID: {cli_id}")
        print(f"  Total Pares: {pares}")
        print(f"  Total Monto: {monto}")
        print(f"  Estado: {estado}")
        print(f"  Creado: {creado}")
        print()
else:
    print("  (ninguno)")
    print()

print("-"*70)
print()

# Facturas sin vendedor
print("Facturas internas con vendedor_id IS NULL:")
print("-"*70)
cur.execute("""
    SELECT
      fi.id, fi.nro_factura, fi.pp_id, fi.pedido_id, fi.estado,
      fi.total_pares, fi.total_monto, fi.created_at::timestamp(0) AS creada
    FROM public.factura_interna fi
    WHERE fi.vendedor_id IS NULL
    ORDER BY fi.id DESC
""")

facturas_null = cur.fetchall()

if facturas_null:
    print(f"Total: {len(facturas_null)}")
    print()
    for row in facturas_null:
        id_fi, nro_fi, pp_id, ped_id, estado, pares, monto, creada = row
        print(f"  ID: {id_fi}")
        print(f"  Nro Factura: {nro_fi}")
        print(f"  PP ID: {pp_id}")
        print(f"  Pedido ID: {ped_id}")
        print(f"  Estado: {estado}")
        print(f"  Total Pares: {pares}")
        print(f"  Total Monto: {monto}")
        print(f"  Creada: {creada}")
        print()
else:
    print("  (ninguno)")
    print()

print("-"*70)
print()

print("RESUMEN:")
print(f"  Pedidos con vendedor NULL: {len(pedidos_null)}")
print(f"  Facturas con vendedor NULL: {len(facturas_null)}")

if len(pedidos_null) > 0 or len(facturas_null) > 0:
    print()
    print("CRITICO: Contaminacion confirmada en produccion")
else:
    print()
    print("OK: Sin contaminacion detectada")

conn.close()
