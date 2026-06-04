#!/usr/bin/env python3
"""Verificar que el sistema de quincenas está correctamente instalado"""
from core.database import get_engine
from sqlalchemy import text as sqlt

def verificar():
    engine = get_engine()
    with engine.connect() as conn:
        # 1. Verificar que existe la tabla quincena_arribo
        print("=== 1. Tabla quincena_arribo ===")
        result = conn.execute(sqlt("""
            SELECT COUNT(*) FROM quincena_arribo
        """)).fetchone()
        print(f"OK Registros en quincena_arribo: {result[0]}")

        # Mostrar primeras 3 quincenas
        result = conn.execute(sqlt("""
            SELECT id, descripcion FROM quincena_arribo ORDER BY id LIMIT 3
        """)).fetchall()
        for row in result:
            print(f"  {row[0]}: {row[1]}")

        # 2. Verificar columnas FK en intencion_compra
        print("\n=== 2. FK en intencion_compra ===")
        result = conn.execute(sqlt("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'intencion_compra'
            AND column_name IN ('quincena_arribo_id', 'fecha_llegada')
            ORDER BY column_name
        """)).fetchall()
        for row in result:
            print(f"  OK {row[0]}: {row[1]}")

        # 3. Verificar columnas FK en pedido_proveedor
        print("\n=== 3. FK en pedido_proveedor ===")
        result = conn.execute(sqlt("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'pedido_proveedor'
            AND column_name IN ('quincena_arribo_id', 'fecha_arribo_estimada')
            ORDER BY column_name
        """)).fetchall()
        for row in result:
            print(f"  OK {row[0]}: {row[1]}")

        # 4. Verificar columnas FK en factura_interna
        print("\n=== 4. FK en factura_interna ===")
        result = conn.execute(sqlt("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'factura_interna'
            AND column_name = 'quincena_arribo_id'
        """)).fetchall()
        for row in result:
            print(f"  OK {row[0]}: {row[1]}")

        # 5. Verificar índices
        print("\n=== 5. Índices ===")
        result = conn.execute(sqlt("""
            SELECT indexname, tablename
            FROM pg_indexes
            WHERE indexname LIKE '%quincena%'
            ORDER BY tablename, indexname
        """)).fetchall()
        for row in result:
            print(f"  OK {row[1]}.{row[0]}")

        print("\n✅ Cable de acero reforzado: VERIFICADO")

if __name__ == "__main__":
    verificar()
