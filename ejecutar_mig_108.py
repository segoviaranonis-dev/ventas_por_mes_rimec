#!/usr/bin/env python3
"""Ejecutar migración 108: Backfill gradas_fmt en 71 PVs"""
from core.database import commit_query, get_dataframe

print("=" * 80)
print("MIGRACION 108: Backfill gradas_fmt en 71 PVs")
print("=" * 80)

with open("migrations/108_backfill_gradas_fmt_71pv.sql", "r", encoding="utf-8") as f:
    sql = f.read()

try:
    # Antes de la migración
    print("\nANTES del backfill:")
    df_antes = get_dataframe("""
        SELECT
          COUNT(*) AS total_items,
          COUNT(*) FILTER (WHERE linea_snapshot->>'gradas_fmt' != '') AS con_gradas,
          COUNT(*) FILTER (WHERE linea_snapshot->>'gradas_fmt' = '') AS sin_gradas
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        WHERE fi.pv_global IS NOT NULL
    """)
    if df_antes is not None and not df_antes.empty:
        print(df_antes.to_string(index=False))

    # Ejecutar migración
    print("\nEjecutando backfill...")
    commit_query(sql)
    print("OK - Migracion 108 ejecutada correctamente")

    # Después de la migración
    print("\nDESPUES del backfill:")
    df_despues = get_dataframe("""
        SELECT
          COUNT(*) AS total_items,
          COUNT(*) FILTER (WHERE linea_snapshot->>'gradas_fmt' != '') AS con_gradas,
          COUNT(*) FILTER (WHERE linea_snapshot->>'gradas_fmt' = '') AS sin_gradas
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        WHERE fi.pv_global IS NOT NULL
    """)
    if df_despues is not None and not df_despues.empty:
        print(df_despues.to_string(index=False))

    # Mostrar ejemplos
    print("\nEJEMPLOS de gradas_fmt actualizados:")
    df_ejemplos = get_dataframe("""
        SELECT
          fi.pv_global,
          fi.nro_factura,
          fid.pares,
          fid.linea_snapshot->>'gradas_fmt' AS gradas_fmt
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        WHERE fi.pv_global IS NOT NULL
        ORDER BY fi.pv_global DESC
        LIMIT 10
    """)
    if df_ejemplos is not None and not df_ejemplos.empty:
        print(df_ejemplos.to_string(index=False))

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("MIGRACION COMPLETADA")
print("=" * 80)