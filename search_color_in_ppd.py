#!/usr/bin/env python
"""Buscar colores en pedido_proveedor_detalle"""
from sqlalchemy import create_engine, text
import sys

host = 'aws-1-sa-east-1.pooler.supabase.com'
port = 6543
dbname = 'postgres'
user = 'postgres.extrlcvcgypwazxipvqm'
password = 'IJoFJbT8Qj0Q0w5m'

conn_str = f'postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=require'
engine = create_engine(conn_str, pool_pre_ping=True)

print('Buscando "ROSA 942" y "BLANCO 99/MARINO 488" en PPD...\n')

queries = [
    ("ROSA 942 - Exacto", "SELECT DISTINCT descp_color, color_code, id_color FROM pedido_proveedor_detalle WHERE descp_color = 'ROSA 942'"),
    ("ROSA 942 - LIKE", "SELECT DISTINCT descp_color, color_code, id_color FROM pedido_proveedor_detalle WHERE descp_color LIKE '%ROSA%942%' LIMIT 5"),
    ("BLANCO MARINO - Exacto", "SELECT DISTINCT descp_color, color_code, id_color FROM pedido_proveedor_detalle WHERE descp_color = 'BLANCO 99/MARINO 488'"),
    ("BLANCO MARINO - LIKE", "SELECT DISTINCT descp_color, color_code, id_color FROM pedido_proveedor_detalle WHERE descp_color LIKE '%BLANCO%MARINO%' LIMIT 5"),
    ("Todos los colores en PPD del producto 2126-529", """
        SELECT DISTINCT descp_color, color_code, id_color
        FROM pedido_proveedor_detalle
        WHERE linea = '2126' AND referencia = '529'
    """),
    ("Todos los colores en PPD del producto 2133-182", """
        SELECT DISTINCT descp_color, color_code, id_color
        FROM pedido_proveedor_detalle
        WHERE linea = '2133' AND referencia = '182'
    """),
]

try:
    with engine.connect() as conn:
        for title, query in queries:
            print(f'[{title}]')
            print('-'*70)
            result = conn.execute(text(query))
            rows = result.fetchall()
            if rows:
                for row in rows:
                    print(f'  {row[0]:40} | color_code: {row[1] if row[1] else "NULL":12} | id_color: {row[2] if row[2] else "NULL"}')
            else:
                print('  [Sin resultados]')
            print()

except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
