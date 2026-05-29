# Diagnóstico específico de los 2 items sin precio

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("DIAGNOSTICO: Items sin precio en PP-2026-0010")
print("="*80 + "\n")

pp_id = 10

# 1. Ver datos completos del pedido
print("[1] Datos del pedido proveedor:\n")
query_pp = """
    SELECT
        pp.id,
        pp.numero_registro,
        pp.proveedor_importacion_id,
        pp.id_intencion_compra,
        ic.precio_evento_id
    FROM public.pedido_proveedor pp
    LEFT JOIN public.intencion_compra ic ON ic.id = pp.id_intencion_compra
    WHERE pp.id = :pp_id
"""
df_pp = get_dataframe(query_pp, {"pp_id": pp_id})
if df_pp is not None and not df_pp.empty:
    print(df_pp.to_string(index=False))
    proveedor_id = df_pp.iloc[0]['proveedor_importacion_id']
    precio_evento_id = df_pp.iloc[0]['precio_evento_id']
    print(f"\n[INFO] Proveedor ID: {proveedor_id}")
    print(f"[INFO] Precio Evento ID: {precio_evento_id}")

# 2. Ver los 2 items problemáticos
print("\n" + "="*80)
print("[2] Items sin precio (IDs 954 y 955):\n")

query_items = """
    SELECT *
    FROM public.pedido_proveedor_detalle
    WHERE id IN (954, 955)
    ORDER BY id
"""
df_items = get_dataframe(query_items)
if df_items is not None and not df_items.empty:
    for idx, item in df_items.iterrows():
        print(f"\n--- Item ID {item['id']} ---")
        print(f"  Linea: {item['linea']}")
        print(f"  Referencia: {item['referencia']}")
        print(f"  Material: {item['material_code']}")
        print(f"  Color: {item['color_code']}")
        print(f"  Nombre: {item['nombre']}")
        print(f"  Pares: {item['cantidad_pares']}")

# 3. Buscar estos SKUs en las tablas maestras
print("\n" + "="*80)
print("[3] Buscando SKUs en tablas maestras (linea, referencia, material):\n")

for idx, item in df_items.iterrows():
    linea_code = item['linea']
    ref_code = item['referencia']
    mat_code = item['material_code']

    print(f"\n--- SKU: {linea_code}:{ref_code} Material: {mat_code} ---")

    # Buscar linea
    query_linea = """
        SELECT id, codigo_proveedor, proveedor_id
        FROM public.linea
        WHERE codigo_proveedor = :codigo
            AND proveedor_id = :prov_id
        LIMIT 1
    """
    df_linea = get_dataframe(query_linea, {"codigo": linea_code, "prov_id": proveedor_id})

    if df_linea is not None and not df_linea.empty:
        linea_id = df_linea.iloc[0]['id']
        print(f"  [OK] Linea encontrada - ID: {linea_id}")

        # Buscar referencia
        query_ref = """
            SELECT id, codigo_proveedor
            FROM public.referencia
            WHERE codigo_proveedor = :codigo
                AND linea_id = :linea_id
            LIMIT 1
        """
        df_ref = get_dataframe(query_ref, {"codigo": ref_code, "linea_id": linea_id})

        if df_ref is not None and not df_ref.empty:
            ref_id = df_ref.iloc[0]['id']
            print(f"  [OK] Referencia encontrada - ID: {ref_id}")

            # Buscar material
            query_mat = """
                SELECT id, codigo_proveedor
                FROM public.material
                WHERE codigo_proveedor = :codigo
                    AND proveedor_id = :prov_id
                LIMIT 1
            """
            df_mat = get_dataframe(query_mat, {"codigo": mat_code, "prov_id": proveedor_id})

            if df_mat is not None and not df_mat.empty:
                mat_id = df_mat.iloc[0]['id']
                print(f"  [OK] Material encontrado - ID: {mat_id}")

                # Ahora buscar el precio
                if precio_evento_id:
                    print(f"\n  [4] Buscando precio en precio_lista:")
                    print(f"      Evento ID: {precio_evento_id}")
                    print(f"      Linea ID: {linea_id}, Ref ID: {ref_id}, Mat ID: {mat_id}")

                    query_precio = """
                        SELECT
                            pl.id,
                            pl.lpn,
                            pl.lpc02,
                            pl.lpc03,
                            pl.lpc04,
                            pl.nombre_caso_aplicado,
                            pl.caso_id
                        FROM public.precio_lista pl
                        WHERE pl.evento_id = :evento_id
                            AND pl.linea_id = :linea_id
                            AND pl.referencia_id = :ref_id
                            AND pl.material_id = :mat_id
                        LIMIT 1
                    """
                    df_precio = get_dataframe(query_precio, {
                        "evento_id": precio_evento_id,
                        "linea_id": linea_id,
                        "ref_id": ref_id,
                        "mat_id": mat_id
                    })

                    if df_precio is not None and not df_precio.empty:
                        print(f"      [OK] PRECIO ENCONTRADO!")
                        print(f"          LPN: {df_precio.iloc[0]['lpn']}")
                        print(f"          LPC02: {df_precio.iloc[0]['lpc02']}")
                        print(f"          LPC03: {df_precio.iloc[0]['lpc03']}")
                        print(f"          Caso: {df_precio.iloc[0]['nombre_caso_aplicado']}")
                    else:
                        print(f"      [ERROR] NO HAY PRECIO para este SKU en el evento {precio_evento_id}")
                        print(f"      Este es el problema: el SKU no tiene precio asignado en precio_lista")
                else:
                    print(f"  [ERROR] El pedido NO tiene precio_evento_id asociado")
            else:
                print(f"  [ERROR] Material {mat_code} NO encontrado")
        else:
            print(f"  [ERROR] Referencia {ref_code} NO encontrada para linea {linea_id}")
    else:
        print(f"  [ERROR] Linea {linea_code} NO encontrada para proveedor {proveedor_id}")

print("\n" + "="*80)
print("Fin del diagnóstico")
print("="*80 + "\n")
