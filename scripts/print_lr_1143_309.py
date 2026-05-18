#!/usr/bin/env python3
"""Imprime linea + referencia + linea_referencia para 1143-309 (proveedor 654)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from decouple import Config, RepositoryEnv  # noqa: E402
from decouple import UndefinedValueError, config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

P = 654
LC, RC = 1143, 309


def get_database_url() -> str:
    u = (os.environ.get("DATABASE_URL") or "").strip()
    if u:
        return u
    env_path = ROOT / ".env"
    if env_path.is_file():
        try:
            u2 = str(Config(RepositoryEnv(str(env_path)))("DATABASE_URL")).strip()
            if u2:
                return u2
        except UndefinedValueError:
            pass
    p = ROOT / ".streamlit" / "secrets.toml"
    if p.is_file():
        import tomllib

        with p.open("rb") as f:
            pg = tomllib.load(f).get("postgres")
        if isinstance(pg, dict) and all(k in pg for k in ("user", "password", "host", "port", "dbname")):
            return (
                f"postgresql://{pg['user']}:{quote_plus(str(pg['password']))}@"
                f"{pg['host']}:{pg['port']}/{pg['dbname']}?sslmode=require"
            )
    return str(config("DATABASE_URL")).strip()


def row_dict(r) -> dict:
    return {k: (None if v is None else str(v) if not isinstance(v, (int, float, bool)) else v) for k, v in r._mapping.items()}


def main() -> None:
    eng = create_engine(get_database_url(), pool_pre_ping=True)
    print(f"=== Búsqueda L+R proveedor_id={P} linea={LC} ref={RC} ===\n", flush=True)

    q_lr = text(
        """
        SELECT
            lr.*,
            l.codigo_proveedor AS linea_cod,
            l.id AS linea_pk,
            l.descripcion AS linea_desc,
            r.codigo_proveedor AS ref_cod,
            r.id AS ref_pk,
            r.linea_id AS ref_linea_id_fk
        FROM public.linea_referencia lr
        JOIN public.linea l
          ON l.id = lr.linea_id AND l.proveedor_id = lr.proveedor_id
        JOIN public.referencia r
          ON r.id = lr.referencia_id AND r.proveedor_id = lr.proveedor_id
        WHERE lr.proveedor_id = CAST(:p AS bigint)
          AND l.codigo_proveedor = CAST(:lc AS bigint)
          AND r.codigo_proveedor = CAST(:rc AS bigint)
        """
    )
    q_lr_loose = text(
        """
        SELECT lr.id, lr.proveedor_id, lr.linea_id, lr.referencia_id,
               l.codigo_proveedor AS lc, r.codigo_proveedor AS rc
        FROM public.linea_referencia lr
        JOIN public.linea l ON l.id = lr.linea_id
        JOIN public.referencia r ON r.id = lr.referencia_id
        WHERE l.codigo_proveedor = CAST(:lc AS bigint)
          AND r.codigo_proveedor = CAST(:rc AS bigint)
        """
    )
    q_linea = text(
        """
        SELECT * FROM public.linea
        WHERE proveedor_id = CAST(:p AS bigint) AND codigo_proveedor = CAST(:lc AS bigint)
        """
    )
    q_ref = text(
        """
        SELECT r.*, l.codigo_proveedor AS linea_cod
        FROM public.referencia r
        JOIN public.linea l ON l.id = r.linea_id AND l.proveedor_id = r.proveedor_id
        WHERE r.proveedor_id = CAST(:p AS bigint)
          AND l.codigo_proveedor = CAST(:lc AS bigint)
          AND r.codigo_proveedor = CAST(:rc AS bigint)
        """
    )
    q_lr_by_linea_id = text(
        """
        SELECT lr.*, r.codigo_proveedor AS ref_cod
        FROM public.linea_referencia lr
        JOIN public.referencia r ON r.id = lr.referencia_id
        WHERE lr.linea_id = 90007 AND lr.proveedor_id = CAST(:p AS bigint)
        ORDER BY r.codigo_proveedor
        """
    )

    params = {"p": P, "lc": LC, "rc": RC}

    with eng.connect() as conn:
        rows = conn.execute(q_lr, params).fetchall()
        print("--- linea_referencia (JOIN estricto proveedor + códigos) ---", flush=True)
        if not rows:
            print("(0 filas)\n", flush=True)
        for i, r in enumerate(rows, 1):
            print(f"[{i}] {json.dumps(row_dict(r), ensure_ascii=False, indent=2)}\n", flush=True)

        loose = conn.execute(q_lr_loose, {"lc": LC, "rc": RC}).fetchall()
        print("--- linea_referencia (solo códigos, cualquier proveedor) ---", flush=True)
        if not loose:
            print("(0 filas)\n", flush=True)
        for r in loose:
            print(json.dumps(row_dict(r), ensure_ascii=False, indent=2), flush=True)

        print("\n--- public.linea 1143 ---", flush=True)
        for r in conn.execute(q_linea, params).fetchall():
            print(json.dumps(row_dict(r), ensure_ascii=False, indent=2), flush=True)

        print("\n--- public.referencia 309 bajo linea 1143 ---", flush=True)
        for r in conn.execute(q_ref, params).fetchall():
            print(json.dumps(row_dict(r), ensure_ascii=False, indent=2), flush=True)

        print("\n--- Todos linea_referencia con linea_id=90007 ---", flush=True)
        for r in conn.execute(q_lr_by_linea_id, {"p": P}).fetchall():
            print(json.dumps(row_dict(r), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
