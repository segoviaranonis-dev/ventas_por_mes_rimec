#!/usr/bin/env python3
"""Conteo rápido de pilares tras un reset. Uso: python scripts/diagnostico_pilares_conteo.py"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from decouple import UndefinedValueError, config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


def _db_url() -> str:
    try:
        u = config("DATABASE_URL")
        if u:
            return u
    except UndefinedValueError:
        pass
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
    raise SystemExit("DATABASE_URL o secrets.toml [postgres]")


def main() -> None:
    engine = create_engine(_db_url())
    tablas = ("linea", "referencia", "linea_referencia", "material", "color", "talla")
    print("=== Conteo pilares ===")
    with engine.connect() as conn:
        for t in tablas:
            n = conn.execute(text(f"SELECT COUNT(*) FROM public.{t}")).scalar()
            print(f"  {t}: {n}")
    print("\nSi linea = 0, restaurar desde backup Supabase o re-importar Excel de pilares.")


if __name__ == "__main__":
    main()
