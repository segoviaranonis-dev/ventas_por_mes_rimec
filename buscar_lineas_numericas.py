# Buscar líneas 2305 y 2400 como números

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("BUSQUEDA: Lineas 2305 y 2400 (como numeros)")
print("="*80 + "\n")

# Buscar las líneas específicas
print("[1] Buscando lineas 2305 y 2400:\n")
query = """
    SELECT
        id,
        codigo_proveedor,
        proveedor_id,
        descripcion,
        marca_id,
        genero_id,
        grupo_estilo_id
    FROM public.linea
    WHERE codigo_proveedor IN (2305, 2400)
    ORDER BY codigo_proveedor
"""
df = get_dataframe(query)

if df is not None and not df.empty:
    print("[OK] Lineas encontradas:\n")
    print(df.to_string(index=False))

    # Para cada línea, buscar referencias
    print("\n" + "="*80)
    print("[2] Referencias disponibles para estas lineas:\n")

    for idx, linea in df.iterrows():
        linea_id = linea['id']
        linea_codigo = linea['codigo_proveedor']

        query_refs = """
            SELECT
                id,
                codigo_proveedor as ref_codigo,
                linea_id
            FROM public.referencia
            WHERE linea_id = :linea_id
            ORDER BY codigo_proveedor
            LIMIT 10
        """
        df_refs = get_dataframe(query_refs, {"linea_id": linea_id})

        print(f"\n  Linea {linea_codigo} (ID: {linea_id}):")
        if df_refs is not None and not df_refs.empty:
            print(f"    {len(df_refs)} referencias encontradas")
            # Buscar específicamente la ref 1579 para linea 2305 y 139 para 2400
            if linea_codigo == 2305 and 1579 in df_refs['ref_codigo'].values:
                print(f"      [OK] Referencia 1579 encontrada")
                ref_id = df_refs[df_refs['ref_codigo'] == 1579].iloc[0]['id']
                print(f"          Ref ID: {ref_id}")
            elif linea_codigo == 2400 and 139 in df_refs['ref_codigo'].values:
                print(f"      [OK] Referencia 139 encontrada")
                ref_id = df_refs[df_refs['ref_codigo'] == 139].iloc[0]['id']
                print(f"          Ref ID: {ref_id}")
            else:
                print(f"      Referencias: {df_refs['ref_codigo'].tolist()[:5]}")
        else:
            print(f"    [ERROR] No hay referencias para esta linea")

else:
    print("[ERROR] Lineas 2305 y 2400 NO encontradas como numeros")
    print("\n[INFO] Mostrando lineas similares:")

    query_similar = """
        SELECT
            id,
            codigo_proveedor,
            proveedor_id
        FROM public.linea
        WHERE codigo_proveedor BETWEEN 2300 AND 2410
        ORDER BY codigo_proveedor
    """
    df_similar = get_dataframe(query_similar)
    if df_similar is not None and not df_similar.empty:
        print(df_similar.to_string(index=False))

print("\n" + "="*80)
