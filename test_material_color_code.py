#!/usr/bin/env python
"""Verificar que material_code y color_code tienen valores para producto 8246-1176"""
from sqlalchemy import create_engine, text
import sys

host = 'aws-1-sa-east-1.pooler.supabase.com'
port = 6543
dbname = 'postgres'
user = 'postgres.extrlcvcgypwazxipvqm'
password = 'IJoFJbT8Qj0Q0w5m'

conn_str = f'postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=require'
engine = create_engine(conn_str, pool_pre_ping=True)

print('🔍 Consultando producto 8246-1176...', file=sys.stderr)

query = """
SELECT
    linea_codigo,
    referencia_codigo,
    material_id,
    material_code,
    color_id,
    color_code,
    color_nombre,
    COUNT(*) as tallas_count
FROM v_stock_web
WHERE linea_codigo = '8246' AND referencia_codigo = '1176'
GROUP BY linea_codigo, referencia_codigo, material_id, material_code, color_id, color_code, color_nombre
LIMIT 5
"""

try:
    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = result.fetchall()

        if not rows:
            print('❌ No se encontraron datos para 8246-1176', file=sys.stderr)
            sys.exit(1)

        print('\n' + '='*80)
        print('DATOS PRODUCTO 8246-1176:')
        print('='*80)
        for row in rows:
            print(f'\nLinea: {row[0]}')
            print(f'  Referencia: {row[1]}')
            print(f'  Material ID: {row[2]}')
            print(f'  Material Code: {row[3]} {"OK" if row[3] else "NULL"}')
            print(f'  Color ID: {row[4]}')
            print(f'  Color Code: {row[5]} {"OK" if row[5] else "NULL"}')
            print(f'  Color Nombre: {row[6]}')
            print(f'  Tallas: {row[7]}')

            if row[3] and row[5]:
                url = f'{row[0]}-{row[1]}-{row[3]}-{row[5]}.jpg'
                print(f'\n  URL: {url}')
                if url == '8246-1176-9569-89673.jpg':
                    print('  [OK] URL CORRECTA!')
                else:
                    print(f'  [!] Esperada: 8246-1176-9569-89673.jpg')

        print('\n' + '='*80)
        print('[OK] Columnas material_code y color_code disponibles')
        print('='*80 + '\n')

except Exception as e:
    print(f'❌ Error: {e}', file=sys.stderr)
    sys.exit(1)
