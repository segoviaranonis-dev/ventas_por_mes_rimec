#!/usr/bin/env python3
"""
Probar sincronización con columnas específicas (sin sku_key)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    engine = get_engine()

    print("=" * 70)
    print(" PRUEBA DE SINCRONIZACION (SIN sku_key)")
    print("=" * 70)

    with engine.begin() as conn:
        # 1. Borrar registros existentes
        print("\n1. Borrando registros existentes...")
        delete_result = conn.execute(text("DELETE FROM deposito_tienda_fernando_adultos"))
        print(f"   Borrados: {delete_result.rowcount}")

        # 2. Insertar SIN sku_key
        print("\n2. Insertando registros (sin sku_key)...")
        insert_result = conn.execute(text("""
            INSERT INTO deposito_tienda_fernando_adultos (
              id, batch_id, batch_label, fecha_mov, origen_holding, tipo_movimiento,
              codigo_barras, linea_codigo_proveedor, referencia_codigo_proveedor,
              excel_material_code, excel_color_code, linea_id, referencia_id,
              material_id, color_id, grada, cantidad, precio_unitario, monto,
              imagen_nombre, archivo_origen, excel_sheet, created_at, created_by,
              marca_id, genero_id, grupo_estilo_id, tipo_1_id, tipo_v2_id, cliente_id
            )
            SELECT
              r.id, r.batch_id, r.batch_label, r.fecha_mov, r.origen_holding, r.tipo_movimiento,
              r.codigo_barras, r.linea_codigo_proveedor, r.referencia_codigo_proveedor,
              r.excel_material_code, r.excel_color_code, r.linea_id, r.referencia_id,
              r.material_id, r.color_id, r.grada, r.cantidad, r.precio_unitario, r.monto,
              r.imagen_nombre, r.archivo_origen, r.excel_sheet, r.created_at, r.created_by,
              r.marca_id, r.genero_id, r.grupo_estilo_id, r.tipo_1_id, r.tipo_v2_id, r.cliente_id
            FROM registro_st_vt_rc_reposicion r
            INNER JOIN tiendas_marcas tm ON
              tm.cliente_id = 2100 AND
              tm.marca_id = r.marca_id AND
              tm.activo = true
            WHERE r.cliente_id = 2100
              AND lower(btrim(r.tipo_movimiento)) = 'stock'
        """))
        registros_insertados = insert_result.rowcount
        print(f"   Insertados: {registros_insertados:,}")

        # 3. Verificar que sku_key se generó automáticamente
        print("\n3. Verificando columna generada sku_key...")
        verify_result = conn.execute(text("""
            SELECT sku_key, COUNT(*) as total
            FROM deposito_tienda_fernando_adultos
            WHERE sku_key IS NOT NULL
            GROUP BY sku_key
            LIMIT 5
        """))

        print("   Primeros 5 sku_key generados:")
        for row in verify_result:
            sku_key = row[0]
            count = row[1]
            print(f"     {sku_key}: {count} registro(s)")

    print("\n" + "=" * 70)
    print(f" SINCRONIZACION EXITOSA: {registros_insertados:,} registros")
    print("=" * 70)

if __name__ == "__main__":
    main()
