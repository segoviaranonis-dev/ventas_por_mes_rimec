#!/usr/bin/env python3
"""Ejecutar migración 107: pv_global secuencial"""
from core.database import commit_query, get_dataframe

print("=" * 80)
print("MIGRACIÓN 107: Agregar pv_global y backfill")
print("=" * 80)

with open("migrations/107_pv_global_secuencial.sql", "r", encoding="utf-8") as f:
    sql = f.read()

try:
    commit_query(sql)
    print("\nOK - Migración 107 ejecutada correctamente")

    # Verificar resultado
    df = get_dataframe("""
        SELECT estado, COUNT(*) as total,
               MIN(pv_global) as min_pv,
               MAX(pv_global) as max_pv
        FROM factura_interna
        GROUP BY estado
        ORDER BY estado
    """)
    print("\nVerificación:")
    if df is not None and not df.empty:
        print(df.to_string(index=False))

    # Mostrar últimas 5
    df = get_dataframe("""
        SELECT pv_global, nro_factura, estado
        FROM factura_interna
        WHERE pv_global IS NOT NULL
        ORDER BY pv_global DESC
        LIMIT 5
    """)
    print("\nÚltimas 5 FIs numeradas:")
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            print(f"  PV{row['pv_global']:06d} - {row['nro_factura']} ({row['estado']})")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("MIGRACIÓN COMPLETADA")
print("=" * 80)
