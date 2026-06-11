#!/usr/bin/env python3
"""
Probar query de análisis para depósito
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    engine = get_engine()
    tabla = "deposito_tienda_fernando_adultos"

    print("=" * 70)
    print(f" PROBANDO QUERY DE ANALISIS PARA: {tabla}")
    print("=" * 70)

    with engine.connect() as conn:
        # Verificar datos
        print("\n1. Verificando datos...")
        result = conn.execute(text(f"SELECT COUNT(*) FROM {tabla}"))
        total = result.fetchone()[0]
        print(f"   Total registros: {total:,}")

        # Probar query de resumen
        print("\n2. Query de resumen...")
        try:
            result = conn.execute(text(f"""
                SELECT
                    SUM(cantidad) AS total_inicial,
                    COUNT(DISTINCT CONCAT(linea_id, '-', referencia_id, '-', material_id, '-', color_id)) AS total_skus,
                    COUNT(DISTINCT marca_id) AS total_marcas
                FROM {tabla}
            """))
            row = result.fetchone()
            print(f"   Total inicial: {float(row[0] or 0):,.0f}")
            print(f"   Total SKUs: {row[1]}")
            print(f"   Total marcas: {row[2]}")
        except Exception as e:
            print(f"   ERROR: {e}")
            return

        # Probar query de datos jerárquicos
        print("\n3. Query de datos jerárquicos...")
        try:
            result = conn.execute(text(f"""
                SELECT
                    d.batch_label,
                    COALESCE(g.id, 0) AS genero_id,
                    COALESCE(g.descripcion, 'Sin genero') AS genero,
                    COALESCE(m.id_marca, 0) AS marca_id,
                    COALESCE(m.descp_marca, 'Sin marca') AS marca,
                    e.id_grupo_estilo AS estilo_id,
                    e.descp_grupo_estilo AS estilo,
                    d.linea_codigo_proveedor AS linea_codigo,
                    d.referencia_codigo_proveedor AS ref_codigo,
                    d.excel_material_code AS material_code,
                    d.excel_color_code AS color_code,
                    d.grada,
                    d.cantidad
                FROM {tabla} d
                LEFT JOIN genero g ON g.id = d.genero_id
                LEFT JOIN marca_v2 m ON m.id_marca = d.marca_id
                LEFT JOIN grupo_estilo_v2 e ON e.id_grupo_estilo = d.grupo_estilo_id
                ORDER BY d.batch_label, genero, marca, estilo, linea_codigo, ref_codigo
                LIMIT 5
            """))
            rows = list(result)
            print(f"   {len(rows)} filas de ejemplo:")
            for row in rows[:3]:
                print(f"     - PP: {row[0]}, Género: {row[2]}, Marca: {row[4]}")
        except Exception as e:
            print(f"   ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
