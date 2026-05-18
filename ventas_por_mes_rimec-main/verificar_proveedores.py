#!/usr/bin/env python
"""Verificar nombres de proveedores"""
from sqlalchemy import create_engine, text

db_url = 'postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres'
engine = create_engine(db_url)

with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT p.id, p.nombre, COUNT(l.id) as lineas
        FROM proveedor_importacion p
        LEFT JOIN linea l ON l.proveedor_id = p.id
        GROUP BY p.id, p.nombre
        ORDER BY lineas DESC
    '''))
    print('Proveedores y sus lineas:')
    print('-'*80)
    for row in result:
        print(f'{row[0]:4} | {row[1]:30} | {row[2]:4} lineas')
