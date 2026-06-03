"""
Verificar si las migraciones 052-054 estan realmente aplicadas en Supabase
"""

from sqlalchemy import create_engine, text

# Supabase connection
CONN_STR = (
    "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@"
    "aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
    "?sslmode=require&application_name=verificacion_migraciones"
)

def verificar_migraciones():
    """Verifica si las migraciones estan aplicadas"""
    print("=" * 80)
    print("VERIFICACION MIGRACIONES 052-054 EN SUPABASE PROD")
    print("=" * 80)

    engine = create_engine(CONN_STR, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            # Verificar indices de migracion 052
            print("\n[CHECK 052] Verificando indices triplete en precio_lista...")
            result = conn.execute(text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'precio_lista'
                  AND indexname LIKE '%triplete%'
                ORDER BY indexname
            """))
            indices = [row[0] for row in result]

            if indices:
                print(f"  [OK] Indices encontrados: {len(indices)}")
                for idx in indices:
                    print(f"     - {idx}")
            else:
                print("  [FALTA] NO SE ENCONTRARON indices triplete")

            # Verificar funcion de migracion 053
            print("\n[CHECK 053] Verificando funcion calcular_precio_lista_evento_sql...")
            result = conn.execute(text("""
                SELECT proname, pronargs
                FROM pg_proc
                WHERE proname = 'calcular_precio_lista_evento_sql'
            """))
            funcion_053 = result.fetchone()

            if funcion_053:
                print(f"  [OK] Funcion encontrada: {funcion_053[0]}({funcion_053[1]} args)")
            else:
                print("  [FALTA] NO SE ENCONTRO funcion calcular_precio_lista_evento_sql")

            # Verificar funcion de migracion 054
            print("\n[CHECK 054] Verificando funcion resolver_pilares_sql...")
            result = conn.execute(text("""
                SELECT proname, pronargs
                FROM pg_proc
                WHERE proname = 'resolver_pilares_sql'
            """))
            funcion_054 = result.fetchone()

            if funcion_054:
                print(f"  [OK] Funcion encontrada: {funcion_054[0]}({funcion_054[1]} args)")
            else:
                print("  [FALTA] NO SE ENCONTRO funcion resolver_pilares_sql")

            # Verificar indices de migracion 054
            print("\n[CHECK 054] Verificando indices (proveedor_id, codigo_proveedor)...")
            result = conn.execute(text("""
                SELECT
                    tablename,
                    indexname
                FROM pg_indexes
                WHERE indexname IN (
                    'idx_linea_proveedor_codigo',
                    'idx_referencia_proveedor_codigo',
                    'idx_material_proveedor_codigo'
                )
                ORDER BY tablename
            """))
            indices_054 = list(result)

            if indices_054:
                print(f"  [OK] Indices encontrados: {len(indices_054)}")
                for row in indices_054:
                    print(f"     - {row[0]}.{row[1]}")
            else:
                print("  [WARN] NO SE ENCONTRARON indices pilar (pueden existir por UNIQUE constraint)")

            # Resumen
            print("\n" + "=" * 80)
            print("RESUMEN")
            print("=" * 80)

            all_ok = bool(indices and funcion_053 and funcion_054)

            if all_ok:
                print("[OK] TODAS LAS MIGRACIONES ESTAN APLICADAS")
            else:
                print("[FALTA] FALTAN MIGRACIONES POR APLICAR")
                if not indices:
                    print("   - Migracion 052 pendiente")
                if not funcion_053:
                    print("   - Migracion 053 pendiente")
                if not funcion_054:
                    print("   - Migracion 054 pendiente")

            return all_ok

    except Exception as e:
        print(f"\n[ERROR] al verificar: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        engine.dispose()

if __name__ == "__main__":
    result = verificar_migraciones()
    import sys
    sys.exit(0 if result else 1)
