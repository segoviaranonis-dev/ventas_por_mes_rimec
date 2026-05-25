#!/usr/bin/env python3
"""Verifica: filas con precio (lpn) deben tener caso desde precio_lista."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text

from scripts.aplicar_vista_stock_cli import _db_url  # noqa: E402


def main() -> None:
    from scripts.fix_v_stock_rimec import SQL

    eng = create_engine(_db_url(), pool_pre_ping=True)
    with eng.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS v_stock_rimec CASCADE"))
        conn.execute(text(SQL))

    q_control = text("""
        SELECT COUNT(*) AS con_precio_sin_caso
        FROM v_stock_rimec
        WHERE lpn > 0 AND caso_id IS NULL
    """)
    q_stats = text("""
        SELECT
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE lpn > 0) AS con_precio
        FROM v_stock_rimec
    """)

    with eng.connect() as conn:
        control = conn.execute(q_control).scalar_one()
        stats = conn.execute(q_stats).mappings().one()

    print("=== MIG-071 — Validación post-aplicación ===")
    print(f"Total filas:              {stats['total']}")
    print(f"Con precio (lpn > 0):     {stats['con_precio']}")
    print(f"lpn>0 AND caso_id NULL:   {control}")

    if control != 0:
        print("FALLO — muestra de filas inconsistentes:")
        with eng.connect() as conn:
            rows = conn.execute(text("""
                SELECT pp_nro, linea_codigo, referencia_codigo, material_code,
                       lpn, caso_id, descp_caso
                FROM v_stock_rimec
                WHERE lpn > 0 AND caso_id IS NULL
                LIMIT 10
            """))
            for r in rows.mappings():
                print(dict(r))
        raise SystemExit(1)

    print("OK — conteo EXACTAMENTE 0 (lpn>0 con caso_id NULL)")


if __name__ == "__main__":
    main()
