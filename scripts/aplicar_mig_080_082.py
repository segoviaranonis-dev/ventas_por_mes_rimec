"""
Aplicar MIG-080 → 082: carrito persistente + validar/confirmar atómico.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backfill_combinacion_desde_ppd import _db_url

MIGS = (
    "080_carrito_persistente_multidispositivo.sql",
    "081_fn_carrito_validar_y_confirmar_atomico.sql",
    "082_rpc_confirmar_pedido_web_token_y_lock.sql",
)


def main() -> int:
    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return 1

    import psycopg2

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    for name in MIGS:
        path = ROOT / "migrations" / name
        sql = path.read_text(encoding="utf-8")
        print(f"\n>> {name}")
        cur.execute(sql)
        conn.commit()
        print("   OK")

    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('carrito_sesion','carrito_item')
        ORDER BY table_name
    """)
    tablas = [r[0] for r in cur.fetchall()]
    print(f"\nTablas creadas: {tablas}")

    cur.execute("""
        SELECT proname
        FROM pg_proc
        WHERE proname IN ('carrito_validar','carrito_token_vigente','confirmar_pedido_web','vincular_listado_a_pp')
        ORDER BY proname
    """)
    funcs = [r[0] for r in cur.fetchall()]
    print(f"Funciones presentes: {funcs}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
