#!/usr/bin/env python3
"""
Diagnóstico y backfill de caso_id para línea 1143 (proveedor 654).
Uso: python scripts/diagnostico_linea_caso.py
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

PROVEEDOR_ID = 654
LINEA_COD = 1143


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
            "Falta conexión: DATABASE_URL, .env o .streamlit/secrets.toml [postgres]."
        ) from e


def _print_rows(title: str, rows: list) -> None:
    print(f"\n=== {title} ===", flush=True)
    if not rows:
        print("(sin filas)", flush=True)
        return
    keys = rows[0]._mapping.keys()
    print(" | ".join(keys), flush=True)
    print("-" * 60, flush=True)
    for r in rows:
        print(" | ".join(str(r._mapping[k]) for k in keys), flush=True)


def main() -> None:
    url = get_database_url()
    eng = create_engine(url, pool_pre_ping=True)
    print(f"Conectado (host en URL oculto). proveedor_id={PROVEEDOR_ID} linea={LINEA_COD}", flush=True)

    q_linea = text(
        """
        SELECT id, codigo_proveedor, caso_id, descripcion, marca_id, genero_id
        FROM public.linea
        WHERE proveedor_id = :p AND codigo_proveedor = :lc
        """
    )
    q_fuentes = text(
        """
        SELECT codigo_proveedor, caso_id, id
        FROM public.linea
        WHERE proveedor_id = :p
          AND codigo_proveedor < :lc
          AND caso_id IS NOT NULL
        ORDER BY codigo_proveedor DESC
        LIMIT 10
        """
    )
    q_preview = text(
        """
        SELECT dest.id, dest.codigo_proveedor, dest.caso_id AS caso_actual, src.caso_id AS caso_heredado
        FROM public.linea dest
        CROSS JOIN (
            SELECT caso_id
            FROM public.linea
            WHERE proveedor_id = :p
              AND codigo_proveedor < :lc
              AND caso_id IS NOT NULL
            ORDER BY codigo_proveedor DESC
            LIMIT 1
        ) AS src
        WHERE dest.proveedor_id = :p
          AND dest.codigo_proveedor = :lc
          AND dest.caso_id IS NULL
        """
    )
    q_update = text(
        """
        UPDATE public.linea dest
        SET caso_id = src.caso_id
        FROM (
            SELECT caso_id
            FROM public.linea
            WHERE proveedor_id = :p
              AND codigo_proveedor < :lc
              AND caso_id IS NOT NULL
            ORDER BY codigo_proveedor DESC
            LIMIT 1
        ) AS src
        WHERE dest.proveedor_id = :p
          AND dest.codigo_proveedor = :lc
          AND dest.caso_id IS NULL
        RETURNING dest.id, dest.codigo_proveedor, dest.caso_id
        """
    )
    q_lr = text(
        """
        SELECT lr.id, l.codigo_proveedor AS linea, r.codigo_proveedor AS ref,
               lr.grupo_estilo_id, lr.tipo_1_id, lr.descp_grupo_estilo, lr.descp_tipo_1
        FROM public.linea_referencia lr
        JOIN public.linea l ON l.id = lr.linea_id AND l.proveedor_id = lr.proveedor_id
        JOIN public.referencia r ON r.id = lr.referencia_id AND r.proveedor_id = lr.proveedor_id
        WHERE lr.proveedor_id = :p AND l.codigo_proveedor = :lc
        ORDER BY r.codigo_proveedor
        LIMIT 20
        """
    )

    params = {"p": PROVEEDOR_ID, "lc": LINEA_COD}

    with eng.connect() as conn:
        _print_rows("1) Línea destino", list(conn.execute(q_linea, params).fetchall()))
        _print_rows("2) Líneas anteriores con caso_id (fuentes)", list(conn.execute(q_fuentes, params).fetchall()))
        _print_rows("3) Preview UPDATE (qué se actualizaría)", list(conn.execute(q_preview, params).fetchall()))
        _print_rows("4) linea_referencia en esta línea", list(conn.execute(q_lr, params).fetchall()))

    with eng.begin() as conn:
        updated = list(conn.execute(q_update, params).fetchall())

    _print_rows("5) UPDATE con RETURNING (filas tocadas)", updated)
    print(f"\nTotal filas actualizadas: {len(updated)}", flush=True)

    with eng.connect() as conn:
        _print_rows("6) Línea destino (después)", list(conn.execute(q_linea, params).fetchall()))


if __name__ == "__main__":
    main()
