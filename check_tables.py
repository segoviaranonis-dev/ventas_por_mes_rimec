from core.database import engine
from sqlalchemy import text

conn = engine.connect()

# Buscar tablas v2
result = conn.execute(text("""
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
      AND (tablename LIKE '%_v2' OR tablename LIKE 'v_%')
    ORDER BY tablename
""")).fetchall()

print("=" * 60)
print("TABLAS V2 Y VISTAS:")
print("=" * 60)
for t in result:
    print(f"  + {t[0]}")

print(f"\nTotal: {len(result)} tablas")

# Verificar las que faltan
missing = ['categoria_v2', 'tipo_v2', 'v_ventas_pivot']
print("\n" + "=" * 60)
print("VERIFICANDO TABLAS REQUERIDAS:")
print("=" * 60)

for table in missing:
    exists = conn.execute(text(f"""
        SELECT EXISTS (
            SELECT 1 FROM pg_tables
            WHERE schemaname = 'public' AND tablename = '{table}'
        )
    """)).scalar()

    status = "[OK] EXISTE" if exists else "[X] FALTA"
    print(f"  {status}: {table}")

conn.close()