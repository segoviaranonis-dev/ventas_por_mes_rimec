from core.database import engine
from sqlalchemy import text as sqlt

with engine.connect() as conn:
    print("=== TABLA: linea ===")
    cols_linea = conn.execute(sqlt("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'linea'
        ORDER BY ordinal_position
    """)).fetchall()
    for c in cols_linea:
        print(f"  {c[0]:30} {c[1]}")

    print("\n=== TABLA: referencia ===")
    cols_ref = conn.execute(sqlt("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'referencia'
        ORDER BY ordinal_position
    """)).fetchall()
    for c in cols_ref:
        print(f"  {c[0]:30} {c[1]}")

    print("\n=== TABLA: talla ===")
    cols_talla = conn.execute(sqlt("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'talla'
        ORDER BY ordinal_position
    """)).fetchall()
    for c in cols_talla:
        print(f"  {c[0]:30} {c[1]}")
