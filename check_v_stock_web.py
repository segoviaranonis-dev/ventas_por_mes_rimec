#!/usr/bin/env python
"""Script para verificar definición actual de v_stock_web"""
from sqlalchemy import create_engine, text
import sys

host = 'aws-1-sa-east-1.pooler.supabase.com'
port = 6543
dbname = 'postgres'
user = 'postgres.extrlcvcgypwazxipvqm'
password = 'IJoFJbT8Qj0Q0w5m'

conn_str = f'postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=require'
engine = create_engine(conn_str, pool_pre_ping=True)

print('🔍 Consultando definición actual de v_stock_web...', file=sys.stderr)

query = """
SELECT pg_get_viewdef('v_stock_web', true) as definition
"""

try:
    with engine.connect() as conn:
        result = conn.execute(text(query))
        definition = result.fetchone()[0]
        print('\n' + '='*80)
        print('DEFINICIÓN ACTUAL v_stock_web:')
        print('='*80)
        print(definition)
        print('='*80 + '\n')
except Exception as e:
    print(f'❌ Error: {e}', file=sys.stderr)
    sys.exit(1)
