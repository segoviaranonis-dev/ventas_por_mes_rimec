"""
OT-006 Paso 2: Resolver id_usuario de BZZP y reasignar pedido
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
print("OT-006 PASO 2: Resolver BZZP y Reasignar Pedido")
print("="*70)
print()

# Paso 2.0 - Resolver id_usuario de BZZP
print("Paso 2.0: Buscando usuario BZZP...")
cur.execute("""
    SELECT id_usuario, descp_usuario, categoria, rol_id
    FROM public.usuario_v2
    WHERE UPPER(TRIM(descp_usuario)) = 'BZZP'
       OR UPPER(TRIM(descp_usuario)) LIKE 'BZZP%'
""")

usuario = cur.fetchone()

if not usuario:
    print("ERROR: Usuario BZZP no encontrado en usuario_v2")
    print("ACCION: Avisar al Director")
    conn.close()
    exit(1)

id_bzzp, descp, categoria, rol_id = usuario

print(f"  id_usuario: {id_bzzp}")
print(f"  descp_usuario: {descp}")
print(f"  categoria: {categoria}")
print(f"  rol_id: {rol_id}")
print()

# Verificar que el rol sea VENDEDOR o ADMIN
cur.execute("""
    SELECT nombre_rol FROM public.maestro_rol_acceso WHERE id = %s
""", (rol_id,))

rol_row = cur.fetchone()
if rol_row:
    nombre_rol = rol_row[0]
    print(f"  Rol: {nombre_rol}")

    if nombre_rol not in ('VENDEDOR', 'ADMIN'):
        print()
        print(f"ADVERTENCIA: Usuario BZZP tiene rol '{nombre_rol}'")
        print("             No es VENDEDOR ni ADMIN")
        print("ACCION: Avisar al Director antes de continuar")
        conn.close()
        exit(1)
else:
    print("  ADVERTENCIA: rol_id no encontrado en maestro_rol_acceso")
    print("ACCION: Avisar al Director")
    conn.close()
    exit(1)

print()
print("OK: Usuario BZZP tiene rol valido para ventas")
print()

# Paso 2.1 - UPDATE atomico
print("Paso 2.1: Ejecutando UPDATE atomico...")
print()

try:
    # UPDATE pedido
    print(f"  Actualizando pedido_venta_rimec (PVR-2026-794967)...")
    cur.execute("""
        UPDATE public.pedido_venta_rimec
        SET vendedor_id = %s
        WHERE nro_pedido = 'PVR-2026-794967'
          AND vendedor_id IS NULL
    """, (id_bzzp,))

    filas_pedido = cur.rowcount
    print(f"    Filas actualizadas: {filas_pedido}")

    # UPDATE factura
    print(f"  Actualizando factura_interna...")
    cur.execute("""
        UPDATE public.factura_interna
        SET vendedor_id = %s
        WHERE pedido_id IN (
          SELECT id FROM public.pedido_venta_rimec WHERE nro_pedido = 'PVR-2026-794967'
        )
          AND vendedor_id IS NULL
    """, (id_bzzp,))

    filas_factura = cur.rowcount
    print(f"    Filas actualizadas: {filas_factura}")
    print()

    # Verificacion dentro de la transaccion
    print("  Verificando dentro de la transaccion...")
    cur.execute("""
        SELECT 'pedido' AS tabla, nro_pedido, vendedor_id
        FROM public.pedido_venta_rimec
        WHERE nro_pedido = 'PVR-2026-794967'
        UNION ALL
        SELECT 'factura', nro_factura, vendedor_id
        FROM public.factura_interna
        WHERE pedido_id IN (
          SELECT id FROM public.pedido_venta_rimec WHERE nro_pedido = 'PVR-2026-794967'
        )
    """)

    verificacion = cur.fetchall()

    print()
    print("  Resultados:")
    for row in verificacion:
        tabla, nro, vendedor = row
        print(f"    {tabla}: {nro} -> vendedor_id={vendedor}")

    print()

    # COMMIT
    conn.commit()
    print("COMMIT EXITOSO")
    print()
    print(f"Pedido PVR-2026-794967 reasignado a usuario_v2.id_usuario={id_bzzp} (BZZP)")

except Exception as e:
    print(f"ERROR: {e}")
    print("ROLLBACK ejecutado")
    conn.rollback()
    raise
finally:
    conn.close()
