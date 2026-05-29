#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico específico: FI 10-PV002
"""
from core.database import get_dataframe

print("=" * 80)
print("DIAGNOSTICO: FI 10-PV002")
print("=" * 80)

# 1. Buscar la FI por nombre
print("\n1. Datos de la FI:")
df_fi = get_dataframe("""
    SELECT
        fi.id,
        fi.nro_factura,
        fi.pp_id,
        fi.pedido_id,
        fi.marca,
        fi.caso,
        fi.total_pares,
        fi.total_monto,
        fi.estado,
        fi.created_at,
        pp.numero_registro as pp_nro,
        pp.estado as pp_estado
    FROM factura_interna fi
    LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
    WHERE fi.nro_factura = '10-PV002'
""")

if df_fi is None or df_fi.empty:
    print("ERROR - FI no encontrada")
    exit(1)

print(df_fi.to_string(index=False))

fi_id = int(df_fi['id'].iloc[0])
pedido_id = df_fi['pedido_id'].iloc[0]
estado_fi = df_fi['estado'].iloc[0]
pp_id = int(df_fi['pp_id'].iloc[0])

# 2. Si tiene pedido_id, ver el pedido
if pedido_id:
    print(f"\n2. Pedido asociado (ID: {pedido_id}):")
    df_pedido = get_dataframe("""
        SELECT
            id,
            nro_pedido,
            estado,
            motivo_rechazo,
            created_at
        FROM pedido_venta_rimec
        WHERE id = :pid
    """, {"pid": int(pedido_id)})

    if df_pedido is not None and not df_pedido.empty:
        print(df_pedido.to_string(index=False))
    else:
        print("WARNING - Pedido no encontrado")
else:
    print("\n2. FI NO tiene pedido_id asociado (huerfana sin vinculo)")

# 3. Verificar stock del PP
print(f"\n3. Stock del PP-{pp_id}:")
df_stock = get_dataframe("""
    SELECT
        pp.id,
        pp.numero_registro,
        COUNT(DISTINCT ppd.id) as articulos_fi,
        SUM(ppd.cantidad_pares) as total_pares,
        SUM(ppd.pares_vendidos) as pares_vendidos,
        SUM(ppd.cantidad_pares) - SUM(ppd.pares_vendidos) as saldo_disponible
    FROM pedido_proveedor pp
    LEFT JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
    WHERE pp.id = :pp_id
    GROUP BY pp.id, pp.numero_registro
""", {"pp_id": pp_id})

if df_stock is not None and not df_stock.empty:
    print(df_stock.to_string(index=False))

# 4. Todas las FIs de este PP
print(f"\n4. Todas las FIs del PP-{pp_id}:")
df_todas_fis = get_dataframe("""
    SELECT
        fi.id,
        fi.nro_factura,
        fi.estado,
        fi.total_pares,
        fi.pedido_id,
        pvr.nro_pedido,
        pvr.estado as pedido_estado
    FROM factura_interna fi
    LEFT JOIN pedido_venta_rimec pvr ON pvr.id = fi.pedido_id
    WHERE fi.pp_id = :pp_id
    ORDER BY fi.id
""", {"pp_id": pp_id})

if df_todas_fis is not None and not df_todas_fis.empty:
    print(df_todas_fis.to_string(index=False))

# 5. Recomendación
print("\n" + "=" * 80)
print("RECOMENDACION:")

if estado_fi == 'RESERVADA':
    print(f"La FI {df_fi['nro_factura'].iloc[0]} esta en estado RESERVADA")
    print(f"Total pares bloqueados: {df_fi['total_pares'].iloc[0]}")

    if pedido_id:
        print(f"\nTiene pedido_id: {pedido_id}")
        if df_pedido is not None and not df_pedido.empty:
            if df_pedido['estado'].iloc[0] == 'RECHAZADO':
                print("El pedido esta RECHAZADO")
                print("\nACCION: Anular manualmente esta FI")
                print(f"Comando: anular_fi({fi_id}, motivo='Pedido rechazado')")
    else:
        print("\nNO tiene pedido_id (FI huerfana sin vinculo)")
        print("\nACCION: Anular manualmente esta FI")
        print(f"Comando: anular_fi({fi_id}, motivo='FI huerfana sin pedido')")
else:
    print(f"La FI ya esta en estado: {estado_fi}")

print("=" * 80)
