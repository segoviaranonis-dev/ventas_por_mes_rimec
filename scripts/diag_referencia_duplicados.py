"""
Diagnóstico local: duplicados en referencia y FKs entrantes.
Uso (desde raíz del repo):
  python scripts/diag_referencia_duplicados.py

Lee .streamlit/secrets.toml [postgres] — no imprime credenciales.
También escribe la salida en `_diag_referencia_salida.txt` en la raíz del repo.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tomllib  # noqa: E402
from urllib.parse import quote_plus  # noqa: E402

from sqlalchemy import create_engine, text  # noqa: E402


def main() -> None:
    out_path = ROOT / "_diag_referencia_salida.txt"
    lines: list[str] = []

    def emit(msg: str) -> None:
        lines.append(msg)
        print(msg)

    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    with open(secrets_path, "rb") as f:
        cfg = tomllib.load(f)
    pg = cfg["postgres"]
    user = quote_plus(str(pg["user"]))
    pw = quote_plus(str(pg["password"]))
    url = (
        f"postgresql+psycopg2://{user}:{pw}@{pg['host']}:{pg['port']}/"
        f"{pg['dbname']}?sslmode=require"
    )
    eng = create_engine(url, pool_pre_ping=True)

    with eng.connect() as c:
        emit("=== Constraints en referencia (pg_constraint) ===")
        for row in c.execute(
            text(
                """
                SELECT conname, contype, pg_get_constraintdef(c.oid) AS def
                FROM pg_constraint c
                WHERE c.conrelid = 'public.referencia'::regclass
                ORDER BY conname
                """
            )
        ):
            emit(f"  {row[0]} ({row[1]}): {row[2][:160]}")

        emit("\n=== Grupos duplicados (proveedor_id, codigo_proveedor) ===")
        dup = c.execute(
            text(
                """
                SELECT proveedor_id, codigo_proveedor, COUNT(*) AS n,
                       MIN(linea_id) AS min_linea, MAX(linea_id) AS max_linea,
                       array_agg(id ORDER BY id) AS ids,
                       MAX(id) AS id_mas_reciente
                FROM referencia
                GROUP BY proveedor_id, codigo_proveedor
                HAVING COUNT(*) > 1
                ORDER BY n DESC, proveedor_id, codigo_proveedor
                """
            )
        ).mappings().all()
        emit(f"Total grupos: {len(dup)}")
        distintas = sum(1 for r in dup if r["min_linea"] != r["max_linea"])
        emit(f"Grupos con distinta linea_id (NO fusionar por codigo solo): {distintas}")
        for row in dup[:80]:
            same_linea = row["min_linea"] == row["max_linea"]
            flag = "OK_MERGE_LINEA_IGUAL" if same_linea else "REVISAR_lineas_distintas"
            emit(f"  {flag} | {dict(row)}")

        emit("\n=== Duplicados triple (proveedor_id, linea_id, codigo_proveedor) ===")
        trip = c.execute(
            text(
                """
                SELECT proveedor_id, linea_id, codigo_proveedor, COUNT(*) AS n,
                       array_agg(id ORDER BY id) AS ids
                FROM referencia
                GROUP BY proveedor_id, linea_id, codigo_proveedor
                HAVING COUNT(*) > 1
                """
            )
        ).mappings().all()
        emit(f"Total grupos triple duplicados: {len(trip)}")
        for row in trip[:40]:
            emit(f"  {dict(row)}")

        emit("\n=== FKs (information_schema) hacia public.referencia ===")
        for row in c.execute(
            text(
                """
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.table_schema = 'public'
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND ccu.table_name = 'referencia'
                ORDER BY tc.table_name, kcu.column_name
                """
            )
        ):
            emit(f"  {row[0]}.{row[1]}")

    eng.dispose()
    emit("\n=== Fin diagnóstico ===")
    out_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
