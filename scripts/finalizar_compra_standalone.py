"""
Standalone finalizar_compra(1) - no module dependencies
Replica logic from modules/compra_legal/logic.py usando solo psycopg2
"""
import psycopg2
import json
from datetime import date

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

ALM_TRANSITO = 3
ALM_WEB_BAZAR = 1

def _resolve_combinacion_id(cur, linea, referencia, material, color, talla):
    """
    Busca combinacion_id para (linea, ref, mat, col, talla)
    OT-2026-026: obtiene proveedor_id de linea
    """
    # Get proveedor_id from linea
    cur.execute("""
        SELECT l.id AS linea_id, l.proveedor_id
        FROM linea l
        WHERE l.codigo_proveedor::text = %s
        LIMIT 1
    """, (str(linea),))

    l_row = cur.fetchone()
    if not l_row:
        return None

    linea_id, prov_id = l_row

    # Get referencia_id
    cur.execute("""
        SELECT lr.id AS ref_id
        FROM linea_referencia lr
        WHERE lr.linea_id = %s
          AND lr.codigo_proveedor::text = %s
        LIMIT 1
    """, (linea_id, str(referencia)))

    r_row = cur.fetchone()
    if not r_row:
        return None

    ref_id = r_row[0]

    # Get material_id and color_id
    cur.execute("""
        SELECT m.id AS mat_id
        FROM material m
        WHERE m.codigo_proveedor::text = %s
          AND m.proveedor_id = %s
        LIMIT 1
    """, (str(material), prov_id))

    m_row = cur.fetchone()
    mat_id = m_row[0] if m_row else None

    cur.execute("""
        SELECT c.id AS col_id
        FROM color c
        WHERE c.codigo_proveedor::text = %s
          AND c.proveedor_id = %s
        LIMIT 1
    """, (str(color), prov_id))

    c_row = cur.fetchone()
    col_id = c_row[0] if c_row else None

    if not mat_id or not col_id:
        return None

    # Get combinacion_id
    cur.execute("""
        SELECT c.id
        FROM combinacion c
        WHERE c.linea_id = %s
          AND c.referencia_id = %s
          AND c.material_id = %s
          AND c.color_id = %s
          AND c.talla = %s
        LIMIT 1
    """, (linea_id, ref_id, mat_id, col_id, str(talla)))

    comb_row = cur.fetchone()
    return comb_row[0] if comb_row else None


def _get_next_traspaso_num(cur, anio):
    """Obtiene siguiente numero_registro para traspasos"""
    cur.execute("""
        SELECT COALESCE(MAX(CAST(SUBSTRING(numero_registro FROM '[0-9]+$') AS INTEGER)), 0) + 1
        FROM traspaso
        WHERE anio_fiscal = %s
    """, (anio,))

    row = cur.fetchone()
    num = row[0] if row else 1
    return f"T-{anio}-{num:04d}"


def crear_traspaso_por_factura(cur, id_pp, id_marca, numero_factura, items_tallas):
    """
    Crea traspaso BORRADOR con OT-TRASPASO-504-001 fixes
    """
    anio = date.today().year
    trp_n = _get_next_traspaso_num(cur, anio)

    snapshot = {
        "numero_factura": numero_factura,
        "id_pp": id_pp,
        "id_marca": id_marca,
        "items": items_tallas,
    }

    cur.execute("""
        INSERT INTO traspaso (
            numero_registro, anio_fiscal,
            almacen_origen_id, almacen_destino_id,
            estado, snapshot_json, documento_ref
        ) VALUES (
            %s, %s, %s, %s, 'BORRADOR', %s, %s
        )
        RETURNING id
    """, (trp_n, anio, ALM_TRANSITO, ALM_WEB_BAZAR,
          json.dumps(snapshot), numero_factura))

    trp_id = cur.fetchone()[0]

    # OT-TRASPASO-504-001: Agrupar cantidades por combinacion_id antes del INSERT
    comb_qty_map = {}

    for rec in items_tallas:
        for col, qty_val in rec.get("tallas", {}).items():
            qty = int(qty_val or 0)
            if qty <= 0:
                continue
            t = col.replace("t", "")
            comb_id = _resolve_combinacion_id(
                cur,
                rec.get("linea", ""),
                rec.get("referencia", ""),
                rec.get("material", ""),
                rec.get("color", ""),
                str(t)
            )
            if comb_id is None:
                continue
            comb_qty_map[comb_id] = comb_qty_map.get(comb_id, 0) + qty

    # Insertar una sola vez por combinacion_id
    for comb_id, total_qty in comb_qty_map.items():
        cur.execute("""
            INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
            VALUES (%s, %s, %s)
        """, (trp_id, comb_id, total_qty))

    return trp_id


def _crear_traspasos_para_pp(cur, id_pp, cl_id):
    """
    Crea traspasos para FAC-INTs del PP con OT-TRASPASO-504-001 R2 merge
    """
    creados = 0

    # Solo procesar factura_interna (skip venta_transito legacy)
    cur.execute("""
        SELECT DISTINCT fi.id, fi.nro_factura AS numero_factura,
               COALESCE(MIN(ppd.id_marca), 0) AS id_marca
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        JOIN pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
        WHERE fi.pp_id = %s
          AND fi.estado IN ('CONFIRMADA', 'RESERVADA')
          AND NOT EXISTS (
              SELECT 1 FROM traspaso t WHERE t.documento_ref = fi.nro_factura
          )
        GROUP BY fi.id, fi.nro_factura
    """, (id_pp,))

    facturas = cur.fetchall()

    for (fi_id, nro_factura, id_marca) in facturas:
        # Leer detalles FI
        cur.execute("""
            SELECT
                ppd.linea, ppd.referencia,
                ppd.id_material, ppd.id_color,
                ppd.descp_material, ppd.descp_color,
                ppd.grades_json,
                fid.linea_snapshot,
                fid.pares
            FROM factura_interna_detalle fid
            JOIN pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
            WHERE fid.factura_id = %s
        """, (fi_id,))

        rows = cur.fetchall()
        items_tallas = []

        for r in rows:
            linea, ref, id_mat, id_col, mat, col, grades_json, linea_snapshot, pares = r

            tallas = {}

            # Try grades_json
            if grades_json:
                try:
                    grades = json.loads(grades_json) if isinstance(grades_json, str) else grades_json
                    for talla_str, qty in (grades or {}).items():
                        talla_num = int(talla_str)
                        tallas[f"t{talla_num}"] = int(qty)
                except:
                    pass

            # Fallback to linea_snapshot
            if not tallas and linea_snapshot:
                try:
                    snapshot = json.loads(linea_snapshot) if isinstance(linea_snapshot, str) else linea_snapshot
                    gradas_fmt = snapshot.get("gradas_fmt", "") if snapshot else ""
                    if gradas_fmt and "(" in gradas_fmt and ")" in gradas_fmt:
                        inicio_str, resto = gradas_fmt.split("(", 1)
                        cantidades_str, fin_str = resto.split(")", 1)
                        talla_inicio = int(inicio_str.strip())
                        cantidades = [int(x.strip()) for x in cantidades_str.split("-") if x.strip()]
                        for idx, qty in enumerate(cantidades):
                            talla_num = talla_inicio + idx
                            if qty > 0:
                                tallas[f"t{talla_num}"] = qty
                except:
                    pass

            # Last fallback
            if not tallas and pares and pares > 0:
                tallas["t37"] = int(pares)

            if not tallas:
                continue

            items_tallas.append({
                "linea": linea or "",
                "referencia": ref or "",
                "id_material": int(id_mat or 0),
                "id_color": int(id_col or 0),
                "material": mat or "",
                "color": col or "",
                "tallas": tallas,
            })

        if not items_tallas:
            continue

        # OT-TRASPASO-504-001 R2: Merge items_tallas por SKU
        merged = {}
        for item in items_tallas:
            key = (item["linea"], item["referencia"], item["id_material"], item["id_color"])
            if key not in merged:
                merged[key] = {
                    "linea": item["linea"],
                    "referencia": item["referencia"],
                    "id_material": item["id_material"],
                    "id_color": item["id_color"],
                    "material": item["material"],
                    "color": item["color"],
                    "tallas": {}
                }
            for talla, qty in item["tallas"].items():
                merged[key]["tallas"][talla] = merged[key]["tallas"].get(talla, 0) + qty

        items_tallas_merged = list(merged.values())

        trp_id = crear_traspaso_por_factura(cur, id_pp, id_marca, nro_factura, items_tallas_merged)
        cur.execute("""
            UPDATE traspaso SET compra_legal_id = %s WHERE id = %s
        """, (cl_id, trp_id))
        creados += 1

    return creados


def finalizar_compra(id_cl):
    """
    Finaliza compra: crea traspasos + marca DISTRIBUIDA
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Get PPs
        cur.execute("""
            SELECT pedido_proveedor_id FROM compra_legal_pedido
            WHERE compra_legal_id = %s
        """, (id_cl,))

        pps = cur.fetchall()
        total_nuevos = 0

        for (id_pp,) in pps:
            total_nuevos += _crear_traspasos_para_pp(cur, id_pp, id_cl)

        # Update compra estado
        cur.execute("""
            UPDATE compra_legal SET estado = 'DISTRIBUIDA'
            WHERE id = %s
        """, (id_cl,))

        conn.commit()
        cur.close()
        conn.close()

        return True, f"Compra distribuida. {total_nuevos} traspaso(s) nuevo(s) creado(s)."

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return False, str(e)


if __name__ == "__main__":
    print("=" * 80)
    print("FINALIZAR COMPRA (standalone)")
    print("=" * 80)
    print()

    ok, msg = finalizar_compra(1)
    print(f"ok: {ok}")
    print(f"msg: {msg}")

    import sys
    sys.exit(0 if ok else 1)
