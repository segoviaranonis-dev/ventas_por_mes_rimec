"""
Debug: Por que _resolve_combinacion_id falla para ref 565.
"""
import psycopg2
import json

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("DEBUG: Resolucion referencia 565")
    print("=" * 80)
    print()

    # Obtener snapshot item 4
    cur.execute("""
        SELECT snapshot_json
        FROM traspaso
        WHERE id = 2
    """)

    snap_raw = cur.fetchone()[0]
    snapshot = json.loads(snap_raw) if isinstance(snap_raw, str) else snap_raw
    items = snapshot.get("items", [])

    # Encontrar item con ref 565
    item_565 = None
    for item in items:
        if str(item.get("referencia", "")) == "565":
            item_565 = item
            break

    if not item_565:
        print("[ERROR] No se encontro item con ref 565 en snapshot")
        return

    print("[1] SNAPSHOT Item 4 (ref 565):")
    print(f"    linea:      '{item_565.get('linea', '')}'")
    print(f"    referencia: '{item_565.get('referencia', '')}'")
    print(f"    material:   '{item_565.get('material', '')}'")
    print(f"    color:      '{item_565.get('color', '')}'")
    print(f"    tallas:     {item_565.get('tallas', {})}")
    print()

    linea_cod = item_565.get("linea", "")
    ref_cod = item_565.get("referencia", "")
    material = item_565.get("material", "")
    color = item_565.get("color", "")

    # Paso 1: Resolver linea
    print("[2] Paso 1: Resolver linea_id")
    cur.execute("""
        SELECT l.id, l.proveedor_id
        FROM linea l
        WHERE l.codigo_proveedor::text = %s
        LIMIT 1
    """, (str(linea_cod),))

    l_row = cur.fetchone()
    if l_row:
        linea_id, prov_id = l_row
        print(f"    + OK: linea_id={linea_id}, proveedor_id={prov_id}")
    else:
        print(f"    - FAIL: Linea '{linea_cod}' no encontrada")
        return

    print()

    # Paso 2: Resolver referencia_id
    print("[3] Paso 2: Resolver referencia_id")
    cur.execute("""
        SELECT r.id
        FROM referencia r
        WHERE r.proveedor_id = %s
          AND r.linea_id = %s
          AND r.codigo_proveedor::text = %s
        LIMIT 1
    """, (prov_id, linea_id, str(ref_cod)))

    r_row = cur.fetchone()
    if r_row:
        ref_id = r_row[0]
        print(f"    + OK: referencia_id={ref_id}")
    else:
        print(f"    - FAIL: Referencia '{ref_cod}' no encontrada para linea_id={linea_id}, prov={prov_id}")
        return

    print()

    # Paso 3: Resolver material_id
    print("[4] Paso 3: Resolver material_id")
    print(f"    Buscando material.descripcion = '{material}'")

    if not material:
        print(f"    - FAIL: material vacio en snapshot")
        print(f"    CAUSA RAIZ: _resolve_combinacion_id retorna None si material vacio")
        print()
        print("[SOLUCION]")
        print("  El snapshot tiene material='' (vacio) para ref 565")
        print("  _resolve_combinacion_id requiere material no-vacio")
        print()
        print("  OPCIONES:")
        print("    1. Corregir snapshot_json con material correcto")
        print("    2. Consultar PPD para obtener material original")
        print("    3. Crear combinaciones manualmente si se conoce el material")
        return

    cur.execute("""
        SELECT m.id
        FROM material m
        WHERE m.proveedor_id = %s
          AND m.descripcion = %s
        LIMIT 1
    """, (prov_id, str(material)))

    m_row = cur.fetchone()
    if m_row:
        mat_id = m_row[0]
        print(f"    + OK: material_id={mat_id}")
    else:
        print(f"    - FAIL: Material '{material}' no encontrado para prov={prov_id}")

        # Ver materiales disponibles
        cur.execute("""
            SELECT id, descripcion
            FROM material
            WHERE proveedor_id = %s
            LIMIT 10
        """, (prov_id,))

        mats = cur.fetchall()
        print(f"    Materiales disponibles:")
        for m_id, m_desc in mats:
            print(f"      {m_id}: {m_desc}")
        return

    print()

    # Paso 4: Resolver color_id
    print("[5] Paso 4: Resolver color_id")
    print(f"    Buscando color.nombre = '{color}'")

    if not color:
        print(f"    - FAIL: color vacio en snapshot")
        return

    cur.execute("""
        SELECT c.id
        FROM color c
        WHERE c.proveedor_id = %s
          AND c.nombre = %s
        LIMIT 1
    """, (prov_id, str(color)))

    c_row = cur.fetchone()
    if c_row:
        col_id = c_row[0]
        print(f"    + OK: color_id={col_id}")
    else:
        print(f"    - FAIL: Color '{color}' no encontrado para prov={prov_id}")

        # Ver colores disponibles
        cur.execute("""
            SELECT id, nombre
            FROM color
            WHERE proveedor_id = %s
            LIMIT 20
        """, (prov_id,))

        cols = cur.fetchall()
        print(f"    Colores disponibles:")
        for c_id, c_nom in cols[:10]:
            print(f"      {c_id}: {c_nom}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
