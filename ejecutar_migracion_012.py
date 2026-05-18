#!/usr/bin/env python
"""OT-2026-047: Ejecutar migración 012_snapshot_costos.sql"""
from sqlalchemy import create_engine, text
import sys

db_url = 'postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres'
engine = create_engine(db_url)

print('='*80)
print('OT-2026-047: CREANDO TABLA snapshot_costos')
print('='*80)

try:
    with engine.begin() as conn:
        # Leer SQL
        with open('migrations/012_snapshot_costos.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Ejecutar
        conn.execute(text(sql_content))
        print('[OK] Tabla snapshot_costos creada exitosamente')

        # Verificar estructura
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'snapshot_costos'
            ORDER BY ordinal_position
        """))

        print('\n[ESTRUCTURA DE LA TABLA]')
        print('-'*80)
        for row in result:
            nullable = 'NULL' if row[2] == 'YES' else 'NOT NULL'
            default = f' DEFAULT {row[3]}' if row[3] else ''
            print(f'  {row[0]:20} {row[1]:15} {nullable:10}{default}')

        # Verificar indices
        result2 = conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'snapshot_costos'
        """))

        print('\n[INDICES CREADOS]')
        print('-'*80)
        for row in result2:
            print(f'  {row[0]}')

        print('\n' + '='*80)
        print('[OK] MIGRACION 012 COMPLETADA')
        print('='*80)

except Exception as e:
    print(f'\n[ERROR] {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
