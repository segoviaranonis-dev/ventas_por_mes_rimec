"""
OT-WEB-PRECIO-509-001 D1-D2: Aplicar migración 048 (tabla + seed + función).
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2

from scripts.backfill_combinacion_desde_ppd import _db_url


def main() -> bool:
    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return False

    migration_path = ROOT / "migrations" / "048_caso_precio_web_regla.sql"

    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read()

    print("=" * 80)
    print("APLICAR MIGRACIÓN 048: caso_precio_web_regla")
    print("=" * 80)
    print()

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    try:
        cur.execute(sql)
        conn.commit()
        print("[OK] Migración 048 aplicada exitosamente")
        print("  - Tabla caso_precio_web_regla creada")
        print("  - 6 reglas seed insertadas (5 casos + DEFAULT)")
        print("  - Función fn_precio_venta_web creada")
        print()

        # Verificar seed
        cur.execute("SELECT caso_codigo, markup_pct, activo FROM caso_precio_web_regla ORDER BY caso_codigo")
        rows = cur.fetchall()
        print(f"[VERIFICAR] {len(rows)} reglas en BD:")
        for codigo, markup, activo in rows:
            estado = "OK" if activo else "OFF"
            print(f"  {estado} {codigo}: +{markup}%")

        # Test función
        print()
        print("[TEST] fn_precio_venta_web(100000, 'ACT-BRSPORT'):")
        cur.execute("SELECT fn_precio_venta_web(100000, 'ACT-BRSPORT')")
        resultado = cur.fetchone()[0]
        print(f"  Resultado: {resultado} Gs (esperado: 150000)")

        if resultado == 150000:
            print("  PASS")
        else:
            print(f"  FAIL (esperado 150000, obtenido {resultado})")

    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

    print()
    print("=" * 80)
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
