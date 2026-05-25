#!/usr/bin/env python3
"""Ejecuta auditoría completa del carrito de Bzzf"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import create_engine, text
import pandas as pd

def _db_url() -> str:
    p = ROOT / ".streamlit" / "secrets.toml"
    if p.is_file():
        import tomllib
        with p.open("rb") as f:
            pg = tomllib.load(f).get("postgres")
        if isinstance(pg, dict):
            user = pg.get("user") or pg.get("username")
            pwd = pg.get("password")
            host = pg.get("host", "localhost")
            port = pg.get("port", 5432)
            db = pg.get("database") or pg.get("dbname")
            if user and pwd and db:
                return (
                    f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(pwd)}"
                    f"@{host}:{port}/{db}"
                )
    raise SystemExit("Falta .streamlit/secrets.toml [postgres]")

def main():
    eng = create_engine(_db_url(), pool_pre_ping=True)

    sql_file = ROOT / "scripts" / "diagnostico" / "auditoria_carrito_bzzf.sql"
    sql = sql_file.read_text(encoding="utf-8")

    # Dividir por queries individuales
    queries = [q.strip() for q in sql.split(';') if q.strip() and not q.strip().startswith('--')]

    print("=" * 80)
    print("AUDITORÍA CARRITO BZZF")
    print("=" * 80)

    with eng.connect() as conn:
        for i, query in enumerate(queries, 1):
            if 'SELECT' not in query.upper():
                continue

            try:
                result = pd.read_sql(text(query), conn)
                if not result.empty:
                    print(f"\n{'=' * 80}")
                    print(f"Query {i}")
                    print('=' * 80)
                    print(result.to_string())
                else:
                    print(f"\nQuery {i}: (sin resultados)")
            except Exception as e:
                print(f"\nQuery {i}: ERROR - {e}")

    print("\n" + "=" * 80)
    print("AUDITORÍA COMPLETADA")
    print("=" * 80)

if __name__ == "__main__":
    main()
