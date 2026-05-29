#!/usr/bin/env python3
"""Verificar que PP-2026-0010 tenga quincena en PP y en v_stock_rimec"""
from core.database import get_dataframe

print("=== 1. PEDIDO PROVEEDOR (cabecera) ===")
pp = get_dataframe("""
    SELECT
        id,
        numero_registro,
        quincena_arribo_id,
        fecha_arribo_estimada
    FROM pedido_proveedor
    WHERE numero_registro = 'PP-2026-0010'
""")

if not pp.empty:
    for col in pp.columns:
        print(f"{col}: {pp[col].iloc[0]}")
else:
    print("PP no encontrado")

print("\n=== 2. STOCK EN TRANSITO (v_stock_rimec) ===")
stock = get_dataframe("""
    SELECT
        det_id,
        pp_id,
        pp_nro,
        eta,
        quincena_arribo_id,
        quincena_desc,
        linea_codigo,
        referencia_codigo,
        saldo_pares
    FROM v_stock_rimec
    WHERE pp_nro = 'PP-2026-0010'
    LIMIT 5
""")

if not stock.empty:
    print(f"Registros encontrados: {len(stock)}")
    for i, row in stock.iterrows():
        print(f"\nArticulo {i+1}:")
        print(f"  det_id: {row['det_id']}")
        print(f"  linea: {row['linea_codigo']}-{row['referencia_codigo']}")
        print(f"  saldo: {row['saldo_pares']} pares")
        print(f"  eta (viejo): {row['eta']}")
        print(f"  quincena_arribo_id (NUEVO): {row['quincena_arribo_id']}")
        print(f"  quincena_desc (NUEVO): {row['quincena_desc']}")
else:
    print("No hay stock en transito para este PP")
