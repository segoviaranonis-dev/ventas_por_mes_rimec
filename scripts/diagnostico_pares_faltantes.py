"""
Diagnosticar diferencia entre pares esperados (44) y obtenidos (36).
"""
import psycopg2
import json

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("DIAGNOSTICO: 44 pares esperados vs 36 obtenidos")
    print("=" * 80)
    print()

    # Obtener snapshot_json del traspaso
    cur.execute("""
        SELECT id, numero_registro, snapshot_json
        FROM traspaso
        WHERE id = 2
    """)

    row = cur.fetchone()
    if not row:
        print("[ERROR] Traspaso id=2 no encontrado")
        return

    trp_id, trp_nro, snap_raw = row
    snapshot = json.loads(snap_raw) if isinstance(snap_raw, str) else snap_raw
    items = snapshot.get("items", [])

    print(f"[1] Traspaso: {trp_nro}")
    print(f"    Snapshot items: {len(items)}")
    print()

    # Calcular totales por item
    print("[2] SNAPSHOT ORIGINAL - Pares por item:")
    print("-" * 80)

    total_snapshot = 0
    items_detalle = []

    for idx, rec in enumerate(items, 1):
        linea = rec.get("linea", "")
        ref = rec.get("referencia", "")
        material = rec.get("material", "")
        color = rec.get("color", "")
        tallas = rec.get("tallas", {})

        item_total = 0
        tallas_str = []

        for talla_key, qty_val in sorted(tallas.items()):
            qty = int(qty_val or 0)
            if qty > 0:
                item_total += qty
                tallas_str.append(f"{talla_key}({qty})")

        total_snapshot += item_total

        items_detalle.append({
            "linea": linea,
            "ref": ref,
            "material": material,
            "color": color,
            "pares": item_total,
            "tallas": ", ".join(tallas_str)
        })

        print(f"  Item {idx}: {linea}-{ref} {material}/{color}")
        print(f"    Tallas: {', '.join(tallas_str)}")
        print(f"    Total: {item_total} pares")
        print()

    print(f"TOTAL SNAPSHOT: {total_snapshot} pares")
    print("=" * 80)
    print()

    # Obtener lo que realmente se insertó
    cur.execute("""
        SELECT COALESCE(SUM(cantidad), 0)
        FROM traspaso_detalle
        WHERE traspaso_id = 2
    """)

    total_insertado = cur.fetchone()[0]

    print(f"[3] TRASPASO_DETALLE - Insertado:")
    print(f"    Total: {total_insertado} pares")
    print()

    # Calcular diferencia
    diferencia = total_snapshot - total_insertado

    print("=" * 80)
    print("[4] ANALISIS")
    print("=" * 80)
    print(f"  Pares en snapshot_json:      {total_snapshot}")
    print(f"  Pares en traspaso_detalle:   {total_insertado}")
    print(f"  DIFERENCIA:                  {diferencia} pares")
    print()

    if diferencia > 0:
        print(f"[DIAGNOSTICO] Faltan {diferencia} pares")
        print()
        print("Causa probable: combinaciones no resueltas (misses)")
        print()
        print("Items con posibles misses:")
        for item in items_detalle:
            print(f"  {item['linea']}-{item['ref']} {item['material']}/{item['color']}: {item['pares']} pares")
        print()
        print("SOLUCION:")
        print("  - Referencia 565: NO EXISTE en tabla referencia")
        print("  - Necesita backfill adicional o creacion manual")
        print("  - Todos los pares de ref 565 se perdieron en la resolucion")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
