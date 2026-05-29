# Buscar referencia 1579

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("BUSQUEDA: Referencia 1579")
print("="*80 + "\n")

# 1. Buscar referencia 1579 en cualquier línea
print("[1] Buscando referencia 1579 en toda la BD:\n")
query_ref = """
    SELECT
        r.id as ref_id,
        r.codigo_proveedor as ref_codigo,
        r.linea_id,
        l.codigo_proveedor as linea_codigo,
        l.proveedor_id
    FROM public.referencia r
    JOIN public.linea l ON l.id = r.linea_id
    WHERE r.codigo_proveedor = 1579
"""
df_ref = get_dataframe(query_ref)

if df_ref is not None and not df_ref.empty:
    print("[OK] Referencia 1579 encontrada:\n")
    print(df_ref.to_string(index=False))

    ref_info = df_ref.iloc[0]
    print(f"\n[INFO] La referencia 1579 pertenece a la linea {ref_info['linea_codigo']}")
    print(f"[INFO] Pero el item del pedido dice que deberia ser linea 2305")

    if ref_info['linea_codigo'] != 2305:
        print(f"\n[PROBLEMA] Hay un conflicto:")
        print(f"  - Item del pedido: Linea 2305, Ref 1579")
        print(f"  - BD: Ref 1579 pertenece a linea {ref_info['linea_codigo']}")
else:
    print("[ERROR] Referencia 1579 NO encontrada en la BD")

# 2. Ver todas las referencias de la línea 2305
print("\n" + "="*80)
print("[2] Todas las referencias disponibles para linea 2305:\n")
query_refs_2305 = """
    SELECT
        r.id,
        r.codigo_proveedor as ref_codigo
    FROM public.referencia r
    WHERE r.linea_id = 221
    ORDER BY r.codigo_proveedor
"""
df_refs = get_dataframe(query_refs_2305)

if df_refs is not None and not df_refs.empty:
    print(f"[INFO] {len(df_refs)} referencias encontradas:\n")
    print(df_refs.to_string(index=False))
else:
    print("[ERROR] No hay referencias para linea 2305")

# 3. Ver datos del item problemático en pedido_proveedor_detalle
print("\n" + "="*80)
print("[3] Datos originales del item 954 en pedido_proveedor_detalle:\n")
query_item = """
    SELECT
        id,
        pedido_proveedor_id,
        linea,
        referencia,
        style_code,
        material_code,
        color_code,
        nombre,
        cantidad_pares
    FROM public.pedido_proveedor_detalle
    WHERE id = 954
"""
df_item = get_dataframe(query_item)

if df_item is not None and not df_item.empty:
    print(df_item.to_string(index=False))
    print(f"\n[INFO] El item original tiene:")
    print(f"  Linea: {df_item.iloc[0]['linea']}")
    print(f"  Referencia: {df_item.iloc[0]['referencia']}")
    print(f"  Style: {df_item.iloc[0]['style_code']}")

print("\n" + "="*80)
