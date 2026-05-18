#!/usr/bin/env python
"""Verificar marcas con stock"""
from sqlalchemy import create_engine, text

db_url = 'postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres'
engine = create_engine(db_url)

with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT DISTINCT marca, COUNT(DISTINCT linea_codigo) as lineas_con_stock
        FROM v_stock_web
        WHERE stock_web > 0
        GROUP BY marca
        ORDER BY marca
    '''))
    print('Marcas con stock en v_stock_web:')
    print('-'*60)
    for row in result:
        print(f'{row[0]:20} | {row[1]:3} lineas con stock')
