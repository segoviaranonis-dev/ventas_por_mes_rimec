# Verificar estructura de tabla linea

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("VERIFICACION: Estructura de tabla linea")
print("="*80 + "\n")

# 1. Ver columnas de tabla linea
print("[1] Columnas de tabla linea:\n")
query_cols = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
        AND table_name = 'linea'
    ORDER BY ordinal_position
"""
df_cols = get_dataframe(query_cols)
if df_cols is not None and not df_cols.empty:
    print(df_cols.to_string(index=False))

# 2. Ver ejemplos de lineas
print("\n" + "="*80)
print("[2] Ejemplos de lineas registradas (primeras 20):\n")
query_lineas = """
    SELECT
        id,
        codigo_proveedor,
        proveedor_id
    FROM public.linea
    ORDER BY id DESC
    LIMIT 20
"""
df_lineas = get_dataframe(query_lineas)
if df_lineas is not None and not df_lineas.empty:
    print(df_lineas.to_string(index=False))

    # Agrupar por proveedor
    print("\n" + "="*80)
    print("[3] Resumen por proveedor:\n")
    proveedores = df_lineas.groupby('proveedor_id').size()
    for prov_id, count in proveedores.items():
        print(f"  Proveedor {prov_id}: {count} lineas")

# 3. Ver todos los códigos que empiecen con 2 o L2
print("\n" + "="*80)
print("[4] Lineas que empiezan con '2' o 'L2':\n")
query_l2 = """
    SELECT
        id,
        codigo_proveedor,
        proveedor_id
    FROM public.linea
    WHERE codigo_proveedor LIKE '2%'
        OR codigo_proveedor LIKE 'L2%'
    ORDER BY codigo_proveedor
    LIMIT 30
"""
df_l2 = get_dataframe(query_l2)
if df_l2 is not None and not df_l2.empty:
    print(df_l2.to_string(index=False))
else:
    print("[INFO] No hay líneas que empiecen con 2 o L2")

print("\n" + "="*80)
