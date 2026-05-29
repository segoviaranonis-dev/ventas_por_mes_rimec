# Verificar estructura de tablas relacionadas con precios

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("VERIFICACION: Estructura de tablas de precios")
print("="*80 + "\n")

# 1. Verificar columnas de precio_evento
print("[1] Columnas de tabla precio_evento:\n")
query_pe = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
        AND table_name = 'precio_evento'
    ORDER BY ordinal_position
"""
df_pe = get_dataframe(query_pe)
if df_pe is not None and not df_pe.empty:
    print(df_pe.to_string(index=False))
else:
    print("[ERROR] No se pudo obtener estructura de precio_evento")

# 2. Buscar el pedido PP-2026-0010 (sin JOIN complicado)
print("\n" + "="*80)
print("[2] Buscando pedido PP-2026-0010...\n")

query_pp_simple = """
    SELECT *
    FROM public.pedido_proveedor
    WHERE numero_registro LIKE '%0010%'
    ORDER BY id DESC
    LIMIT 5
"""
df_pp = get_dataframe(query_pp_simple)
if df_pp is not None and not df_pp.empty:
    print(f"Columnas disponibles: {df_pp.columns.tolist()}\n")
    print(df_pp[['id', 'numero_registro', 'estado']].to_string(index=False))
else:
    print("[INFO] No se encontraron pedidos con 0010")

# 3. Verificar items del último pedido de proveedor
print("\n" + "="*80)
print("[3] Items del último pedido proveedor:\n")

query_items = """
    SELECT
        ppd.id,
        ppd.pedido_proveedor_id,
        ppd.linea,
        ppd.referencia,
        ppd.material_code,
        ppd.color_code,
        ppd.cantidad_pares
    FROM public.pedido_proveedor_detalle ppd
    ORDER BY ppd.id DESC
    LIMIT 10
"""
df_items = get_dataframe(query_items)
if df_items is not None and not df_items.empty:
    print(df_items.to_string(index=False))

print("\n" + "="*80)
