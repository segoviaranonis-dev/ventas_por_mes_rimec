"""
Compara pares: snapshot_json vs traspaso_detalle vs factura_interna_detalle.
Explica brechas tipo 44 esperados vs 36 en BD.

Uso:
  python scripts/diagnosticar_brecha_traspaso.py --traspaso-id 2
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2


def _db_url() -> str | None:
    from urllib.parse import quote_plus

    try:
        from decouple import config

        u = config("DATABASE_URL")
        if u:
            return u.replace("postgresql+psycopg2://", "postgresql://")
    except Exception:
        pass
    p = ROOT / ".streamlit" / "secrets.toml"
    if p.is_file():
        try:
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
                        f"postgresql://{quote_plus(user)}:{quote_plus(pwd)}"
                        f"@{host}:{port}/{db}"
                    )
        except Exception:
            pass
    return None


def _sum_snapshot_items(items: list) -> tuple[int, list[dict]]:
    rows = []
    total = 0
    for i, rec in enumerate(items):
        sub = 0
        tallas = rec.get("tallas") or {}
        for k, v in tallas.items():
            q = int(v or 0)
            if q > 0:
                sub += q
        total += sub
        rows.append(
            {
                "idx": i,
                "linea": rec.get("linea"),
                "referencia": rec.get("referencia"),
                "material": rec.get("material"),
                "color": rec.get("color"),
                "pares": sub,
                "tallas": tallas,
            }
        )
    return total, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traspaso-id", type=int, required=True)
    args = parser.parse_args()

    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT numero_registro, documento_ref, snapshot_json
        FROM traspaso WHERE id = %s
        """,
        (args.traspaso_id,),
    )
    row = cur.fetchone()
    if not row:
        print("Traspaso no encontrado")
        sys.exit(1)

    t_nro, doc_ref, snap_raw = row
    snap = json.loads(snap_raw) if isinstance(snap_raw, str) else (snap_raw or {})
    items = snap.get("items") or []

    snap_total, per_item = _sum_snapshot_items(items)

    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(cantidad), 0)
        FROM traspaso_detalle WHERE traspaso_id = %s
        """,
        (args.traspaso_id,),
    )
    td_rows, td_pares = cur.fetchone()

    print("=" * 72)
    print(f"BRECHA TRASPASO {t_nro} (id={args.traspaso_id}) doc={doc_ref}")
    print("=" * 72)
    print(f"Snapshot (items):     {snap_total} pares en {len(items)} moléculas")
    print(f"traspaso_detalle:    {td_pares} pares en {td_rows} filas")
    print(f"Diferencia:           {snap_total - int(td_pares or 0)} pares faltantes")
    print()

    print("Por ítem en snapshot:")
    for it in per_item:
        print(
            f"  [{it['idx']}] {it['linea']}-{it['referencia']} "
            f"{it['material']}/{it['color']} -> {it['pares']} pares"
        )
    print()

  # FI total
    cur.execute(
        """
        SELECT COALESCE(SUM(fid.pares), 0)
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        WHERE fi.nro_factura = %s OR fi.numero_factura = %s
        """,
        (doc_ref, doc_ref),
    )
    fi_pares = cur.fetchone()[0]
    print(f"factura_interna_detalle (doc {doc_ref}): {fi_pares} pares (sum fid.pares)")

    # referencia 565?
    cur.execute(
        """
        SELECT COUNT(*) FROM referencia r
        JOIN linea l ON l.id = r.linea_id
        WHERE l.codigo_proveedor::text = '4202'
          AND r.codigo_proveedor::text = '565'
        """
    )
    ref565 = cur.fetchone()[0]
    print(f"referencia 4202-565 en BD: {'SÍ' if ref565 else 'NO'}")
    print()

    if snap_total > int(td_pares or 0):
        print("CAUSA PROBABLE:")
        for it in per_item:
            if it["pares"] <= 0:
                continue
            ref = str(it["referencia"])
            cur.execute(
                """
                SELECT r.id FROM referencia r
                JOIN linea l ON l.id = r.linea_id
                WHERE l.codigo_proveedor::text = %s
                  AND r.codigo_proveedor::text = %s
                LIMIT 1
                """,
                (str(it["linea"]), ref),
            )
            if not cur.fetchone():
                print(
                    f"  - Ítem [{it['idx']}] ref {ref}: NO existe en tabla referencia "
                    f"-> rehidratación omitió {it['pares']} pares"
                )

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
