#!/usr/bin/env python3
"""
Ejecutar migración 111: Depósitos Bazzar - 6 Tiendas
"""

import sys
from pathlib import Path

# Agregar control_central al path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    print("=" * 70)
    print(" EJECUTANDO MIGRACIÓN 111: Depósitos Bazzar - 6 Tiendas")
    print("=" * 70)

    migration_file = Path(__file__).resolve().parents[1] / "migrations" / "111_depositos_bazzar_tiendas.sql"

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
        print(" MIGRACIÓN 111 EJECUTADA EXITOSAMENTE")
        print("=" * 70)

        print("\nTablas creadas:")
        print("  1. deposito_tienda_fernando_adultos   (cliente_id 2100)")
        print("  2. deposito_tienda_fernando_ninos     (cliente_id 2900)")
        print("  3. deposito_tienda_sanmartin_adultos  (cliente_id 2400)")
        print("  4. deposito_tienda_sanmartin_ninos    (cliente_id 2700)")
        print("  5. deposito_tienda_palma_adultos      (cliente_id 3100)")
        print("  6. deposito_tienda_palma_ninos        (cliente_id 3200)")

        print("\nÍndices creados: 18 (3 por tabla)")
        print("\nPróximo paso: http://localhost:3000/depositos-bazzar")

    except Exception as e:
        print("\n" + "=" * 70)
        print(" ERROR AL EJECUTAR MIGRACIÓN")
        print("=" * 70)
        print(f"\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
