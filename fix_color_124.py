#!/usr/bin/env python
"""Corregir codigo_proveedor del color ID 124 (TAN 1080)"""
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
print('CORRECCION COLOR ID 124 - TAN 1080')
print('='*80)

# Verificar estado actual
print('\n[1] Estado ANTES de la correccion:')
print('-'*80)

query_before = """
SELECT id, nombre, codigo_proveedor, proveedor_id
FROM color
WHERE id = 124
"""

try:
    with engine.connect() as conn:
        result = conn.execute(text(query_before))
        row = result.fetchone()
        if row:
            print(f'  ID: {row[0]}')
            print(f'  Nombre: {row[1]}')
            print(f'  Codigo Proveedor ACTUAL: {row[2]} [INCORRECTO]')
            print(f'  Proveedor ID: {row[3]}')
        else:
            print('  [ERROR] Color ID 124 no encontrado')
            sys.exit(1)

    # Aplicar corrección
    print('\n[2] Aplicando correccion...')
    print('-'*80)

    update_query = """
    UPDATE color
    SET codigo_proveedor = 89673
    WHERE id = 124
    """

    with engine.begin() as conn:
        result = conn.execute(text(update_query))
        print(f'  [OK] Filas actualizadas: {result.rowcount}')

    # Verificar estado después
    print('\n[3] Estado DESPUES de la correccion:')
    print('-'*80)

    with engine.connect() as conn:
        result = conn.execute(text(query_before))
        row = result.fetchone()
        if row:
            print(f'  ID: {row[0]}')
            print(f'  Nombre: {row[1]}')
            print(f'  Codigo Proveedor NUEVO: {row[2]} [CORRECTO]')
            print(f'  Proveedor ID: {row[3]}')

    # Verificar impacto en v_stock_web
    print('\n[4] Verificacion en v_stock_web (producto 8246-1176):')
    print('-'*80)

    query_verify = """
    SELECT DISTINCT
        linea_codigo,
        referencia_codigo,
        material_code,
        color_code,
        color_nombre
    FROM v_stock_web
    WHERE linea_codigo = '8246' AND referencia_codigo = '1176'
    ORDER BY color_code
    """

    with engine.connect() as conn:
        result = conn.execute(text(query_verify))
        rows = result.fetchall()
        for row in rows:
            url = f'{row[0]}-{row[1]}-{row[2]}-{row[3]}.jpg'
            print(f'  {row[4]:15} -> {url}')
            if row[3] == 89673:
                print(f'                    {"^"*len(url)} [CORRECTO!]')

    print('\n' + '='*80)
    print('[OK] Correccion completada exitosamente')
    print('='*80)

except Exception as e:
    print(f'\n[ERROR] {e}', file=sys.stderr)
    sys.exit(1)
