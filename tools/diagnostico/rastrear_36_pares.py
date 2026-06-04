#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RASTREO FORENSE: 36 pares bloqueados en PP-2026-0010
"""
from core.database import get_dataframe
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

print("=" * 100)
print("RASTREO FORENSE: 36 pares bloqueados en PP-2026-0010")
print("=" * 100)

# 1. Información del PP
print("\n1. PEDIDO PROVEEDOR:")
df_pp = get_dataframe("""
    SELECT
        id,
        numero_registro,
        estado,
        proveedor_importacion_id,
        quincena_arribo_id
    FROM pedido_proveedor
    WHERE numero_registro = 'PP-2026-0010'
""")

if df_pp is None or df_pp.empty:
    print("ERROR - PP no encontrado")
    exit(1)

print(df_pp.to_string(index=False))
pp_id = int(df_pp['id'].iloc[0])

# 2. Detalles del PP (artículos)
print(f"\n2. ARTICULOS DEL PP (pedido_proveedor_detalle):")
df_ppd = get_dataframe("""
    SELECT
        id as ppd_id,
        linea,
        referencia,
        material_code,
        color_code,
        cantidad_pares as pares_totales,
        COALESCE(pares_vendidos, 0) as pares_vendidos,
        cantidad_pares - COALESCE(pares_vendidos, 0) as saldo_disponible
    FROM pedido_proveedor_detalle
    WHERE pedido_proveedor_id = :pp_id
    ORDER BY id
""", {"pp_id": pp_id})

if df_ppd is not None and not df_ppd.empty:
    print(df_ppd.to_string(index=False))
    print(f"\nTOTAL PARES:")
    print(f"  Iniciales: {df_ppd['pares_totales'].sum()}")
    print(f"  Vendidos: {df_ppd['pares_vendidos'].sum()}")
    print(f"  Disponibles: {df_ppd['saldo_disponible'].sum()}")
else:
    print("WARNING - No hay detalles")

# 3. Facturas Internas del PP
print(f"\n3. FACTURAS INTERNAS (factura_interna):")
df_fi = get_dataframe("""
    SELECT
        fi.id as fi_id,
        fi.nro_factura,
        fi.estado,
        fi.marca,
        fi.caso,
        fi.total_pares,
        fi.pedido_id,
        pvr.nro_pedido,
        pvr.estado as pedido_estado,
        fi.created_at
    FROM factura_interna fi
    LEFT JOIN pedido_venta_rimec pvr ON pvr.id = fi.pedido_id
    WHERE fi.pp_id = :pp_id
    ORDER BY fi.id
""", {"pp_id": pp_id})

if df_fi is not None and not df_fi.empty:
    print(df_fi.to_string(index=False))
else:
    print("WARNING - No hay facturas internas")

# 4. Detalles de cada FI (qué artículos tiene cada una)
print(f"\n4. ITEMS DE CADA FACTURA INTERNA:")
for _, fi_row in df_fi.iterrows():
    fi_id = int(fi_row['fi_id'])
    nro_fi = fi_row['nro_factura']
    estado_fi = fi_row['estado']

    print(f"\n{nro_fi} ({estado_fi}):")

    df_fid = get_dataframe("""
        SELECT
            fid.id as fid_id,
            fid.ppd_id,
            fid.pares,
            fid.cajas,
            fid.subtotal,
            fid.linea_snapshot
        FROM factura_interna_detalle fid
        WHERE fid.factura_id = :fi_id
        ORDER BY fid.id
    """, {"fi_id": fi_id})

    if df_fid is not None and not df_fid.empty:
        # Parsear snapshot para mostrar info legible
        for idx, det_row in df_fid.iterrows():
            import json
            import ast
            snap = {}
            try:
                ls = det_row['linea_snapshot']
                if isinstance(ls, dict):
                    snap = ls
                elif isinstance(ls, str):
                    try:
                        snap = json.loads(ls)
                    except:
                        snap = ast.literal_eval(ls)
            except:
                pass

            linea = snap.get('linea_codigo', '?')
            ref = snap.get('ref_codigo', '?')
            print(f"  - L{linea} R{ref}: {det_row['pares']} pares (ppd_id: {det_row['ppd_id']})")

        print(f"  Total: {df_fid['pares'].sum()} pares")
    else:
        print("  (sin items)")

# 5. ANÁLISIS: Qué artículos tienen pares_vendidos > 0
print(f"\n5. ARTICULOS CON STOCK BLOQUEADO (pares_vendidos > 0):")
if df_ppd is not None and not df_ppd.empty:
    bloqueados = df_ppd[df_ppd['pares_vendidos'] > 0]
    if not bloqueados.empty:
        print(bloqueados[['ppd_id', 'linea', 'referencia', 'pares_totales', 'pares_vendidos', 'saldo_disponible']].to_string(index=False))
        print(f"\nTOTAL BLOQUEADO: {bloqueados['pares_vendidos'].sum()} pares")
    else:
        print("No hay artículos bloqueados")

# 6. VERIFICACIÓN: Función revertir_stock_fi
print(f"\n6. VERIFICACION: Existe funcion revertir_stock_fi en BD?")
df_func = get_dataframe("""
    SELECT proname, prosrc
    FROM pg_proc
    WHERE proname = 'revertir_stock_fi'
""")

if df_func is not None and not df_func.empty:
    print("SI - La funcion existe")
else:
    print("NO - La funcion NO existe (esto seria un problema)")

# 7. DIAGNÓSTICO FINAL
print("\n" + "=" * 100)
print("DIAGNOSTICO:")

if df_fi is not None and not df_fi.empty:
    reservadas = df_fi[df_fi['estado'] == 'RESERVADA']
    anuladas = df_fi[df_fi['estado'] == 'ANULADA']

    print(f"\nFacturas Internas encontradas: {len(df_fi)}")
    print(f"  - RESERVADAS: {len(reservadas)} (bloqueando stock)")
    print(f"  - ANULADAS: {len(anuladas)}")

    if not reservadas.empty:
        print(f"\nFIs RESERVADAS que estan bloqueando stock:")
        for _, r in reservadas.iterrows():
            print(f"  {r['nro_factura']}: {r['total_pares']} pares bloqueados")
            if r['pedido_id']:
                print(f"    Pedido: {r['nro_pedido']} (estado: {r['pedido_estado']})")
            else:
                print(f"    Sin pedido asociado (huerfana)")

        print(f"\nACCION REQUERIDA:")
        for _, r in reservadas.iterrows():
            print(f"  Anular {r['nro_factura']} (ID: {r['fi_id']})")
            print(f"    Esto liberara {r['total_pares']} pares")

print("\n" + "=" * 100)
