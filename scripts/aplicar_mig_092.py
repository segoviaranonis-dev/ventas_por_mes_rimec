#!/usr/bin/env python3
"""
Aplica MIG-092: Funciones RPC para aprobación/rechazo de pedidos
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backfill_combinacion_desde_ppd import _db_url

def main() -> int:
    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return 1

    import psycopg2

    migration_file = ROOT / "migrations" / "092_rpc_aprobacion_pedidos.sql"

    if not migration_file.exists():
        print(f"[ERROR] No encontrado: {migration_file}")
        return 1

    print(">> Aplicando MIG-092: RPC aprobacion de pedidos")
    print(f"   Archivo: {migration_file}")
    print()

    sql = migration_file.read_text(encoding="utf-8")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    try:
        print(">> Ejecutando migración...")
        cur.execute(sql)
        conn.commit()
        print("   OK")

        # Verificar funciones creadas
        cur.execute("""
            SELECT proname
            FROM pg_proc
            WHERE proname IN ('aprobar_pedido', 'rechazar_pedido')
            ORDER BY proname
        """)
        funcs = [r[0] for r in cur.fetchall()]

        print()
        print("[OK] MIG-092 aplicada exitosamente")
        print()
        print(f"Funciones creadas: {funcs}")
        print()
        print("Columnas agregadas a pedido_venta:")
        print("  - fecha_aprobacion")
        print("  - aprobado_por_id")
        print("  - fecha_rechazo")
        print("  - rechazado_por_id")
        print("  - motivo_rechazo")

        return 0

    except Exception as e:
        print()
        print(f"[ERROR] Error aplicando MIG-092: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())
