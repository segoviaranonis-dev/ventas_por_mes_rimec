#!/usr/bin/env python3
"""
Ejecuta el vaciado operativo de staging (misma intención que
migrations/034_retail_staging_operativo_vaciado.sql).

Orden de resolución de conexión (no imprime secretos):
  1) variable de entorno DATABASE_URL
  2) .env en la raíz del repo (DATABASE_URL)
  3) .streamlit/secrets.toml → sección [postgres] (mismo esquema que core/database.py)
  4) python-decouple DATABASE_URL
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from decouple import Config, RepositoryEnv  # noqa: E402
from decouple import UndefinedValueError, config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


def _url_from_streamlit_secrets() -> str | None:
    p = ROOT / ".streamlit" / "secrets.toml"
    if not p.is_file():
        return None
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    with p.open("rb") as f:
        data = tomllib.load(f)
    pg = data.get("postgres")
    if not isinstance(pg, dict):
        return None
    for k in ("user", "password", "host", "port", "dbname"):
        if k not in pg:
            return None
    user = str(pg["user"]).strip()
    pwd = quote_plus(str(pg["password"]))
    host = str(pg["host"]).strip()
    port = int(pg["port"])
    dbn = str(pg["dbname"]).strip()
    return f"postgresql://{user}:{pwd}@{host}:{port}/{dbn}?sslmode=require"


def get_database_url() -> str:
    u = (os.environ.get("DATABASE_URL") or "").strip()
    if u:
        return u
    env_path = ROOT / ".env"
    if env_path.is_file():
        try:
            cfg = Config(RepositoryEnv(str(env_path)))
            u2 = str(cfg("DATABASE_URL")).strip()
            if u2:
                return u2
        except UndefinedValueError:
            pass
    u3 = _url_from_streamlit_secrets()
    if u3:
        return u3
    try:
        return str(config("DATABASE_URL")).strip()
    except UndefinedValueError as e:
        raise SystemExit(
            "Falta conexión: definí DATABASE_URL, .env con DATABASE_URL, o .streamlit/secrets.toml con [postgres]."
        ) from e


def main() -> None:
    url = get_database_url()
    eng = create_engine(url, pool_pre_ping=True)
    sql_count = text("SELECT COUNT(*)::bigint FROM public.retail_multitienda_staging")
    sql_trunc = text("TRUNCATE TABLE public.retail_multitienda_staging RESTART IDENTITY")
    sql_delete = text("DELETE FROM public.retail_multitienda_staging")
    with eng.connect() as c:
        before = int(c.execute(sql_count).scalar() or 0)
    try:
        with eng.begin() as conn:
            conn.execute(sql_trunc)
        mode = "TRUNCATE"
    except Exception as exc:
        print(f"TRUNCATE no aplicó ({exc!r}); usando DELETE…", flush=True)
        with eng.begin() as conn:
            conn.execute(sql_delete)
        mode = "DELETE"
    print(f"OK ({mode}): retail_multitienda_staging vaciada. Filas que había: {before}.", flush=True)


if __name__ == "__main__":
    main()
