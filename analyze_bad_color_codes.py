#!/usr/bin/env python
"""Analizar patrón de códigos incorrectos y encontrar productos afectados"""
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
print('ANALISIS DE CODIGOS INCORRECTOS - PATRON Y PRODUCTOS AFECTADOS')
print('='*80)

queries = {
    "1. Todos los colores con codigo > 100000": """
        SELECT
            id,
            nombre,
            codigo_proveedor,
            proveedor_id,
            (
                SELECT COUNT(*)
                FROM combinacion c
                WHERE c.color_id = color.id
            ) as total_combinaciones,
            (
                SELECT COUNT(DISTINCT CONCAT(l.codigo_proveedor, '-', r.codigo_proveedor))
                FROM combinacion c
                JOIN linea l ON l.id = c.linea_id
                JOIN referencia r ON r.id = c.referencia_id
                WHERE c.color_id = color.id
            ) as productos_unicos
        FROM color
        WHERE codigo_proveedor > 100000
        ORDER BY codigo_proveedor DESC
    """,

    "2. Productos que usan color 924113200 (BLANCO 99/MARINO 488)": """
        SELECT DISTINCT
            l.codigo_proveedor as linea,
            r.codigo_proveedor as ref,
            mat.codigo_proveedor as material,
            col.codigo_proveedor as color,
            col.nombre as color_nombre,
            c.activo_web
        FROM combinacion c
        JOIN linea l ON l.id = c.linea_id
        JOIN referencia r ON r.id = c.referencia_id
        JOIN material mat ON mat.id = c.material_id
        JOIN color col ON col.id = c.color_id
        WHERE col.codigo_proveedor = 924113200
        LIMIT 5
    """,

    "3. Productos que usan color 599041400 (ROSA 942)": """
        SELECT DISTINCT
            l.codigo_proveedor as linea,
            r.codigo_proveedor as ref,
            mat.codigo_proveedor as material,
            col.codigo_proveedor as color,
            col.nombre as color_nombre,
            c.activo_web
        FROM combinacion c
        JOIN linea l ON l.id = c.linea_id
        JOIN referencia r ON r.id = c.referencia_id
        JOIN material mat ON mat.id = c.material_id
        JOIN color col ON col.id = c.color_id
        WHERE col.codigo_proveedor = 599041400
        LIMIT 5
    """,

    "4. Analisis de patron - ultimos colores creados": """
        SELECT
            id,
            nombre,
            codigo_proveedor,
            LENGTH(codigo_proveedor::text) as digitos,
            created_at
        FROM color
        WHERE created_at > NOW() - INTERVAL '7 days'
        ORDER BY created_at DESC
        LIMIT 10
    """,

    "5. Comparar con pedido_proveedor_detalle (id_color)": """
        SELECT DISTINCT
            ppd.id_color as codigo_f9,
            col.id as color_id_bd,
            col.nombre,
            col.codigo_proveedor as codigo_bd,
            ppd.descp_color
        FROM pedido_proveedor_detalle ppd
        LEFT JOIN color col ON ppd.descp_color = col.nombre
        WHERE ppd.id_color IN (924113200, 599041400, 89673, 15745)
        ORDER BY ppd.id_color
        LIMIT 10
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
                print('  [Sin resultados]')
                continue

            # Header
            print('  ' + ' | '.join(str(c) for c in cols))
            print('  ' + '-'*70)

            # Rows
            for row in rows:
                print('  ' + ' | '.join(str(v) if v is not None else 'NULL' for v in row))

except Exception as e:
    print(f'\n[ERROR] {e}', file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n' + '='*80)
