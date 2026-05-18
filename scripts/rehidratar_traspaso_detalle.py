"""
OT-COMBINACION-505-001 Fase 2 R3: Rehidratar traspaso_detalle desde snapshot_json.

Usa _resolve_combinacion_id (misma ruta que crear_traspaso_por_factura) y agrupa
cantidades por combinacion_id para evitar UniqueViolation.

Uso:
  python scripts/rehidratar_traspaso_detalle.py --traspaso-id 2 --dry-run
  python scripts/rehidratar_traspaso_detalle.py --traspaso-id 2 --yes
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text as sqlt

from core.database import engine
from modules.compra_legal.logic import _resolve_combinacion_id


def _load_snapshot(conn, traspaso_id: int) -> dict | None:
    row = conn.execute(
        sqlt(
            "SELECT numero_registro, snapshot_json FROM traspaso WHERE id = :id"
        ),
        {"id": traspaso_id},
    ).fetchone()
    if not row:
        return None
    snap_raw = row[1]
    if isinstance(snap_raw, str):
        snap = json.loads(snap_raw)
    elif snap_raw is None:
        snap = {}
    else:
        snap = snap_raw
    snap["_numero_registro"] = row[0]
    return snap


def _build_comb_qty_map(conn, items: list) -> tuple[dict[int, int], list[str]]:
    comb_qty: dict[int, int] = {}
    misses: list[str] = []
    for rec in items:
        linea = rec.get("linea", "")
        ref = rec.get("referencia", "")
        material = rec.get("material", "")
        color = rec.get("color", "")
        for col, qty_val in (rec.get("tallas") or {}).items():
            qty = int(qty_val or 0)
            if qty <= 0:
                continue
            talla = str(col).replace("t", "")
            comb_id = _resolve_combinacion_id(
                conn, linea, ref, material, color, talla
            )
            if comb_id is None:
                misses.append(f"{linea}-{ref} {material}/{color} t{talla}")
                continue
            comb_qty[comb_id] = comb_qty.get(comb_id, 0) + qty
    return comb_qty, misses


def main() -> bool:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traspaso-id", type=int, required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dry_run = not args.yes
    trp_id = args.traspaso_id

    print("=" * 80)
    print(f"REHIDRATAR traspaso_detalle (id={trp_id})")
    print("MODE:", "DRY RUN" if dry_run else "EXECUTE")
    print("=" * 80)

    with engine.begin() as conn:
        snap = _load_snapshot(conn, trp_id)
        if snap is None:
            print(f"[ERROR] Traspaso {trp_id} no encontrado")
            return False

        items = snap.get("items") or []
        print(f"Traspaso: {snap.get('_numero_registro')} | snapshot items: {len(items)}")

        existing = conn.execute(
            sqlt(
                """
                SELECT COUNT(*), COALESCE(SUM(cantidad), 0)
                FROM traspaso_detalle WHERE traspaso_id = :id
                """
            ),
            {"id": trp_id},
        ).fetchone()
        print(f"traspaso_detalle actual: filas={existing[0]} pares={existing[1]}")

        comb_qty, misses = _build_comb_qty_map(conn, items)
        total_pares = sum(comb_qty.values())
        print(f"Resueltos: {len(comb_qty)} combinaciones, {total_pares} pares")
        if misses:
            print(f"Sin resolver ({len(misses)}):")
            for m in misses[:15]:
                print(f"  - {m}")

        if dry_run:
            if existing[0] > 0:
                print("[DRY] Se borrarían filas existentes y se insertarían las nuevas")
            return len(misses) == 0 and total_pares > 0

        conn.execute(
            sqlt("DELETE FROM traspaso_detalle WHERE traspaso_id = :id"),
            {"id": trp_id},
        )
        for comb_id, qty in comb_qty.items():
            conn.execute(
                sqlt(
                    """
                    INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
                    VALUES (:trp, :comb, :qty)
                    """
                ),
                {"trp": trp_id, "comb": comb_id, "qty": qty},
            )

    with engine.connect() as conn:
        row = conn.execute(
            sqlt(
                """
                SELECT COUNT(*), COALESCE(SUM(cantidad), 0)
                FROM traspaso_detalle WHERE traspaso_id = :id
                """
            ),
            {"id": trp_id},
        ).fetchone()
        print(f"\n[OK] traspaso_detalle: filas={row[0]} pares={row[1]}")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
