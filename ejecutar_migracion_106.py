#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MIGRACION 106: Fix vista v_pedido_estado_resumen (bug migración 095)

PROBLEMA: FIs confirmadas no aparecen en Aprobaciones porque vista usa
columna equivocada (fi.id_pedido_venta_rimec en lugar de fi.pedido_id)

INVESTIGACION: diagnostico_fi_huerfanas_vista.py confirmó que TODAS las
69 FIs confirmadas SÍ tienen pedido_id correcto. El problema es la vista.
"""
from core.database import engine
from sqlalchemy import text
import sys

print('=' * 80)
print('MIGRACION 106: Fix vista v_pedido_estado_resumen')
print('=' * 80)

try:
    with engine.begin() as conn:
        # Verificar si vista existe
        print('\n[VERIFICANDO VISTA]')
        print('-' * 80)
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views
                WHERE table_schema = 'public'
                  AND table_name = 'v_pedido_estado_resumen'
            )
        """))
        vista_existe = result.scalar()
        print(f'  Vista existe: {vista_existe}')

        if vista_existe:
            print('\n[ANTES - Vista rota]')
            print('-' * 80)
            result = conn.execute(text("""
                SELECT
                    pedido_estado,
                    COUNT(*) as pedidos,
                    SUM(total_facturas) as total_fis,
                    SUM(fis_confirmadas) as total_confirmadas
                FROM v_pedido_estado_resumen
                GROUP BY pedido_estado
                ORDER BY pedido_estado
            """))
            for row in result:
                estado = row[0] or 'NULL'
                print(f'  {estado:15} : {row[1]:3} pedidos, {row[2]:3} FIs, {row[3]:3} confirmadas')

        # Ejecutar migración
        print('\n[EJECUTANDO MIGRACION 106]')
        print('-' * 80)
        with open('migrations/106_fix_vista_pedido_estado.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()

        conn.execute(text(sql_content))
        print('  Vista recreada con JOIN correcto (fi.pedido_id = pvr.id)')

        # Estado DESPUES
        print('\n[DESPUES - Vista corregida]')
        print('-' * 80)
        result = conn.execute(text("""
            SELECT
                pedido_estado,
                COUNT(*) as pedidos,
                SUM(total_facturas) as total_fis,
                SUM(fis_confirmadas) as total_confirmadas
            FROM v_pedido_estado_resumen
            GROUP BY pedido_estado
            ORDER BY pedido_estado
        """))
        for row in result:
            estado = row[0] or 'NULL'
            print(f'  {estado:15} : {row[1]:3} pedidos, {row[2]:3} FIs, {row[3]:3} confirmadas')

        # Verificar casos específicos
        print('\n[VERIFICACION - Pedidos con facturas]')
        print('-' * 80)
        result = conn.execute(text("""
            SELECT
                nro_pedido,
                pedido_estado,
                total_facturas,
                fis_confirmadas,
                fis_reservadas
            FROM v_pedido_estado_resumen
            WHERE total_facturas > 0
            ORDER BY created_at DESC
            LIMIT 10
        """))

        if result.rowcount > 0:
            for row in result:
                print(f'  {row[0]:20} | Estado: {row[1]:12} | FIs: {row[2]:2} (CONF: {row[3]:2}, RES: {row[4]:2})')
        else:
            print('  (sin pedidos con facturas)')

        print('\n' + '=' * 80)
        print('[OK] MIGRACION 106 COMPLETADA')
        print('=' * 80)
        print('\nAhora las FIs confirmadas deberían aparecer en Aprobaciones.')

except Exception as e:
    print(f'\n[ERROR] {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
