#!/usr/bin/env python3
"""
Ejecutar migración 113: Sistema de Categorías de Cliente
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    print("=" * 70)
    print(" EJECUTANDO MIGRACIÓN 113: Sistema de Categorías de Cliente")
    print("=" * 70)

    migration_file = Path(__file__).resolve().parents[1] / "migrations" / "113_categoria_cliente_sistema.sql"

    if not migration_file.exists():
        print(f"\nERROR: Archivo de migración no encontrado: {migration_file}")
        sys.exit(1)

    print(f"\nLeyendo migración desde: {migration_file}")
    sql = migration_file.read_text(encoding="utf-8")

    print("\nEjecutando SQL...")
    engine = get_engine()

    try:
        with engine.begin() as conn:
            conn.execute(text(sql))

        print("\n" + "=" * 70)
        print(" MIGRACIÓN 113 EJECUTADA EXITOSAMENTE")
        print("=" * 70)

        print("\nTablas creadas:")
        print("  1. categoria_cliente (maestro)")
        print("  2. categoria_cliente_marca (relacional)")

        print("\nCategorías creadas:")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, codigo, descripcion
                FROM categoria_cliente
                ORDER BY orden
            """))

            for row in result:
                print(f"  {row[0]}. {row[1]}: {row[2]}")

        print("\nMarcas por categoría:")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                  cc.codigo,
                  COUNT(ccm.marca_id) as total_marcas
                FROM categoria_cliente cc
                LEFT JOIN categoria_cliente_marca ccm ON ccm.categoria_id = cc.id
                GROUP BY cc.id, cc.codigo
                ORDER BY cc.id
            """))

            for row in result:
                print(f"  {row[0]}: {row[1]} marcas")

        print("\nTiendas actualizadas (heredando de categorías):")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT cliente_id, COUNT(*) as total_marcas
                FROM tiendas_marcas
                GROUP BY cliente_id
                ORDER BY cliente_id
            """))

            for row in result:
                cliente_id = row[0]
                total = row[1]
                tipo = "Niños" if cliente_id in (2900, 2700, 3200) else "Adultos"
                print(f"  {cliente_id} ({tipo}): {total} marcas permitidas")

        print("\nVistas creadas:")
        print("  - v_categoria_marcas")
        print("  - v_tiendas_con_categoria")
        print("  - v_resumen_categorias")

        print("\n" + "=" * 70)
        print(" SISTEMA DE CATEGORÍAS LISTO PARA USO EN TODO EL PROYECTO")
        print("=" * 70)

    except Exception as e:
        print("\n" + "=" * 70)
        print(" ERROR AL EJECUTAR MIGRACIÓN")
        print("=" * 70)
        print(f"\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
