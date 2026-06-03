#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESTADISTICAS: Contador de PV y cantidad vendida

CASO DE CONTROL: PV000007 - Cliente P Y N - Vendedor CESAR
"""
from core.database import get_dataframe
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

print("=" * 80)
print("ESTADISTICAS DE VENTAS - CONTADOR PV")
print("=" * 80)

# 1. CASO DE CONTROL: PV000007 (P Y N - CESAR)
print("\n1. CASO DE CONTROL: PV000007 (Cliente P Y N - Vendedor CESAR)")
print("-" * 80)
df_pv7 = get_dataframe("""
    SELECT
        fi.id as fi_id,
        fi.nro_factura,
        fi.estado as fi_estado,
        fi.pedido_id,
        pvr.nro_pedido,
        pvr.estado as pedido_estado,
        c.descp_cliente as cliente,
        v.descp_usuario as vendedor,
        fi.total_pares,
        fi.total_monto,
        fi.marca,
        fi.caso,
        fi.created_at
    FROM factura_interna fi
    LEFT JOIN pedido_venta_rimec pvr ON pvr.id = fi.pedido_id
    LEFT JOIN cliente_v2 c ON c.id_cliente = fi.cliente_id
    LEFT JOIN usuario_v2 v ON v.id_usuario = fi.vendedor_id
    WHERE fi.nro_factura LIKE '%00007%'
       OR fi.nro_factura LIKE '%PV7%'
       OR UPPER(c.descp_cliente) LIKE '%P Y N%'
    ORDER BY fi.nro_factura
""")

if df_pv7 is not None and not df_pv7.empty:
    print(f"ENCONTRADO: {len(df_pv7)} registro(s)")
    print(df_pv7.to_string(index=False))

    if df_pv7['pedido_id'].isna().any():
        print("\nALERTA: PV000007 NO tiene pedido_id (huerfana)")
    else:
        print("\nOK: PV000007 SI tiene pedido asociado")
        print(f"  Pedido: {df_pv7['nro_pedido'].iloc[0]}")
        print(f"  Estado pedido: {df_pv7['pedido_estado'].iloc[0]}")
else:
    print("NO ENCONTRADO - PV000007 no existe en BD")

# 2. CONTADOR GENERAL: Total PV y Pares Vendidos
print("\n2. CONTADOR GENERAL: Facturas Internas")
print("-" * 80)
df_contador = get_dataframe("""
    SELECT
        fi.estado,
        COUNT(*) as num_facturas,
        SUM(fi.total_pares) as total_pares,
        SUM(fi.total_monto) as total_monto
    FROM factura_interna fi
    GROUP BY fi.estado
    ORDER BY fi.estado
""")

if df_contador is not None and not df_contador.empty:
    print(df_contador.to_string(index=False))
    print("\nTOTAL GENERAL:")
    print(f"  Facturas:  {df_contador['num_facturas'].sum()}")
    print(f"  Pares:     {df_contador['total_pares'].sum()}")
    print(f"  Monto:     Gs. {df_contador['total_monto'].sum():,.0f}")
else:
    print("ERROR - no se pudo consultar")

# 3. TOP 10: Clientes con mas pares vendidos
print("\n3. TOP 10 CLIENTES (por pares vendidos):")
print("-" * 80)
df_clientes = get_dataframe("""
    SELECT
        c.descp_cliente as cliente,
        COUNT(fi.id) as num_facturas,
        SUM(fi.total_pares) as total_pares,
        SUM(fi.total_monto) as total_monto
    FROM factura_interna fi
    LEFT JOIN cliente_v2 c ON c.id_cliente = fi.cliente_id
    WHERE fi.estado = 'CONFIRMADA'
    GROUP BY c.descp_cliente
    ORDER BY total_pares DESC
    LIMIT 10
""")

if df_clientes is not None and not df_clientes.empty:
    print(df_clientes.to_string(index=False))
else:
    print("ERROR - no se pudo consultar")

# 4. TOP 10: Vendedores con mas pares vendidos
print("\n4. TOP 10 VENDEDORES (por pares vendidos):")
print("-" * 80)
df_vendedores = get_dataframe("""
    SELECT
        v.descp_usuario as vendedor,
        COUNT(fi.id) as num_facturas,
        SUM(fi.total_pares) as total_pares,
        SUM(fi.total_monto) as total_monto
    FROM factura_interna fi
    LEFT JOIN usuario_v2 v ON v.id_usuario = fi.vendedor_id
    WHERE fi.estado = 'CONFIRMADA'
    GROUP BY v.descp_usuario
    ORDER BY total_pares DESC
    LIMIT 10
""")

if df_vendedores is not None and not df_vendedores.empty:
    print(df_vendedores.to_string(index=False))
else:
    print("ERROR - no se pudo consultar")

# 5. Distribución por marca
print("\n5. VENTAS POR MARCA (CONFIRMADAS):")
print("-" * 80)
df_marcas = get_dataframe("""
    SELECT
        fi.marca,
        COUNT(fi.id) as num_facturas,
        SUM(fi.total_pares) as total_pares,
        SUM(fi.total_monto) as total_monto
    FROM factura_interna fi
    WHERE fi.estado = 'CONFIRMADA'
    GROUP BY fi.marca
    ORDER BY total_pares DESC
""")

if df_marcas is not None and not df_marcas.empty:
    print(df_marcas.to_string(index=False))
else:
    print("ERROR - no se pudo consultar")

# 6. VERIFICAR: PV000007 en vista de aprobaciones
print("\n6. VERIFICAR: PV000007 en vista aprobaciones (post-fix):")
print("-" * 80)
df_vista = get_dataframe("""
    SELECT
        pvr.nro_pedido,
        pvr.estado as pedido_estado,
        COUNT(fi.id) as num_fis,
        STRING_AGG(fi.nro_factura, ', ') as facturas
    FROM pedido_venta_rimec pvr
    LEFT JOIN factura_interna fi ON fi.pedido_id = pvr.id
    WHERE fi.nro_factura LIKE '%00007%'
       OR fi.nro_factura LIKE '%PV7%'
    GROUP BY pvr.id, pvr.nro_pedido, pvr.estado
""")

if df_vista is not None and not df_vista.empty:
    print("OK - PV000007 aparece en pedidos:")
    print(df_vista.to_string(index=False))
else:
    print("PROBLEMA - PV000007 NO aparece asociado a ningun pedido")

print("\n" + "=" * 80)
print("FIN DEL REPORTE")
print("=" * 80)
