#!/usr/bin/env python
"""Diagnóstico profundo del color_code para producto 8246-1176"""
from sqlalchemy import create_engine, text
import sys

host = 'aws-1-sa-east-1.pooler.supabase.com'
port = 6543
dbname = 'postgres'
user = 'postgres.extrlcvcgypwazxipvqm'
password = 'IJoFJbT8Qj0Q0w5m'

conn_str = f'postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=require'
engine = create_engine(conn_str, pool_pre_ping=True)

print('[*] DIAGNOSTICO PRODUCTO 8246-1176 - Color Code Incorrecto')
print('='*80)

queries = {
    "1. Datos en v_stock_web": """
        SELECT DISTINCT
            linea_codigo,
            referencia_codigo,
            material_id,
            material_code,
            color_id,
            color_code,
            color_nombre
        FROM v_stock_web
        WHERE linea_codigo = '8246' AND referencia_codigo = '1176'
        ORDER BY color_id
    """,

    "2. Datos directos tabla color (por ID)": """
        SELECT id, nombre, codigo_proveedor, hex_web, proveedor_id
        FROM color
        WHERE id IN (
            SELECT DISTINCT color_id
            FROM combinacion c
            JOIN linea l ON l.id = c.linea_id
            JOIN referencia r ON r.id = c.referencia_id
            WHERE l.codigo_proveedor = 8246 AND r.codigo_proveedor = 1176
        )
        ORDER BY id
    """,

    "3. Combinaciones del producto": """
        SELECT
            c.id as combinacion_id,
            c.color_id,
            col.nombre as color_nombre,
            col.codigo_proveedor as color_codigo_proveedor,
            c.material_id,
            mat.codigo_proveedor as material_codigo_proveedor
        FROM combinacion c
        JOIN linea l ON l.id = c.linea_id
        JOIN referencia r ON r.id = c.referencia_id
        LEFT JOIN color col ON col.id = c.color_id
        LEFT JOIN material mat ON mat.id = c.material_id
        WHERE l.codigo_proveedor = 8246
          AND r.codigo_proveedor = 1176
        ORDER BY c.color_id
        LIMIT 10
    """,

    "4. Verificar color ID 124 específicamente": """
        SELECT
            id,
            nombre,
            codigo_proveedor,
            hex_web,
            proveedor_id,
            created_at
        FROM color
        WHERE id = 124
    """
}

try:
    with engine.connect() as conn:
        for title, query in queries.items():
            print(f'\n{title}')
            print('-'*80)
            result = conn.execute(text(query))
            rows = result.fetchall()
            cols = result.keys()

            if not rows:
                print('  [!] Sin resultados')
                continue

            # Header
            print('  ' + ' | '.join(str(c) for c in cols))
            print('  ' + '-'*70)

            # Rows
            for row in rows:
                print('  ' + ' | '.join(str(v) if v is not None else 'NULL' for v in row))

except Exception as e:
    print(f'\n[ERROR] {e}', file=sys.stderr)
    sys.exit(1)

print('\n' + '='*80)
