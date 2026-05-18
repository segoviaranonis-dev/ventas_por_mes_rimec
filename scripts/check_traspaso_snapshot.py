"""Check traspaso snapshot and detalle"""
import psycopg2
import json

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get traspaso
cur.execute("SELECT id, numero_registro, snapshot_json, documento_ref FROM traspaso WHERE id = 2")
row = cur.fetchone()

if row:
    t_id, t_nro, snap_json, doc_ref = row
    print(f"Traspaso: {t_nro} (id={t_id})")
    print(f"  documento_ref: {doc_ref}")
    print(f"  snapshot_json type: {type(snap_json)}")

    if isinstance(snap_json, str):
        snap = json.loads(snap_json)
    else:
        snap = snap_json

    print(f"\nSnapshot:")
    print(json.dumps(snap, indent=2))

    # Check items count
    items = snap.get("items", [])
    print(f"\nTotal items: {len(items)}")
    if items:
        print("Items preview:")
        for i, item in enumerate(items[:3]):
            print(f"  [{i}] {item.get('linea')}-{item.get('referencia')}: tallas={list(item.get('tallas', {}).keys())}")

# Check traspaso_detalle
cur.execute("SELECT COUNT(*), SUM(cantidad) FROM traspaso_detalle WHERE traspaso_id = 2")
row = cur.fetchone()
print(f"\nTraspaso_detalle:")
print(f"  Rows: {row[0]}")
print(f"  Total qty: {row[1]}")

# If 0 rows, check why combinacion_id resolution failed
if row[0] == 0:
    print("\n[!!] 0 rows in traspaso_detalle - combinacion_id resolution may have failed")
    print("Checking if combinaciones exist...")

    # Try to resolve one SKU manually
    cur.execute("""
        SELECT ppd.linea, ppd.referencia, ppd.id_material, ppd.id_color
        FROM factura_interna_detalle fid
        JOIN pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
        WHERE fid.factura_id = (
            SELECT fi.id FROM factura_interna fi WHERE fi.nro_factura = %s LIMIT 1
        )
        LIMIT 1
    """, (doc_ref,))

    ppd_row = cur.fetchone()
    if ppd_row:
        linea, ref, mat, col = ppd_row
        print(f"  Sample SKU: {linea}-{ref}-{mat}-{col}")

        # Check if combinacion exists for this SKU
        cur.execute("""
            SELECT c.id, c.talla
            FROM combinacion c
            JOIN linea l ON l.id = c.linea_id
            JOIN linea_referencia lr ON lr.id = c.referencia_id
            WHERE l.codigo_proveedor::text = %s
              AND lr.codigo_proveedor::text = %s
              AND c.material_id = %s
              AND c.color_id = %s
            LIMIT 5
        """, (str(linea), str(ref), mat, col))

        comb_rows = cur.fetchall()
        if comb_rows:
            print(f"  Found {len(comb_rows)} combinaciones for this SKU:")
            for cr in comb_rows:
                print(f"    comb_id={cr[0]}, talla={cr[1]}")
        else:
            print("  [!!] No combinaciones found for this SKU")
            print("  This explains why traspaso_detalle is empty")

conn.close()
