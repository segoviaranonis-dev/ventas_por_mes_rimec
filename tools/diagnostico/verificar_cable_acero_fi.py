#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificar Cable de Acero Reforzado: PP -> FI
Confirma que quincena_arribo_id se propaga correctamente.
"""
from core.database import get_dataframe

print("=" * 80)
print("VERIFICACION CABLE DE ACERO: PP -> FACTURA INTERNA")
print("=" * 80)

# 1. PPs con quincena definida
print("\n1. Pedidos Proveedor con quincena asignada:")
df_pp = get_dataframe("""
    SELECT
        pp.id,
        pp.numero_registro,
        pp.quincena_arribo_id,
        qa.descripcion as quincena_desc,
        COUNT(DISTINCT fi.id) as facturas_generadas
    FROM pedido_proveedor pp
    LEFT JOIN quincena_arribo qa ON qa.id = pp.quincena_arribo_id
    LEFT JOIN factura_interna fi ON fi.pp_id = pp.id
    WHERE pp.quincena_arribo_id IS NOT NULL
    GROUP BY pp.id, pp.numero_registro, pp.quincena_arribo_id, qa.descripcion
    ORDER BY pp.id DESC
    LIMIT 10
""")

if df_pp is not None and not df_pp.empty:
    print(df_pp.to_string(index=False))
    print(f"\nTotal PPs con quincena: {len(df_pp)}")
else:
    print("WARNING: No hay PPs con quincena asignada")

# 2. Facturas Internas con quincena heredada
print("\n" + "=" * 80)
print("2. Facturas Internas con quincena heredada de PP:")
df_fi = get_dataframe("""
    SELECT
        fi.id as fi_id,
        fi.nro_factura,
        fi.pp_id,
        pp.numero_registro as pp_nro,
        pp.quincena_arribo_id as pp_quincena,
        fi.quincena_arribo_id as fi_quincena,
        qa.descripcion as quincena_desc,
        fi.estado,
        fi.created_at
    FROM factura_interna fi
    LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
    LEFT JOIN quincena_arribo qa ON qa.id = fi.quincena_arribo_id
    WHERE fi.created_at > NOW() - INTERVAL '7 days'
    ORDER BY fi.created_at DESC
    LIMIT 20
""")

if df_fi is not None and not df_fi.empty:
    print(df_fi.to_string(index=False))

    # Verificar consistencia
    print("\n" + "=" * 80)
    print("3. VERIFICACION DE INTEGRIDAD:")

    inconsistentes = 0
    consistentes = 0
    sin_pp = 0

    for _, row in df_fi.iterrows():
        if row['pp_id'] is None:
            sin_pp += 1
        elif row['pp_quincena'] != row['fi_quincena']:
            inconsistentes += 1
            print(f"ERROR - INCONSISTENTE: FI {row['fi_id']} ({row['nro_factura']})")
            print(f"   PP quincena: {row['pp_quincena']}")
            print(f"   FI quincena: {row['fi_quincena']}")
        else:
            consistentes += 1

    print(f"\nOK - Consistentes (FI.quincena = PP.quincena): {consistentes}")
    print(f"ERROR - Inconsistentes: {inconsistentes}")
    print(f"WARNING - Sin PP asociado: {sin_pp}")

    if inconsistentes == 0 and consistentes > 0:
        print("\nSUCCESS: CABLE DE ACERO FUNCIONANDO CORRECTAMENTE")
    elif inconsistentes > 0:
        print("\nWARNING: Hay inconsistencias - verificar logica de creacion de FI")
    else:
        print("\nINFO: Sin datos para verificar - crear FIs de prueba")
else:
    print("WARNING: No hay FIs recientes para verificar")

# 4. Vista v_stock_rimec con quincena
print("\n" + "=" * 80)
print("4. Vista v_stock_rimec expone quincena correctamente:")
df_stock = get_dataframe("""
    SELECT
        pp_id,
        pp_nro,
        quincena_arribo_id,
        quincena_desc,
        COUNT(*) as articulos_distintos,
        SUM(saldo_pares) as total_pares
    FROM v_stock_rimec
    WHERE quincena_arribo_id IS NOT NULL
    GROUP BY pp_id, pp_nro, quincena_arribo_id, quincena_desc
    ORDER BY pp_id DESC
    LIMIT 10
""")

if df_stock is not None and not df_stock.empty:
    print(df_stock.to_string(index=False))
    print(f"\nOK - Vista v_stock_rimec expone quincena correctamente")
    print(f"Total PPs con quincena en transito: {len(df_stock)}")
else:
    print("WARNING: No hay stock en transito con quincena asignada")

print("\n" + "=" * 80)
print("VERIFICACION COMPLETADA")
print("=" * 80)
