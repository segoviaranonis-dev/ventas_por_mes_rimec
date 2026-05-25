#!/usr/bin/env python3
"""Recrea v_stock_rimec en Supabase (sin Streamlit). Escribe scripts/aplicar_vista_stock_cli.log"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
LOG = Path(__file__).resolve().parent / "aplicar_vista_stock_cli.log"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import create_engine, text  # noqa: E402

from scripts.fix_v_stock_rimec import SQL  # noqa: E402


def _db_url() -> str:
    try:
        from decouple import config

        u = config("DATABASE_URL")
        if u:
            return u
    except Exception:
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
    raise SystemExit("Falta DATABASE_URL o .streamlit/secrets.toml [postgres]")


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    LOG.write_text("", encoding="utf-8")
    log("Inicio — recrear v_stock_rimec")
    eng = create_engine(_db_url(), pool_pre_ping=True)
    with eng.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS v_stock_rimec CASCADE"))
        conn.execute(text(SQL))
    log("OK — vista recreada")

    q = text(
        """
        SELECT linea_codigo, referencia_codigo, linea_id, referencia_id,
               descp_grupo_estilo, descp_tipo_1
        FROM v_stock_rimec
        WHERE (linea_codigo, referencia_codigo) IN (
          ('1214','1073'), ('1214','1075'), ('1388','500')
        )
        GROUP BY 1,2,3,4,5,6
        ORDER BY 1,2
        """
    )
    import pandas as pd

    df = pd.read_sql(q, eng)
    log("—— Pares de prueba ——")
    log("\n" + df.to_string(index=False))

    q_val = text("""
        SELECT COUNT(*) AS n
        FROM v_stock_rimec
        WHERE lpn > 0 AND caso_id IS NULL
    """)
    n_sin_caso = int(pd.read_sql(q_val, eng).iloc[0, 0])
    log("—— Validación MIG-071 (lpn>0 AND caso_id IS NULL) ——")
    log(f"Conteo: {n_sin_caso} (debe ser 0)")
    if n_sin_caso != 0:
        log("ERROR: Hay filas con precio sin caso_id — revisar JOIN icp / precio_lista")
        raise SystemExit(1)
    log("OK — validación cumplida")
    log(f"Listo. Log: {LOG}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        raise
