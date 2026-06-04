#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNOSTICO: Consistencia PV entre Pedido Proveedor y Aprobaciones

PREGUNTA: ¿La misma cantidad de PV existe en ambos lados?
- Pedido Proveedor: factura_interna.nro_factura (PV000007, etc)
- Aprobaciones: pedido_venta_rimec.nro_pedido (PVR-2026-XXXXXX)
"""
from core.database import get_dataframe

print("=" * 80)
print("DIAGNOSTICO: Consistencia PV entre FIs y PVRs")
print("=" * 80)

# 1. Contar Facturas Internas (lado Pedido Proveedor)
print("\n1. FACTURAS INTERNAS (Pedido Proveedor):")
print("-" * 80)
df_fis = get_dataframe("""
    SELECT
        estado,
        COUNT(*) as total_fis,
        COUNT(DISTINCT pedido_id) as pedidos_unicos
    FROM factura_interna
    GROUP BY estado
    ORDER BY estado
""")

if df_fis is not None and not df_fis.empty:
    print(df_fis.to_string(index=False))
    total_fis = df_fis['total_fis'].sum()
    print(f"\nTOTAL FIs: {total_fis}")
else:
    print("ERROR - no se pudo consultar")
    total_fis = 0

# 2. Contar Pedidos Venta RIMEC (lado Aprobaciones)
print("\n2. PEDIDOS VENTA RIMEC (Aprobaciones):")
print("-" * 80)
df_pvr = get_dataframe("""
    SELECT
        estado,
        COUNT(*) as total_pedidos
    FROM pedido_venta_rimec
    GROUP BY estado
    ORDER BY estado
""")

if df_pvr is not None and not df_pvr.empty:
    print(df_pvr.to_string(index=False))
    total_pvr = df_pvr['total_pedidos'].sum()
    print(f"\nTOTAL PVRs: {total_pvr}")
else:
    print("ERROR - no se pudo consultar")
    total_pvr = 0

# 3. Relación FI → PVR
print("\n3. RELACION FI → PVR:")
print("-" * 80)
df_relacion = get_dataframe("""
    SELECT
        COUNT(*) as total_fis,
        COUNT(fi.pedido_id) as fis_con_pedido,
        COUNT(*) - COUNT(fi.pedido_id) as fis_sin_pedido,
        COUNT(DISTINCT fi.pedido_id) as pedidos_distintos
    FROM factura_interna fi
""")

if df_relacion is not None and not df_relacion.empty:
    print(df_relacion.to_string(index=False))
else:
    print("ERROR - no se pudo consultar")

# 4. FIs huérfanas (sin pedido_id)
print("\n4. FIs HUERFANAS (sin pedido_id):")
print("-" * 80)
df_huerfanas = get_dataframe("""
    SELECT
        fi.id,
        fi.nro_factura,
        fi.estado,
        fi.pp_id,
        pp.numero_registro as pp_nro,
        fi.total_pares,
        fi.marca,
        fi.created_at
    FROM factura_interna fi
    LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
    WHERE fi.pedido_id IS NULL
    ORDER BY fi.created_at DESC
    LIMIT 20
""")

if df_huerfanas is not None and not df_huerfanas.empty:
    print(f"ENCONTRADAS: {len(df_huerfanas)} FIs sin pedido_id")
    print(df_huerfanas[['nro_factura', 'estado', 'pp_nro', 'marca', 'total_pares']].to_string(index=False))
else:
    print("OK - No hay FIs sin pedido_id")

# 5. PVRs sin FIs (pedidos vacíos)
print("\n5. PVRs SIN FIs (pedidos sin facturas):")
print("-" * 80)
df_pvr_vacios = get_dataframe("""
    SELECT
        pvr.id,
        pvr.nro_pedido,
        pvr.estado,
        pvr.total_pares,
        pvr.total_monto,
        COUNT(fi.id) as num_fis
    FROM pedido_venta_rimec pvr
    LEFT JOIN factura_interna fi ON fi.pedido_id = pvr.id
    GROUP BY pvr.id, pvr.nro_pedido, pvr.estado, pvr.total_pares, pvr.total_monto
    HAVING COUNT(fi.id) = 0
    ORDER BY pvr.created_at DESC
    LIMIT 20
""")

if df_pvr_vacios is not None and not df_pvr_vacios.empty:
    print(f"ENCONTRADOS: {len(df_pvr_vacios)} PVRs sin FIs")
    print(df_pvr_vacios[['nro_pedido', 'estado', 'total_pares', 'total_monto']].to_string(index=False))
else:
    print("OK - Todos los PVRs tienen al menos 1 FI")

# 6. Múltiples FIs por pedido (esperado)
print("\n6. DISTRIBUCION: FIs por Pedido:")
print("-" * 80)
df_dist = get_dataframe("""
    SELECT
        COUNT(fi.id) as num_fis_por_pedido,
        COUNT(DISTINCT pvr.id) as num_pedidos
    FROM pedido_venta_rimec pvr
    LEFT JOIN factura_interna fi ON fi.pedido_id = pvr.id
    GROUP BY pvr.id
    ORDER BY num_fis_por_pedido
""")

if df_dist is not None and not df_dist.empty:
    # Agrupar por cantidad de FIs
    dist_summary = df_dist.groupby('num_fis_por_pedido')['num_pedidos'].sum().reset_index()
    print(dist_summary.to_string(index=False))
else:
    print("ERROR - no se pudo consultar")

print("\n" + "=" * 80)
print("CONCLUSION:")
print(f"  Facturas Internas: {total_fis}")
print(f"  Pedidos Venta:     {total_pvr}")

if total_fis > total_pvr:
    print(f"  DIFERENCIA: {total_fis - total_pvr} FIs de mas (normal: 1 pedido = N facturas)")
    print("  ESPERADO: Un pedido puede tener multiples FIs (por PP/Marca/Caso)")
elif total_fis < total_pvr:
    print(f"  ADVERTENCIA: {total_pvr - total_fis} PVRs sin FIs")
else:
    print("  OK: 1 FI por pedido (poco probable)")
print("=" * 80)
