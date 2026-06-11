#!/usr/bin/env python3
"""
Probar query de TOP 30 productos
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text
import time

def main():
    engine = get_engine()
    tabla = "deposito_tienda_fernando_adultos"

    print("=" * 70)
    print(" PROBANDO QUERY TOP 30 PRODUCTOS CON MAS STOCK")
    print("=" * 70)

    with engine.connect() as conn:
        start = time.time()
        result = conn.execute(text(f"""
            WITH ranked_products AS (
                SELECT
                    s.linea_codigo_proveedor,
                    s.referencia_codigo_proveedor,
                    s.cantidad::float8 AS cantidad,
                    mv.descp_marca AS marca,
                    ROW_NUMBER() OVER (ORDER BY s.cantidad DESC) AS rank_global
                FROM {tabla} s
                LEFT JOIN marca_v2 mv ON mv.id_marca = s.marca_id
            )
            SELECT
                linea_codigo_proveedor,
                referencia_codigo_proveedor,
                marca,
                cantidad
            FROM ranked_products
            WHERE rank_global <= 30
            ORDER BY cantidad DESC
        """))
        rows = list(result)
        elapsed = time.time() - start

        print(f"\nTiempo: {elapsed:.3f} segundos")
        print(f"Registros: {len(rows)}")
        print("\nTOP 30 PRODUCTOS:")
        print("-" * 70)
        print(f"{'LINEA':<8} {'REF':<8} {'MARCA':<20} {'PARES':>8}")
        print("-" * 70)

        for i, row in enumerate(rows, 1):
            print(f"{row[0]:<8} {row[1]:<8} {row[2]:<20} {row[3]:>8.0f}")

        # Contar productos por marca
        print("\n" + "=" * 70)
        print("DISTRIBUCION POR MARCA:")
        print("-" * 70)
        marcas = {}
        for row in rows:
            marca = row[2] or "(sin marca)"
            if marca not in marcas:
                marcas[marca] = {"count": 0, "total_pares": 0}
            marcas[marca]["count"] += 1
            marcas[marca]["total_pares"] += row[3]

        for marca, stats in sorted(marcas.items(), key=lambda x: x[1]["total_pares"], reverse=True):
            print(f"{marca:<20} {stats['count']:>3} productos  {stats['total_pares']:>8.0f} pares")

        print("=" * 70)

if __name__ == "__main__":
    main()
