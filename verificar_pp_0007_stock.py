#!/usr/bin/env python3
from core.database import get_dataframe

df = get_dataframe("""
    SELECT
        pp_nro,
        quincena_arribo_id,
        quincena_desc,
        COUNT(*) as articulos,
        SUM(saldo_pares) as total_saldo
    FROM v_stock_rimec
    WHERE pp_nro = 'PP-2026-0007'
    GROUP BY pp_nro, quincena_arribo_id, quincena_desc
""")

print("=== PP-2026-0007 en v_stock_rimec ===")
if not df.empty:
    for col in df.columns:
        print(f"{col}: {df[col].iloc[0]}")
else:
    print("PP sin stock en tránsito")
