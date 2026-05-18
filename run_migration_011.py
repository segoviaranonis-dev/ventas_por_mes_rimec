#!/usr/bin/env python
"""
Script para ejecutar migración 011
Autorizado por Director - OT-2026-040
"""
from sqlalchemy import create_engine, text
import sys

# Credenciales Supabase
host = 'aws-1-sa-east-1.pooler.supabase.com'
port = 6543
dbname = 'postgres'
user = 'postgres.extrlcvcgypwazxipvqm'
password = 'IJoFJbT8Qj0Q0w5m'

conn_str = f'postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=require'

print('🔌 Conectando a Supabase...', file=sys.stderr)
engine = create_engine(conn_str, pool_pre_ping=True)

print('📖 Leyendo migración 011...', file=sys.stderr)
with open('migrations/011_fix_v_stock_web_codigo_proveedor.sql', 'r', encoding='utf-8') as f:
    sql = f.read()

print('⚡ Ejecutando migración...', file=sys.stderr)
print(f'   Longitud SQL: {len(sql)} caracteres', file=sys.stderr)

try:
    with engine.begin() as conn:
        conn.execute(text(sql))
    print('\n' + '='*60, file=sys.stderr)
    print('✅ MIGRACIÓN 011 EJECUTADA EXITOSAMENTE', file=sys.stderr)
    print('='*60, file=sys.stderr)
    print('\n📋 Cambios aplicados:', file=sys.stderr)
    print('   • v_stock_web DROP y CREATE exitoso', file=sys.stderr)
    print('   • Agregadas columnas:', file=sys.stderr)
    print('     - material_code (mat.codigo_proveedor)', file=sys.stderr)
    print('     - color_code (col.codigo_proveedor)', file=sys.stderr)
    print('\n🎯 Impacto:', file=sys.stderr)
    print('   • bazzar-web ahora puede construir URLs correctas', file=sys.stderr)
    print('   • Formato: {linea}-{ref}-{material_code}-{color_code}.jpg', file=sys.stderr)
    print('   • Ejemplo: 8246-1176-9569-89673.jpg ✓', file=sys.stderr)
    print('\n', file=sys.stderr)
except Exception as e:
    print(f'\n❌ ERROR EN MIGRACIÓN: {e}', file=sys.stderr)
    print(f'   Tipo: {type(e).__name__}', file=sys.stderr)
    sys.exit(1)
