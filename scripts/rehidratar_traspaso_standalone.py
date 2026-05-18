"""
OT-COMBINACION-505-001 R3: Rehidratar traspaso_detalle standalone (no streamlit)
"""
import psycopg2
import sys
import json

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"


def _resolve_combinacion_id(cur, linea_cod, ref_cod, material, color, talla_str):
    """
    Replica logic from modules/compra_legal/logic.py::_resolve_combinacion_id
    Returns combinacion_id or None
    """
    # Get linea_id and proveedor_id
    cur.execute("""
        SELECT l.id, l.proveedor_id
        FROM linea l
        WHERE l.codigo_proveedor::text = %s
        LIMIT 1
    """, (str(linea_cod),))

    l_row = cur.fetchone()
    if not l_row:
        return None

    linea_id, prov_id = l_row

    # Get referencia_id
    cur.execute("""
        SELECT r.id
        FROM referencia r
        WHERE r.proveedor_id = %s
          AND r.linea_id = %s
          AND r.codigo_proveedor::text = %s
        LIMIT 1
    """, (prov_id, linea_id, str(ref_cod)))

    r_row = cur.fetchone()
    if not r_row:
        return None

    ref_id = r_row[0]

    # Get material_id by nombre
    if not material:
        return None

    cur.execute("""
        SELECT m.id
        FROM material m
        WHERE m.proveedor_id = %s
          AND m.descripcion = %s
        LIMIT 1
    """, (prov_id, str(material)))

    m_row = cur.fetchone()
    if not m_row:
        return None

    mat_id = m_row[0]

    # Get color_id by nombre
    if not color:
        return None

    cur.execute("""
        SELECT c.id
        FROM color c
        WHERE c.proveedor_id = %s
          AND c.nombre = %s
        LIMIT 1
    """, (prov_id, str(color)))

    c_row = cur.fetchone()
    if not c_row:
        return None

    col_id = c_row[0]

    # Get talla_id by talla_etiqueta
    cur.execute("""
        SELECT t.id
        FROM talla t
        WHERE t.talla_etiqueta = %s
        LIMIT 1
    """, (str(talla_str),))

    t_row = cur.fetchone()
    if not t_row:
        return None

    talla_id = t_row[0]

    # Get combinacion_id
    cur.execute("""
        SELECT c.id
        FROM combinacion c
        WHERE c.linea_id = %s
          AND c.referencia_id = %s
          AND c.material_id = %s
          AND c.color_id = %s
          AND c.talla_id = %s
        LIMIT 1
    """, (linea_id, ref_id, mat_id, col_id, talla_id))

    comb_row = cur.fetchone()
    return comb_row[0] if comb_row else None


def main():
    traspaso_id = None
    dry_run = True

    # Parse args
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--traspaso-id' and i + 1 < len(sys.argv):
            traspaso_id = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--yes':
            dry_run = False
            i += 1
        elif sys.argv[i] == '--dry-run':
            dry_run = True
            i += 1
        else:
            i += 1

    if not traspaso_id:
        print("[ERROR] Especificar --traspaso-id <id>")
        return False

    print("=" * 80)
    print(f"REHIDRATAR TRASPASO_DETALLE (traspaso_id={traspaso_id})")
    if dry_run:
        print("MODE: DRY RUN")
    else:
        print("MODE: EXECUTE")
    print("=" * 80)
    print()

    conn = psycopg2.connect(DATABASE_URL)
    if dry_run:
        conn.autocommit = True
    cur = conn.cursor()

    # Get traspaso snapshot
    print("[1] Loading snapshot")
    cur.execute("""
        SELECT numero_registro, snapshot_json
        FROM traspaso
        WHERE id = %s
    """, (traspaso_id,))

    t_row = cur.fetchone()
    if not t_row:
        print(f"[ERROR] Traspaso {traspaso_id} not found")
        return False

    t_nro, snap_json = t_row
    print(f"  Traspaso: {t_nro}")

    if isinstance(snap_json, str):
        snapshot = json.loads(snap_json)
    else:
        snapshot = snap_json

    items = snapshot.get("items", [])
    print(f"  Snapshot items: {len(items)}")
    print()

    # Build comb_qty_map (group by combinacion_id)
    print("[2] Resolving combinaciones + grouping")
    comb_qty_map = {}
    misses = []

    for rec in items:
        linea = rec.get("linea", "")
        ref = rec.get("referencia", "")
        material = rec.get("material", "")
        color = rec.get("color", "")
        tallas = rec.get("tallas", {})

        for talla_key, qty_val in tallas.items():
            qty = int(qty_val or 0)
            if qty <= 0:
                continue

            talla_num = talla_key.replace("t", "")

            comb_id = _resolve_combinacion_id(
                cur, linea, ref, material, color, talla_num
            )

            if comb_id is None:
                miss_key = f"{linea}-{ref}-{material}-{color}-t{talla_num}"
                if miss_key not in misses:
                    misses.append(miss_key)
                continue

            comb_qty_map[comb_id] = comb_qty_map.get(comb_id, 0) + qty

    print(f"  Combinaciones resolved: {len(comb_qty_map)}")
    print(f"  Misses (not found): {len(misses)}")

    if misses:
        print("  First 5 misses:")
        for m in misses[:5]:
            print(f"    - {m}")

    print()

    # Clear existing traspaso_detalle
    print("[3] Clearing existing traspaso_detalle")
    if not dry_run:
        cur.execute("""
            DELETE FROM traspaso_detalle
            WHERE traspaso_id = %s
        """, (traspaso_id,))
        print(f"  Deleted existing rows")
    else:
        cur.execute("""
            SELECT COUNT(*) FROM traspaso_detalle
            WHERE traspaso_id = %s
        """, (traspaso_id,))
        existing_count = cur.fetchone()[0]
        print(f"  [DRY] Would delete {existing_count} existing rows")

    print()

    # Insert new traspaso_detalle
    print("[4] Inserting traspaso_detalle")
    inserted = 0
    total_qty = 0

    for comb_id, qty in comb_qty_map.items():
        if not dry_run:
            cur.execute("""
                INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
                VALUES (%s, %s, %s)
            """, (traspaso_id, comb_id, qty))
            inserted += 1
        else:
            print(f"  [DRY] Would INSERT: comb_id={comb_id}, qty={qty}")
            inserted += 1

        total_qty += qty

    print(f"  Inserted rows: {inserted}")
    print(f"  Total pares: {total_qty}")
    print()

    # Stats
    print("=" * 80)
    print("STATS")
    print("=" * 80)
    print(f"  Snapshot items: {len(items)}")
    print(f"  Combinaciones resolved: {len(comb_qty_map)}")
    print(f"  Misses: {len(misses)}")
    print(f"  Traspaso_detalle rows: {inserted}")
    print(f"  Total pares: {total_qty}")

    if not dry_run:
        conn.commit()
        print("\n[OK] Transaction committed")
    else:
        print("\n[DRY RUN] No changes")

    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
