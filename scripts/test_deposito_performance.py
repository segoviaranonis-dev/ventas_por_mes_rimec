#!/usr/bin/env python3
"""
Probar performance del query de depósito
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    engine = get_engine()
    tabla = "deposito_tienda_fernando_adultos"

    print("=" * 70)
    print(" PROBANDO PERFORMANCE DEL QUERY DE DEPÓSITO")
    print("=" * 70)

    with engine.connect() as conn:
        # Test 1: Query con JOINs (como en el API)
        print("\n1. Query con 6 LEFT JOINs...")
        start = time.time()
        result = conn.execute(text(f"""
            SELECT COUNT(*) FROM {tabla} s
            LEFT JOIN material mat ON mat.id = s.material_id
            LEFT JOIN color col ON col.id = s.color_id
            LEFT JOIN marca_v2 mv ON mv.id_marca = s.marca_id
            LEFT JOIN genero g ON g.id = s.genero_id
            LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = s.grupo_estilo_id
            LEFT JOIN tipo_v2 tv ON tv.id_tipo = s.tipo_v2_id
        """))
        count = result.fetchone()[0]
        elapsed = time.time() - start
        print(f"   Registros: {count:,}")
        print(f"   Tiempo: {elapsed:.2f} segundos")

        # Test 2: Verificar índices
        print("\n2. Índices en la tabla...")
        result = conn.execute(text(f"""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = '{tabla}'
            ORDER BY indexname
        """))
        indices = list(result)
        if indices:
            for idx in indices:
                print(f"   [OK] {idx[0]}")
        else:
            print("   [ERROR] NO HAY INDICES (problema grave)")

        # Test 3: Query completo (como en el API)
        print("\n3. Query completo con SELECT *...")
        start = time.time()
        result = conn.execute(text(f"""
            SELECT
                s.linea_codigo_proveedor,
                s.referencia_codigo_proveedor,
                s.material_id,
                s.color_id,
                s.cantidad,
                mv.descp_marca AS marca,
                g.descripcion AS genero
            FROM {tabla} s
            LEFT JOIN marca_v2 mv ON mv.id_marca = s.marca_id
            LEFT JOIN genero g ON g.id = s.genero_id
            ORDER BY s.linea_codigo_proveedor
        """))
        rows = list(result)
        elapsed = time.time() - start
        print(f"   Registros: {len(rows):,}")
        print(f"   Tiempo: {elapsed:.2f} segundos")

    print("\n" + "=" * 70)
    print(" DIAGNÓSTICO:")
    print("=" * 70)
    if elapsed > 2.0:
        print("  [WARNING]  LENTO (>2s) - Necesita optimización urgente")
        print("  Soluciones:")
        print("    1. Agregar índices en FK (material_id, color_id, marca_id, etc.)")
        print("    2. Implementar caché (Redis/Memory)")
        print("    3. Paginación (LIMIT/OFFSET)")
    elif elapsed > 0.5:
        print("  [WARNING]  ACEPTABLE (0.5-2s) - Se puede mejorar")
    else:
        print("  [OK] RÁPIDO (<0.5s)")
    print("=" * 70)

if __name__ == "__main__":
    main()
