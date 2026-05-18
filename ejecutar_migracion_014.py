#!/usr/bin/env python
"""OT-2026-049: Ejecutar migración 014 - Poblar genero por marca (CORRECCION)"""
from sqlalchemy import create_engine, text
import sys

db_url = 'postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres'
engine = create_engine(db_url)

print('='*80)
print('OT-2026-049: POBLANDO GENERO POR MARCA (CORRECCION)')
print('='*80)

try:
    with engine.begin() as conn:
        # Estado ANTES
        print('\n[ANTES]')
        print('-'*80)
        result = conn.execute(text("""
            SELECT COALESCE(g.codigo::text, '(sin genero_id)') AS genero_cod, COUNT(*) as total
            FROM linea l
            LEFT JOIN genero g ON g.id = l.genero_id
            GROUP BY g.codigo
            ORDER BY genero_cod NULLS LAST
        """))
        for row in result:
            g = row[0] if row[0] else 'NULL'
            print(f'  {g:15} : {row[1]:4} lineas')

        # Leer y ejecutar SQL
        with open('migrations/014_poblar_genero_por_marca.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Ejecutar por partes para obtener rowcount de cada UPDATE
        updates = sql_content.split(';')
        print('\n[EJECUTANDO UPDATES]')
        print('-'*80)
        total_updated = 0
        for i, update in enumerate(updates, 1):
            update = update.strip()
            if update and 'UPDATE' in update.upper():
                # Extraer el género del comentario
                if 'DAMAS' in update:
                    label = 'DAMAS'
                elif 'NIÑAS' in update or 'MOLEKINHA' in update:
                    label = 'NIÑAS'
                elif 'NIÑOS' in update or 'MOLEKINHO' in update:
                    label = 'NIÑOS'
                elif 'CABALLEROS' in update:
                    label = 'CABALLEROS'
                else:
                    label = f'UPDATE {i}'

                result = conn.execute(text(update))
                rows_updated = result.rowcount
                total_updated += rows_updated
                print(f'  {label:15} : {rows_updated:4} lineas actualizadas')

        print(f'\n  Total actualizado: {total_updated} lineas')

        # Estado DESPUES
        print('\n[DESPUES]')
        print('-'*80)
        result = conn.execute(text("""
            SELECT COALESCE(g.codigo::text, '(sin genero_id)') AS genero_cod, COUNT(*) as total
            FROM linea l
            LEFT JOIN genero g ON g.id = l.genero_id
            GROUP BY g.codigo
            ORDER BY genero_cod NULLS LAST
        """))
        for row in result:
            g = row[0] if row[0] else 'NULL'
            print(f'  {g:15} : {row[1]:4} lineas')

        # Verificar en v_stock_web con stock
        print('\n[VERIFICACION EN v_stock_web CON STOCK]')
        print('-'*80)
        result = conn.execute(text("""
            SELECT COALESCE(g.codigo::text, '(sin genero_id)') AS genero_cod,
                   COUNT(DISTINCT v.linea_id) as lineas_con_stock
            FROM v_stock_web v
            INNER JOIN linea l ON l.id = v.linea_id
            LEFT JOIN genero g ON g.id = l.genero_id
            WHERE v.stock_web > 0
            GROUP BY g.codigo
            ORDER BY genero_cod NULLS LAST
        """))
        for row in result:
            g = row[0] if row[0] else 'NULL'
            print(f'  {g:15} : {row[1]:4} lineas con stock')

        # Desglose por marca
        print('\n[DESGLOSE POR MARCA]')
        print('-'*80)
        result = conn.execute(text("""
            SELECT v.marca, COALESCE(g.codigo::text, '(sin genero_id)') AS genero_cod,
                   COUNT(DISTINCT v.linea_id) as lineas
            FROM v_stock_web v
            INNER JOIN linea l ON l.id = v.linea_id
            LEFT JOIN genero g ON g.id = l.genero_id
            WHERE v.stock_web > 0
            GROUP BY v.marca, g.codigo
            ORDER BY v.marca, genero_cod
        """))
        for row in result:
            marca = row[0] if row[0] else 'NULL'
            genero = row[1] if row[1] else 'NULL'
            print(f'  {marca:15} | {str(genero):15} : {row[2]:3} lineas')

        print('\n' + '='*80)
        print('[OK] MIGRACION 014 COMPLETADA')
        print('='*80)

except Exception as e:
    print(f'\n[ERROR] {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
