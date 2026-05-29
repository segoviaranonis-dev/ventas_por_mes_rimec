#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Asignar quincena a PP-2026-0010 para pruebas
"""
from core.database import get_dataframe, commit_query

# Verificar estado actual
print("=" * 80)
print("Estado actual PP-2026-0010:")
df = get_dataframe("""
    SELECT
        id,
        numero_registro,
        quincena_arribo_id,
        fecha_arribo_estimada
    FROM pedido_proveedor
    WHERE numero_registro = 'PP-2026-0010'
""")

if df is not None and not df.empty:
    print(df.to_string(index=False))
    pp_id = int(df['id'].iloc[0])
    quincena_actual = df['quincena_arribo_id'].iloc[0]

    if quincena_actual:
        print(f"\nPP ya tiene quincena asignada: {quincena_actual}")
    else:
        print("\nAsignando quincena 10 (2da Quincena de Mayo)...")
        ok = commit_query("""
            UPDATE pedido_proveedor
            SET quincena_arribo_id = 10
            WHERE id = :pp_id
        """, {"pp_id": pp_id})

        if ok:
            print("OK - Quincena asignada exitosamente")

            # Verificar propagacion
            print("\nVerificando propagacion en v_stock_rimec...")
            df_stock = get_dataframe("""
                SELECT
                    pp_id,
                    pp_nro,
                    quincena_arribo_id,
                    quincena_desc,
                    COUNT(*) as articulos
                FROM v_stock_rimec
                WHERE pp_nro = 'PP-2026-0010'
                GROUP BY pp_id, pp_nro, quincena_arribo_id, quincena_desc
            """)

            if df_stock is not None and not df_stock.empty:
                print("OK - Vista actualizada automaticamente:")
                print(df_stock.to_string(index=False))
            else:
                print("WARNING - No hay stock en transito para este PP")
        else:
            print("ERROR - No se pudo actualizar")
else:
    print("ERROR - PP no encontrado")

print("=" * 80)
