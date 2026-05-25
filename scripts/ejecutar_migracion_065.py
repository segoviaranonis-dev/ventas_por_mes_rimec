#!/usr/bin/env python3
"""Ejecuta la migración 065: Validación de Stock en confirmar_pedido_web"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
LOG = Path(__file__).resolve().parent / "ejecutar_migracion_065.log"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import create_engine, text  # noqa: E402

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
    raise SystemExit("Falta DATABASE_URL o .streamlit/secrets.toml [postgres]")

def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def main() -> None:
    LOG.write_text("", encoding="utf-8")
    log("Inicio — ejecutar migración 065")
    
    migration_file = ROOT / "migrations" / "065_rpc_confirmar_pedido_web_stock_check.sql"
    if not migration_file.exists():
        log(f"ERROR: No se encontró la migración en {migration_file}")
        sys.exit(1)
        
    sql = migration_file.read_text(encoding="utf-8")
    eng = create_engine(_db_url(), pool_pre_ping=True)
    with eng.begin() as conn:
        conn.execute(text(sql))
    log("OK — migración 065 aplicada exitosamente")
    print("¡Listo!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        raise
