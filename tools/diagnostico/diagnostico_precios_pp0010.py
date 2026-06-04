# Diagnóstico de precios para pedido proveedor PP-2026-0010

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("DIAGNOSTICO: Precios desconectados en PP-2026-0010")
print("="*80 + "\n")

# 1. Verificar el pedido proveedor
print("[1] Verificando pedido proveedor PP-2026-0010...\n")
query_pp = """
    SELECT
        pp.id,
        pp.numero_registro,
        pp.estado,
        pp.id_intencion_compra,
        ic.precio_evento_id,
        pe.nombre as evento_nombre,
        pe.estado as evento_estado
    FROM public.pedido_proveedor pp
    LEFT JOIN public.intencion_compra ic ON ic.id = pp.id_intencion_compra
    LEFT JOIN public.precio_evento pe ON pe.id = ic.precio_evento_id
    WHERE pp.numero_registro = 'PP-2026-0010'
"""

df_pp = get_dataframe(query_pp)
if df_pp is not None and not df_pp.empty:
    print(df_pp.to_string(index=False))
    pp_id = df_pp.iloc[0]['id']
    precio_evento_id = df_pp.iloc[0]['precio_evento_id']
    print(f"\n[OK] Pedido encontrado - ID: {pp_id}")
    print(f"[INFO] Evento de precio ID: {precio_evento_id}")
else:
    print("[ERROR] Pedido PP-2026-0010 no encontrado")
    sys.exit(1)

# 2. Verificar los items con problemas
print("\n" + "="*80)
print("[2] Verificando items sin precio...\n")

query_items = """
    SELECT
        ppd.id,
        ppd.linea,
        ppd.referencia,
        ppd.material_code,
        ppd.color_code,
        ppd.nombre,
        ppd.cantidad_pares,
        ppd.unit_fob_ajustado
    FROM public.pedido_proveedor_detalle ppd
    WHERE ppd.pedido_proveedor_id = :pp_id
        AND (ppd.linea = 'L2305' AND ppd.referencia = 'R1579'
             OR ppd.linea = 'L2400' AND ppd.referencia = 'R139')
"""

df_items = get_dataframe(query_items, {"pp_id": pp_id})
if df_items is not None and not df_items.empty:
    print(df_items.to_string(index=False))
    print(f"\n[OK] Se encontraron {len(df_items)} items con problemas")
else:
    print("[INFO] No se encontraron los items específicos mencionados")

# 3. Verificar si existen en las tablas maestras
print("\n" + "="*80)
print("[3] Verificando existencia en tablas maestras...\n")

for idx, item in df_items.iterrows():
    linea = item['linea']
    ref = item['referencia']
    material = item['material_code']

    query_maestro = """
        SELECT
            l.id as linea_id,
            l.codigo_proveedor as linea_codigo,
            r.id as referencia_id,
            r.codigo_proveedor as ref_codigo,
            m.id as material_id,
            m.codigo_proveedor as mat_codigo,
            lr.id as linea_ref_id
        FROM public.linea l
        LEFT JOIN public.referencia r ON r.linea_id = l.id
            AND r.codigo_proveedor = :ref
        LEFT JOIN public.material m ON m.codigo_proveedor = :material
        LEFT JOIN public.linea_referencia lr ON lr.linea_id = l.id
            AND lr.referencia_id = r.id
        WHERE l.codigo_proveedor = :linea
        LIMIT 1
    """

    df_maestro = get_dataframe(query_maestro, {
        "linea": linea,
        "ref": ref,
        "material": material
    })

    print(f"\n  SKU: {linea}:{ref} - Material: {material}")
    if df_maestro is not None and not df_maestro.empty:
        row = df_maestro.iloc[0]
        print(f"    Linea ID: {row['linea_id']}")
        print(f"    Referencia ID: {row['referencia_id']}")
        print(f"    Material ID: {row['material_id']}")
        print(f"    Linea-Ref ID: {row['linea_ref_id']}")

        # 4. Buscar precios para este SKU
        if precio_evento_id and row['linea_id'] and row['referencia_id'] and row['material_id']:
            query_precio = """
                SELECT
                    pl.id,
                    pl.lpn,
                    pl.lpc02,
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
                "linea_id": row['linea_id'],
                "ref_id": row['referencia_id'],
                "mat_id": row['material_id']
            })

            if df_precio is not None and not df_precio.empty:
                print(f"    [OK] PRECIO ENCONTRADO:")
                print(f"        LPN: {df_precio.iloc[0]['lpn']}")
                print(f"        LPC02: {df_precio.iloc[0]['lpc02']}")
            else:
                print(f"    [ERROR] NO HAY PRECIO en precio_lista para este SKU")
                print(f"        Evento ID: {precio_evento_id}")
    else:
        print(f"    [ERROR] SKU no encontrado en tablas maestras")

print("\n" + "="*80)
print("Fin del diagnóstico")
print("="*80 + "\n")
