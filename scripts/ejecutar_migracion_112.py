#!/usr/bin/env python3
"""
Ejecutar migración 112: Tabla tiendas_marcas
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    print("=" * 70)
    print(" EJECUTANDO MIGRACIÓN 112: Tabla tiendas_marcas")
    print("=" * 70)

    migration_file = Path(__file__).resolve().parents[1] / "migrations" / "112_tiendas_marcas.sql"

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
        print(" MIGRACIÓN 112 EJECUTADA EXITOSAMENTE")
        print("=" * 70)

        print("\nTabla creada:")
        print("  - tiendas_marcas")

        print("\nRelaciones creadas:")
        print("  ADULTOS (todas excepto Molekinha/Molekinho):")
        print("    - 2100: Fernando Adultos")
        print("    - 2400: San Martin Adultos")
        print("    - 3100: Palma Adultos")
        print("")
        print("  NIÑOS (SOLO Molekinha/Molekinho):")
        print("    - 2900: Fernando Niños")
        print("    - 2700: San Martin Niños")
        print("    - 3200: Palma Niños")

        print("\nVista creada:")
        print("  - v_tiendas_marcas_detalle")

        print("\nVerificando relaciones...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT cliente_id, COUNT(*) as total_marcas
                FROM tiendas_marcas
                GROUP BY cliente_id
                ORDER BY cliente_id
            """))

            print("\nMarcas por tienda:")
            for row in result:
                cliente_id = row[0]
                total = row[1]
                tipo = "Niños" if cliente_id in (2900, 2700, 3200) else "Adultos"
                print(f"  {cliente_id} ({tipo}): {total} marcas permitidas")

    except Exception as e:
        print("\n" + "=" * 70)
        print(" ERROR AL EJECUTAR MIGRACIÓN")
        print("=" * 70)
        print(f"\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
