#!/usr/bin/env python
"""Encontrar todos los colores con codigo_proveedor sospechoso"""
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
print('BUSQUEDA DE COLORES CON CODIGO_PROVEEDOR SOSPECHOSO')
print('='*80)

# Buscar colores con codigo_proveedor > 1000000 (sospechosamente grandes)
query = """
SELECT
    id,
    nombre,
    codigo_proveedor,
    proveedor_id,
    created_at,
    (
        SELECT COUNT(DISTINCT CONCAT(l.codigo_proveedor, '-', r.codigo_proveedor))
        FROM combinacion c
        JOIN linea l ON l.id = c.linea_id
        JOIN referencia r ON r.id = c.referencia_id
        WHERE c.color_id = color.id
          AND c.activo_web = true
    ) as productos_afectados
FROM color
WHERE codigo_proveedor > 1000000
ORDER BY codigo_proveedor DESC
"""

try:
    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = result.fetchall()

        if not rows:
            print('\n[OK] No se encontraron colores con codigo_proveedor sospechoso')
            sys.exit(0)

        print(f'\n[!] {len(rows)} colores encontrados con codigo_proveedor > 1000000:\n')
        print(f'{"ID":>5} | {"Nombre":20} | {"Codigo Prov":>12} | {"Proveedor":>4} | {"Productos":>10}')
        print('-'*80)

        for row in rows:
            print(f'{row[0]:5} | {row[1]:20} | {row[2]:12} | {row[3]:4} | {row[5]:10}')

        print('\n' + '='*80)
        print(f'TOTAL: {len(rows)} colores con codigo_proveedor incorrecto')
        print('='*80)

except Exception as e:
    print(f'\n[ERROR] {e}', file=sys.stderr)
    sys.exit(1)
