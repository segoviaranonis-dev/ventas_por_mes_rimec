"""
Script para contar tablas en la base de datos RIMEC.
"""
from core.database import get_dataframe

# Query para obtener todas las tablas del esquema public
query = """
SELECT
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
ORDER BY table_name;
"""

print("Consultando tablas en la base de datos...\n")

df = get_dataframe(query)

if not df.empty:
    print(f"TOTAL DE TABLAS: {len(df)}\n")
    print("=" * 60)
    print("Lista de tablas:")
    print("=" * 60)
    for idx, row in df.iterrows():
        print(f"  {idx + 1:3d}. {row['table_name']}")
    print("=" * 60)
else:
    print("No se pudieron obtener las tablas.")
