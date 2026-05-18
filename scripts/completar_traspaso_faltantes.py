"""
Inserta en traspaso_detalle los pares del snapshot que no resolvieron
(creado referencia/material/color/combinacion si faltan).

Uso:
  python scripts/completar_traspaso_faltantes.py --traspaso-id 2 --dry-run
  python scripts/completar_traspaso_faltantes.py --traspaso-id 2 --yes
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2

from scripts.backfill_combinacion_desde_ppd import (
    get_or_create_color,
    get_or_create_material,
    get_or_create_referencia,
    get_or_create_talla,
    get_or_insert_combinacion,
    _db_url,
    _normalize_codigo,
    _synthetic_codigo,
    _SYNTH_COLOR_BASE,
)


def _resolve_or_create(
    cur, proveedor_id: int, linea_id: int, linea_cod, ref_cod, material, color, talla_etiqueta
) -> int | None:
    ref_id = get_or_create_referencia(cur, proveedor_id, linea_id, ref_cod)
    mat_id = get_or_create_material(cur, proveedor_id, None, material or "")
    col_id = get_or_create_color(cur, proveedor_id, None, color or "")
    if not mat_id or not col_id:
        if color and _normalize_codigo(None) is None:
            cod = _synthetic_codigo(proveedor_id, color, _SYNTH_COLOR_BASE)
            col_id = get_or_create_color(cur, proveedor_id, cod, color)
    talla_id = get_or_create_talla(cur, str(talla_etiqueta))
    if not all([ref_id, mat_id, col_id, talla_id]):
        return None
    return get_or_insert_combinacion(cur, linea_id, ref_id, mat_id, col_id, talla_id)


def main() -> bool:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traspaso-id", type=int, required=True)
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    dry_run = not args.yes

    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return False

    conn = psycopg2.connect(db_url)
    conn.autocommit = dry_run
    cur = conn.cursor()

    cur.execute(
        "SELECT numero_registro, snapshot_json FROM traspaso WHERE id = %s",
        (args.traspaso_id,),
    )
    row = cur.fetchone()
    if not row:
        print("Traspaso no encontrado")
        return False

    t_nro, snap_raw = row
    snap = json.loads(snap_raw) if isinstance(snap_raw, str) else (snap_raw or {})
    items = snap.get("items") or []

    print("=" * 72)
    print(f"COMPLETAR FALTANTES {t_nro} id={args.traspaso_id} ({'DRY' if dry_run else 'EXEC'})")
    print("=" * 72)

    inserted_pares = 0
    updated_pares = 0
    created_comb = 0

    for rec in items:
        linea_cod = rec.get("linea", "")
        cur.execute(
            """
            SELECT l.id, l.proveedor_id FROM linea l
            WHERE l.codigo_proveedor::text = %s LIMIT 1
            """,
            (str(linea_cod),),
        )
        l_row = cur.fetchone()
        if not l_row:
            print(f"[SKIP] linea {linea_cod} no encontrada")
            continue
        linea_id, proveedor_id = int(l_row[0]), int(l_row[1])

        ref_cod = rec.get("referencia", "")
        material = rec.get("material", "")
        color = rec.get("color", "")

        for talla_key, qty_val in (rec.get("tallas") or {}).items():
            qty = int(qty_val or 0)
            if qty <= 0:
                continue
            etiqueta = str(talla_key).replace("t", "")

            if dry_run:
                cur.execute(
                    """
                    SELECT 1 FROM referencia r
                    WHERE r.linea_id = %s AND r.codigo_proveedor::text = %s
                    """,
                    (linea_id, str(ref_cod)),
                )
                if not cur.fetchone():
                    print(
                        f"[DRY] Crearía ref {linea_cod}-{ref_cod} + comb "
                        f"{material}/{color} t{etiqueta} qty={qty}"
                    )
                    inserted_pares += qty
                continue

            comb_id = _resolve_or_create(
                cur,
                proveedor_id,
                linea_id,
                linea_cod,
                ref_cod,
                material,
                color,
                etiqueta,
            )
            if comb_id is None:
                print(f"[FAIL] {linea_cod}-{ref_cod} t{etiqueta}")
                continue

            cur.execute(
                """
                SELECT id, cantidad FROM traspaso_detalle
                WHERE traspaso_id = %s AND combinacion_id = %s
                """,
                (args.traspaso_id, comb_id),
            )
            existing = cur.fetchone()
            if existing:
                td_id, old_qty = existing
                if int(old_qty) < qty:
                    cur.execute(
                        "UPDATE traspaso_detalle SET cantidad = %s WHERE id = %s",
                        (qty, td_id),
                    )
                    updated_pares += qty - int(old_qty)
            else:
                cur.execute(
                    """
                    INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
                    VALUES (%s, %s, %s)
                    """,
                    (args.traspaso_id, comb_id, qty),
                )
                inserted_pares += qty
                created_comb += 1

    if not dry_run:
        conn.commit()

    cur.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(cantidad), 0)
        FROM traspaso_detalle WHERE traspaso_id = %s
        """,
        (args.traspaso_id,),
    )
    rows, total = cur.fetchone()
    print()
    print(f"Pares insertados/ajustados: +{inserted_pares} (updates +{updated_pares})")
    print(f"Combinaciones nuevas en detalle: {created_comb}")
    print(f"TOTAL traspaso_detalle ahora: {total} pares / {rows} filas")

    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
