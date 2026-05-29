#!/usr/bin/env python3
"""Verificar si PP-2026-0007 tiene quincena_arribo_id en la DB"""
from core.database import get_dataframe

# Verificar PP-2026-0007
pp = get_dataframe("""
    SELECT
        pp.id,
        pp.numero_registro,
        pp.id_intencion_compra,
        pp.quincena_arribo_id,
        pp.fecha_arribo_estimada,
        ic.numero_registro as ic_nro,
        ic.quincena_arribo_id as ic_quincena,
        qa.descripcion as quincena_desc
    FROM pedido_proveedor pp
    LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
    LEFT JOIN quincena_arribo qa ON qa.id = pp.quincena_arribo_id
    WHERE pp.numero_registro = 'PP-2026-0007'
""")

print("\n=== PP-2026-0007 ===")
if not pp.empty:
    for col in pp.columns:
        print(f"{col}: {pp[col].iloc[0]}")
else:
    print("PP no encontrado")

# Verificar IC-2026-0042
ic = get_dataframe("""
    SELECT
        id,
        numero_registro,
        quincena_arribo_id,
        qa.descripcion as quincena_desc
    FROM intencion_compra ic
    LEFT JOIN quincena_arribo qa ON qa.id = ic.quincena_arribo_id
    WHERE numero_registro = 'IC-2026-0042'
""")

print("\n=== IC-2026-0042 ===")
if not ic.empty:
    for col in ic.columns:
        print(f"{col}: {ic[col].iloc[0]}")
else:
    print("IC no encontrada")
