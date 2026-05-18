"""
Ejecutar migración 052: índice triplete precio_lista
OT-MOTOR-SQL-520-001
"""

import sys
sys.path.insert(0, "C:\\Users\\hecto\\Nexus_Core\\control_central")

from core.database import engine
from sqlalchemy import text

def run_migration_052():
    """Ejecuta migración 052 - índice triplete"""

    sql_file = "C:\\Users\\hecto\\Nexus_Core\\control_central\\migrations\\052_precio_lista_indice_triplete.sql"

    print("="*80)
    print("MIGRACIÓN 052 - Índice triplete precio_lista")
    print("="*80)

    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        print(f"\n[OK] Archivo leido: {sql_file}")
        print(f"  Tamano: {len(sql_content)} bytes\n")

        # Ejecutar SQL
        with engine.begin() as conn:
            conn.execute(text(sql_content))
            print("[OK] Migracion 052 ejecutada exitosamente\n")

            # Verificar índices creados
            result = conn.execute(text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'precio_lista'
                  AND indexname LIKE '%triplete%'
                ORDER BY indexname
            """))

            print("Índices creados:")
            for row in result:
                print(f"  • {row[0]}")

        print("\n" + "="*80)
        print("MIGRACIÓN 052 COMPLETADA")
        print("="*80)
        return True

    except Exception as e:
        print(f"\n[ERROR] ejecutando migracion 052:")
        print(f"  {str(e)}")
        return False

if __name__ == "__main__":
    success = run_migration_052()
    sys.exit(0 if success else 1)
