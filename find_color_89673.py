#!/usr/bin/env python
"""Buscar color_code 89673 en la BD"""
from sqlalchemy import create_engine, text
import sys

host = 'aws-1-sa-east-1.pooler.supabase.com'
port = 6543
dbname = 'postgres'
user = 'postgres.extrlcvcgypwazxipvqm'
password = 'IJoFJbT8Qj0Q0w5m'

conn_str = f'postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=require'
engine = create_engine(conn_str, pool_pre_ping=True)

print('[*] Buscando color_code 89673...', file=sys.stderr)

# Buscar en v_stock_web
query1 = """
SELECT linea_codigo, referencia_codigo, material_code, color_code, color_nombre
FROM v_stock_web
WHERE color_code = '89673'
LIMIT 5
"""

# Buscar en tabla color directamente
query2 = """
SELECT id, nombre, codigo_proveedor, hex_web
FROM color
WHERE codigo_proveedor = 89673
"""

try:
    with engine.connect() as conn:
        print('\n[1] Busqueda en v_stock_web:', file=sys.stderr)
        result = conn.execute(text(query1))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f'  {row[0]}-{row[1]}-{row[2]}-{row[3]} | {row[4]}')
        else:
            print('  [!] No encontrado en v_stock_web')

        print('\n[2] Busqueda en tabla color:', file=sys.stderr)
        result = conn.execute(text(query2))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f'  ID: {row[0]} | Nombre: {row[1]} | Codigo: {row[2]} | Hex: {row[3]}')
        else:
            print('  [!] No existe codigo_proveedor 89673 en tabla color')

        print('\n[3] Colores para producto 8246-1176:', file=sys.stderr)
        query3 = """
        SELECT DISTINCT color_id, color_code, color_nombre
        FROM v_stock_web
        WHERE linea_codigo = '8246' AND referencia_codigo = '1176'
        """
        result = conn.execute(text(query3))
        rows = result.fetchall()
        for row in rows:
            print(f'  Color ID: {row[0]} | Codigo: {row[1]} | Nombre: {row[2]}')

except Exception as e:
    print(f'[ERROR] {e}', file=sys.stderr)
    sys.exit(1)
