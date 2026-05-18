#!/usr/bin/env python
"""Corregir colores 122 y 123 con códigos encontrados en color_code"""
from sqlalchemy import create_engine, text
import sys

host = 'aws-1-sa-east-1.pooler.supabase.com'
port = 6543
dbname = 'postgres'
user = 'postgres.extrlcvcgypwazxipvqm'
password = 'IJoFJbT8Qj0Q0w5m'

conn_str = f'postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=require'
engine = create_engine(conn_str, pool_pre_ping=True)

print('='*80)
print('CORRECCION FINAL - COLORES 122 Y 123')
print('='*80)

try:
    with engine.begin() as conn:
        # ANTES
        print('\n[ANTES]')
        print('-'*80)
        result = conn.execute(text("SELECT id, nombre, codigo_proveedor FROM color WHERE id IN (122, 123) ORDER BY id"))
        for row in result:
            print(f'  ID {row[0]} | {row[1]:30} | {row[2]:12}')

        # CORREGIR con UPDATE directo usando color_code de PPD
        print('\n[CORRIGIENDO]')
        print('-'*80)

        updates = [
            (122, """
                UPDATE color
                SET codigo_proveedor = (
                    SELECT DISTINCT color_code::bigint
                    FROM pedido_proveedor_detalle
                    WHERE descp_color = 'ROSA 942' AND color_code IS NOT NULL
                    LIMIT 1
                )
                WHERE id = 122
            """),
            (123, """
                UPDATE color
                SET codigo_proveedor = (
                    SELECT DISTINCT color_code::bigint
                    FROM pedido_proveedor_detalle
                    WHERE descp_color = 'BLANCO 99/MARINO 488' AND color_code IS NOT NULL
                    LIMIT 1
                )
                WHERE id = 123
            """),
        ]

        for color_id, query in updates:
            result = conn.execute(text(query))
            print(f'  ID {color_id}: {result.rowcount} fila actualizada')

        # DESPUES
        print('\n[DESPUES]')
        print('-'*80)
        result = conn.execute(text("SELECT id, nombre, codigo_proveedor FROM color WHERE id IN (122, 123) ORDER BY id"))
        for row in result:
            status = 'CORRECTO' if row[2] < 1000000 else 'INCORRECTO'
            print(f'  ID {row[0]} | {row[1]:30} | {row[2]:12} [{status}]')

        # URLs EN v_stock_web
        print('\n[URLs GENERADAS]')
        print('-'*80)
        result = conn.execute(text("""
            SELECT DISTINCT
                linea_codigo || '-' || referencia_codigo || '-' || material_code || '-' || color_code || '.jpg' as url,
                color_nombre
            FROM v_stock_web
            WHERE color_id IN (122, 123)
        """))
        for row in result:
            print(f'  {row[1]:30} -> {row[0]}')

    print('\n' + '='*80)
    print('CORRECCION COMPLETADA')
    print('='*80 + '\n')

except Exception as e:
    print(f'\nERROR: {e}', file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
