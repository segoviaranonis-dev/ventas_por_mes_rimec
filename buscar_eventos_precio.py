# Buscar eventos de precio disponibles y verificar proveedor

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("ANALISIS: Eventos de precio disponibles")
print("="*80 + "\n")

# 1. Ver eventos de precio recientes
print("[1] Eventos de precio recientes:\n")
query_eventos = """
    SELECT
        id,
        nombre_evento,
        estado,
        proveedor_id,
        fecha_vigencia_desde,
        fecha_vigencia_hasta,
        created_at
    FROM public.precio_evento
    ORDER BY created_at DESC
    LIMIT 10
"""
df_eventos = get_dataframe(query_eventos)
if df_eventos is not None and not df_eventos.empty:
    print(df_eventos.to_string(index=False))
else:
    print("[INFO] No hay eventos de precio")

# 2. Verificar proveedor 654
print("\n" + "="*80)
print("[2] Datos del proveedor ID 654:\n")
query_prov = """
    SELECT *
    FROM public.proveedor
    WHERE id = 654
"""
df_prov = get_dataframe(query_prov)
if df_prov is not None and not df_prov.empty:
    print(df_prov.to_string(index=False))
else:
    print("[ERROR] Proveedor 654 no encontrado")

# 3. Ver líneas disponibles para proveedor 654
print("\n" + "="*80)
print("[3] Lineas registradas para proveedor 654:\n")
query_lineas = """
    SELECT
        id,
        codigo_proveedor,
        descp_linea
    FROM public.linea
    WHERE proveedor_id = 654
    ORDER BY codigo_proveedor
    LIMIT 20
"""
df_lineas = get_dataframe(query_lineas)
if df_lineas is not None and not df_lineas.empty:
    print(df_lineas.to_string(index=False))
    print(f"\n[INFO] Total lineas encontradas: {len(df_lineas)}")

    # Ver si las líneas 2305 y 2400 existen
    if '2305' in df_lineas['codigo_proveedor'].values:
        print("[OK] Linea 2305 SI existe")
    else:
        print("[ERROR] Linea 2305 NO existe")

    if '2400' in df_lineas['codigo_proveedor'].values:
        print("[OK] Linea 2400 SI existe")
    else:
        print("[ERROR] Linea 2400 NO existe")
else:
    print("[ERROR] No hay líneas registradas para proveedor 654")

# 4. Buscar líneas con código similar (por si tiene prefijo L)
print("\n" + "="*80)
print("[4] Buscando lineas con codigo L2305 o L2400:\n")
query_lineas_L = """
    SELECT
        id,
        codigo_proveedor,
        proveedor_id,
        descp_linea
    FROM public.linea
    WHERE codigo_proveedor IN ('L2305', 'L2400', '2305', '2400')
    LIMIT 10
"""
df_lineas_L = get_dataframe(query_lineas_L)
if df_lineas_L is not None and not df_lineas_L.empty:
    print(df_lineas_L.to_string(index=False))
else:
    print("[INFO] No se encontraron líneas con esos códigos")

print("\n" + "="*80)
