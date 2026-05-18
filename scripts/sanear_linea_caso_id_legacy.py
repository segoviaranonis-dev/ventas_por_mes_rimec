#!/usr/bin/env python3
"""
Saneamiento de linea.caso_id (legacy) → NULL en todo el pilar.

Ejecutar después de migrations/037 y 038 (o solo este script con --execute).

  python scripts/sanear_linea_caso_id_legacy.py           # preview
  python scripts/sanear_linea_caso_id_legacy.py --execute  # aplica UPDATE
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from decouple import UndefinedValueError, config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


def _db_url() -> str:
    try:
        url = config("DATABASE_URL")
        if url:
            return url
    except UndefinedValueError:
        pass
    p = ROOT / ".streamlit" / "secrets.toml"
    if p.is_file():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
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
    raise SystemExit("Definí DATABASE_URL o .streamlit/secrets.toml [postgres]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Poner linea.caso_id en NULL (legacy)")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Ejecutar UPDATE (sin esto solo muestra preview)",
    )
    args = parser.parse_args()

    engine = create_engine(_db_url())

    with engine.connect() as conn:
        n_antes = conn.execute(
            text("SELECT COUNT(*) FROM public.linea WHERE caso_id IS NOT NULL")
        ).scalar()
        total = conn.execute(text("SELECT COUNT(*) FROM public.linea")).scalar()

        print(f"=== linea.caso_id (legacy) ===")
        print(f"Total líneas:           {total}")
        print(f"Con caso_id poblado:    {n_antes}")

        if n_antes and n_antes > 0:
            muestra = conn.execute(
                text("""
                    SELECT l.id, l.proveedor_id, l.codigo_proveedor,
                           l.caso_id, cpb.nombre_caso
                    FROM public.linea l
                    LEFT JOIN public.caso_precio_biblioteca cpb ON cpb.id = l.caso_id
                    WHERE l.caso_id IS NOT NULL
                    ORDER BY l.proveedor_id, l.codigo_proveedor
                    LIMIT 15
                """)
            ).mappings().all()
            print("\nMuestra (máx. 15 filas):")
            for r in muestra:
                print(
                    f"  prov={r['proveedor_id']} línea={r['codigo_proveedor']} "
                    f"caso_id={r['caso_id']} ({r['nombre_caso']})"
                )

        if not args.execute:
            print("\n[DRY-RUN] No se modificó la BD. Usá --execute para aplicar.")
            return

        with engine.begin() as tx:
            res = tx.execute(
                text("UPDATE public.linea SET caso_id = NULL WHERE caso_id IS NOT NULL")
            )
            n_upd = res.rowcount

        n_despues = conn.execute(
            text("SELECT COUNT(*) FROM public.linea WHERE caso_id IS NOT NULL")
        ).scalar()
        print(f"\n[OK] Filas actualizadas: {n_upd}")
        print(f"Con caso_id después:    {n_despues} (debe ser 0)")


if __name__ == "__main__":
    main()
