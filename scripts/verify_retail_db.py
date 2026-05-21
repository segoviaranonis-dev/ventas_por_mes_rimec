#!/usr/bin/env python3
"""Verifica tablas Retail vs Sales Report en Supabase."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import create_engine, text

from scripts.print_lr_1143_309 import get_database_url


def main() -> None:
    url = get_database_url()
    if not url:
        print("ERROR: sin DATABASE_URL (.env o secrets.toml)")
        sys.exit(1)

    eng = create_engine(url, pool_pre_ping=True)
    checks = [
        ("registro_st_vt_rc_reposicion", """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'registro_st_vt_rc_reposicion'
            ORDER BY ordinal_position
        """),
        ("registro_st_vt_rc_reposicion count", """
            SELECT COUNT(*)::bigint AS n FROM public.registro_st_vt_rc_reposicion
        """),
        ("registro_ventas_general_v2 count", """
            SELECT COUNT(*)::bigint AS n FROM public.registro_ventas_general_v2
        """),
        ("retail_multitienda_staging count (legacy)", """
            SELECT COUNT(*)::bigint AS n FROM public.retail_multitienda_staging
        """),
    ]

    print("=== VERIFICACION DB RETAIL / SALES ===\n")
    with eng.connect() as conn:
        for label, sql in checks:
            try:
                rows = conn.execute(text(sql)).fetchall()
                if "column_name" in sql:
                    print(f"[OK] {label}: {len(rows)} columnas")
                    for r in rows[:8]:
                        print(f"     - {r[0]} ({r[1]})")
                    if len(rows) > 8:
                        print(f"     ... +{len(rows) - 8} mas")
                else:
                    print(f"[OK] {label}: {rows[0][0]}")
            except Exception as e:
                print(f"[FAIL] {label}: {e}")
    print("\nFin.")


if __name__ == "__main__":
    main()
