#!/usr/bin/env python
"""OT-2026-045: Corregir colores con codigo_proveedor corrupto (IDs 122, 123)"""
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
print('OT-2026-045: CORRECCION COLORES CORRUPTOS (IDs 122, 123)')
print('='*80)

try:
    with engine.begin() as conn:
        # ANTES
        print('\n[1] Estado ANTES de la correccion:')
        print('-'*80)
        result = conn.execute(text("""
            SELECT id, nombre, codigo_proveedor, proveedor_id
            FROM color
            WHERE id IN (122, 123)
            ORDER BY id
        """))
        for row in result:
            print(f'  ID {row[0]:3} | {row[1]:30} | Codigo: {row[2]:12} [INCORRECTO]')

        # CORREGIR
        print('\n[2] Aplicando correccion desde pedido_proveedor_detalle...')
        print('-'*80)

        update_query = """
        UPDATE color
        SET codigo_proveedor = (
            SELECT DISTINCT id_color
            FROM pedido_proveedor_detalle
            WHERE descp_color = color.nombre
              AND id_color IS NOT NULL
            LIMIT 1
        )
        WHERE id IN (122, 123)
          AND EXISTS (
              SELECT 1 FROM pedido_proveedor_detalle
              WHERE descp_color = color.nombre AND id_color IS NOT NULL
          )
        """

        result = conn.execute(text(update_query))
        print(f'  [OK] Filas actualizadas: {result.rowcount}')

        # DESPUES
        print('\n[3] Estado DESPUES de la correccion:')
        print('-'*80)
        result = conn.execute(text("""
            SELECT id, nombre, codigo_proveedor, proveedor_id
            FROM color
            WHERE id IN (122, 123)
            ORDER BY id
        """))
        for row in result:
            status = '[CORRECTO]' if row[2] < 1000000 else '[AUN INCORRECTO]'
            print(f'  ID {row[0]:3} | {row[1]:30} | Codigo: {row[2]:12} {status}')

        # VERIFICAR EN v_stock_web
        print('\n[4] Verificacion en v_stock_web:')
        print('-'*80)
        result = conn.execute(text("""
            SELECT DISTINCT
                linea_codigo,
                referencia_codigo,
                material_code,
                color_code,
                color_nombre
            FROM v_stock_web
            WHERE color_id IN (122, 123)
            ORDER BY linea_codigo, referencia_codigo
        """))
        rows = result.fetchall()
        if rows:
            for row in rows:
                url = f'{row[0]}-{row[1]}-{row[2]}-{row[3]}.jpg'
                print(f'  {row[4]:30} -> {url}')
        else:
            print('  [!] No se encontraron productos en v_stock_web con estos colores')

    print('\n' + '='*80)
    print('[OK] CORRECCION COMPLETADA')
    print('='*80 + '\n')

except Exception as e:
    print(f'\n[ERROR] {e}', file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
