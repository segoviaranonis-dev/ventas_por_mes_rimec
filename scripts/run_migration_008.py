"""
Ejecuta la migración 008: Flujo Reserva/Liberación de FI.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine, DBInspector
from sqlalchemy import text

sql_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "migrations", "008_fi_reserva_liberacion.sql")

with open(sql_path, "r", encoding="utf-8") as f:
    sql = f.read()

# Remove transaction wrappers — engine.begin() handles it
sql_clean = sql.replace("BEGIN;", "").replace("COMMIT;", "")

# Split into individual statements, respecting $$ function bodies
statements = []
current = []
in_function = False
for line in sql_clean.split("\n"):
    stripped = line.strip()
    if stripped.startswith("--") and not in_function:
        continue
    if "$$" in line:
        in_function = not in_function
    current.append(line)
    if not in_function and stripped.endswith(";"):
        stmt = "\n".join(current).strip()
        if stmt and stmt != ";":
            statements.append(stmt)
        current = []

# If there's remaining content
if current:
    stmt = "\n".join(current).strip()
    if stmt and stmt != ";":
        statements.append(stmt)

print(f"Encontradas {len(statements)} sentencias SQL")
print("=" * 60)

try:
    with engine.begin() as conn:
        for i, stmt in enumerate(statements):
            preview = stmt[:100].replace("\n", " ")
            print(f"\n[{i+1}/{len(statements)}] {preview}...")
            conn.execute(text(stmt))
            print(f"  OK")

    print("\n" + "=" * 60)
    print("=== MIGRACION 008 COMPLETADA EXITOSAMENTE ===")
    print("=" * 60)

    # Verificaciones
    with engine.connect() as conn:
        # Verificar constraint
        r = conn.execute(text("""
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'factura_interna'
              AND c.conname = 'factura_interna_estado_check'
        """)).fetchone()
        print(f"\nCHECK constraint: {r[0] if r else 'NO ENCONTRADO'}")

        # Verificar funcion
        r2 = conn.execute(text("""
            SELECT proname FROM pg_proc WHERE proname = 'revertir_stock_fi'
        """)).fetchone()
        print(f"Funcion revertir_stock_fi: {'EXISTE' if r2 else 'NO EXISTE'}")

        # Verificar columna notas
        r3 = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'factura_interna' AND column_name = 'notas'
        """)).fetchone()
        print(f"Columna notas: {'EXISTE' if r3 else 'NO EXISTE'}")

        # Verificar indice
        r4 = conn.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'factura_interna' AND indexname = 'idx_fi_estado'
        """)).fetchone()
        print(f"Indice idx_fi_estado: {'EXISTE' if r4 else 'NO EXISTE'}")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
