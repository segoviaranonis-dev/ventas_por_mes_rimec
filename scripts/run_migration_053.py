"""
Ejecutar migración 053: función calcular_precio_lista_evento_sql + staging
OT-MOTOR-SQL-520-001
"""

import sys
sys.path.insert(0, "C:\\Users\\hecto\\Nexus_Core\\control_central")

from core.database import engine
from sqlalchemy import text

def run_migration_053():
    """Ejecuta migración 053 - función SQL masiva + tabla staging"""

    sql_file = "C:\\Users\\hecto\\Nexus_Core\\control_central\\migrations\\053_calcular_precio_lista_evento_sql.sql"

    print("="*80)
    print("MIGRACIÓN 053 - Función SQL masiva + tabla staging")
    print("="*80)

    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        print(f"\n[OK] Archivo leido: {sql_file}")
        print(f"  Tamano: {len(sql_content)} bytes\n")

        # Ejecutar SQL
        with engine.begin() as conn:
            conn.execute(text(sql_content))
            print("[OK] Migracion 053 ejecutada exitosamente\n")

            # Verificar tabla staging
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'precio_lista_staging'
            """))

            if result.fetchone():
                print("[OK] Tabla precio_lista_staging creada")

            # Verificar función
            result = conn.execute(text("""
                SELECT routine_name, routine_type
                FROM information_schema.routines
                WHERE routine_schema = 'public'
                  AND routine_name = 'calcular_precio_lista_evento_sql'
            """))

            if result.fetchone():
                print("[OK] Funcion calcular_precio_lista_evento_sql creada")

        print("\n" + "="*80)
        print("MIGRACIÓN 053 COMPLETADA")
        print("="*80)
        return True

    except Exception as e:
        print(f"\n[ERROR] ejecutando migracion 053:")
        print(f"  {str(e)}")
        return False

if __name__ == "__main__":
    success = run_migration_053()
    sys.exit(0 if success else 1)
