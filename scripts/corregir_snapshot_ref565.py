"""
OT-COMBINACION-505-002 R1: Corregir snapshot_json — ref 565 material vacio.

Uso:
  python scripts/corregir_snapshot_ref565.py --traspaso-id 2 --dry-run
  python scripts/corregir_snapshot_ref565.py --traspaso-id 2 --yes
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2

from scripts.backfill_combinacion_desde_ppd import _db_url

MATERIAL_REF_565 = "LOC. CENTRUM/CACHAREL"


def main():
    dry_run = True
    traspaso_id = 2

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--yes':
            dry_run = False
            i += 1
        elif sys.argv[i] == '--dry-run':
            dry_run = True
            i += 1
        elif sys.argv[i] == '--traspaso-id' and i + 1 < len(sys.argv):
            traspaso_id = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return False

    print("=" * 80)
    print("CORREGIR snapshot_json: ref 565 material vacio -> LOC. CENTRUM/CACHAREL")
    print("MODE:", "DRY RUN" if dry_run else "EXECUTE")
    print("=" * 80)
    print()

    conn = psycopg2.connect(db_url)
    if not dry_run:
        conn.autocommit = False
    cur = conn.cursor()

    # Obtener snapshot actual
    cur.execute("""
        SELECT id, numero_registro, snapshot_json
        FROM traspaso
        WHERE id = %s
    """, (traspaso_id,))

    row = cur.fetchone()
    if not row:
        print(f"[ERROR] Traspaso id={traspaso_id} no encontrado")
        return False

    trp_id, trp_nro, snap_raw = row
    snapshot = json.loads(snap_raw) if isinstance(snap_raw, str) else snap_raw
    items = snapshot.get("items", [])

    print(f"[1] Traspaso: {trp_nro}")
    print(f"    Items en snapshot: {len(items)}")
    print()

    # Buscar item con ref 565
    modified = False
    for idx, item in enumerate(items):
        if str(item.get("referencia", "")) == "565":
            print(f"[2] Item {idx + 1}: ref 565 encontrado")
            print(f"    Material actual: '{item.get('material', '')}'")

            if not (item.get("material") or "").strip():
                item["material"] = MATERIAL_REF_565
                modified = True
                print(f"    Material corregido: '{MATERIAL_REF_565}'")
            else:
                print(f"    Material ya tiene valor, no se modifica")

            print()
            break

    if not modified:
        print("[INFO] No se encontro item con ref 565 y material vacio")
        return False

    # Actualizar snapshot_json
    if not dry_run:
        new_snapshot_json = json.dumps(snapshot, ensure_ascii=False)

        cur.execute("""
            UPDATE traspaso
            SET snapshot_json = %s
            WHERE id = %s
        """, (new_snapshot_json, traspaso_id))

        conn.commit()
        print("[OK] snapshot_json actualizado")
    else:
        print("[DRY RUN] Se actualizaria snapshot_json con:")
        print()
        print("Item ref 565 (corregido):")
        for item in items:
            if str(item.get("referencia", "")) == "565":
                print(f"  linea: {item.get('linea')}")
                print(f"  referencia: {item.get('referencia')}")
                print(f"  material: '{item.get('material')}'")
                print(f"  color: {item.get('color')}")
                print(f"  tallas: {item.get('tallas')}")
                break

    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
