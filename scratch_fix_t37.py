import json
import ast
from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

def _get_or_create_talla(conn, etiqueta, prov_id):
    if not etiqueta: return None
    row = conn.execute(text("SELECT id FROM talla WHERE talla_etiqueta = :t"), {"t": str(etiqueta)}).fetchone()
    if row: return row[0]
    import time
    return conn.execute(text("INSERT INTO talla (talla_etiqueta, sistema, orden_visual, proveedor_id, codigo_proveedor, talla_valor) VALUES (:t, 'NUMERICO', :ov, :p, :c, :tv) RETURNING id"), {"t": str(etiqueta), "ov": int(etiqueta) if str(etiqueta).isdigit() else 99, "p": prov_id, "c": time.time_ns() % 1000000000, "tv": int(etiqueta) if str(etiqueta).isdigit() else 0}).fetchone()[0]

with engine.begin() as conn:
    # Obtener traspasos con problema de t37
    trps = conn.execute(text("""
        SELECT t.id, t.documento_ref, t.estado
        FROM traspaso t
        WHERE t.documento_ref LIKE '%-%'
    """)).fetchall()

    for trp_id, doc_ref, estado in trps:
        # Check if it was purely t37
        td_count = conn.execute(text("SELECT COUNT(*) FROM traspaso_detalle WHERE traspaso_id = :id"), {"id": trp_id}).fetchone()[0]
        td_t37_count = conn.execute(text("""
            SELECT COUNT(*) FROM traspaso_detalle td 
            JOIN combinacion c ON c.id = td.combinacion_id 
            JOIN talla t ON t.id = c.talla_id 
            WHERE td.traspaso_id = :id AND t.talla_etiqueta = '37'
        """), {"id": trp_id}).fetchone()[0]
        
        if td_count > 0 and td_count == td_t37_count:
            # Re-procesar
            print(f"Reprocesando traspaso {trp_id} (doc {doc_ref})")
            
            # Obtener tallas correctas de factura_interna_detalle
            rows = conn.execute(text("""
                SELECT
                    ppd.linea, ppd.referencia, ppd.id_material, ppd.id_color,
                    fid.linea_snapshot, fid.pares
                FROM factura_interna_detalle fid
                JOIN factura_interna fi ON fi.id = fid.factura_id
                JOIN pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
                WHERE fi.nro_factura = :doc
            """), {"doc": doc_ref}).fetchall()
            
            items_tallas = []
            valid = True
            for r in rows:
                linea, ref, m_id, c_id, l_snap, pares = r
                tallas = {}
                if l_snap:
                    try:
                        snap = json.loads(l_snap) if isinstance(l_snap, str) else l_snap
                    except json.JSONDecodeError:
                        snap = ast.literal_eval(l_snap) if isinstance(l_snap, str) else l_snap
                    
                    gradas_fmt = snap.get("gradas_fmt", "") if isinstance(snap, dict) else ""
                    if gradas_fmt and "(" in gradas_fmt and ")" in gradas_fmt:
                        inicio_str, resto = gradas_fmt.split("(", 1)
                        cantidades_str, fin_str = resto.split(")", 1)
                        talla_inicio = int(inicio_str.strip())
                        cantidades = [int(x.strip()) for x in cantidades_str.split("-") if x.strip()]
                        for idx, qty in enumerate(cantidades):
                            talla_num = talla_inicio + idx
                            if qty > 0:
                                tallas[f"t{talla_num}"] = qty
                if not tallas:
                    valid = False
                    break
                items_tallas.append({
                    "linea": linea, "referencia": ref, "tallas": tallas
                })
                
            if not valid or not items_tallas:
                print("  No se pudo extraer gradas")
                continue
                
            # Eliminar actuales
            conn.execute(text("DELETE FROM movimiento_detalle WHERE movimiento_id IN (SELECT id FROM movimiento WHERE documento_ref = :doc)"), {"doc": doc_ref})
            conn.execute(text("DELETE FROM traspaso_detalle WHERE traspaso_id = :id"), {"id": trp_id})
            
            # Actualizar snapshot
            import time
            snap_json = conn.execute(text("SELECT snapshot_json FROM traspaso WHERE id = :id"), {"id": trp_id}).fetchone()[0]
            if isinstance(snap_json, str):
                try:
                    snap_dict = json.loads(snap_json)
                except:
                    snap_dict = ast.literal_eval(snap_json)
            else:
                snap_dict = snap_json
                
            for i, it in enumerate(snap_dict.get("items", [])):
                for new_it in items_tallas:
                    if it["linea"] == new_it["linea"] and it["referencia"] == new_it["referencia"]:
                        it["tallas"] = new_it["tallas"]
            
            conn.execute(text("UPDATE traspaso SET snapshot_json = :s WHERE id = :id"), {"s": json.dumps(snap_dict), "id": trp_id})
            
            # Insertar nuevos
            prov_row = conn.execute(text("SELECT id FROM proveedor_importacion LIMIT 1")).fetchone()
            prov_id = prov_row[0] if prov_row else 1
            
            total_ins = 0
            for item in snap_dict.get("items", []):
                l_id = conn.execute(text("SELECT id FROM linea WHERE codigo_proveedor = :l"), {"l": item["linea"]}).fetchone()[0]
                r_id = conn.execute(text("SELECT id FROM referencia WHERE codigo_proveedor = :r"), {"r": item["referencia"]}).fetchone()[0]
                
                m_id = conn.execute(text("SELECT id FROM material WHERE descripcion = :d"), {"d": item["material"]}).fetchone()
                if m_id: m_id = m_id[0]
                c_id = conn.execute(text("SELECT id FROM color WHERE nombre = :n"), {"n": item["color"]}).fetchone()
                if c_id: c_id = c_id[0]
                
                for t_key, qty in item.get("tallas", {}).items():
                    qty = int(qty or 0)
                    if qty <= 0: continue
                    t_val = t_key.replace("t", "")
                    t_id_db = _get_or_create_talla(conn, t_val, prov_id)
                    
                    comb = conn.execute(text("SELECT id FROM combinacion WHERE linea_id=:l AND referencia_id=:r AND material_id=:m AND color_id=:c AND talla_id=:t"), 
                        {"l": l_id, "r": r_id, "m": m_id, "c": c_id, "t": t_id_db}).fetchone()
                    if comb:
                        comb_id = comb[0]
                    else:
                        comb_id = conn.execute(text("INSERT INTO combinacion (linea_id, referencia_id, material_id, color_id, talla_id, activo_web) VALUES (:l, :r, :m, :c, :t, false) RETURNING id"), 
                            {"l": l_id, "r": r_id, "m": m_id, "c": c_id, "t": t_id_db}).fetchone()[0]
                            
                    conn.execute(text("INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad) VALUES (:trp, :cmb, :qty)"), 
                        {"trp": trp_id, "cmb": comb_id, "qty": qty})
                    total_ins += 1
            
            print(f"  Insertadas {total_ins} tallas.")
            
            if estado == "CONFIRMADO":
                mov = conn.execute(text("SELECT id FROM movimiento WHERE documento_ref = :doc"), {"doc": doc_ref}).fetchone()
                if mov:
                    mov_id = mov[0]
                    lines = conn.execute(text("SELECT combinacion_id, cantidad FROM traspaso_detalle WHERE traspaso_id = :trp"), {"trp": trp_id}).fetchall()
                    ins = 0
                    for c_id, qty in lines:
                        conn.execute(text("INSERT INTO movimiento_detalle (movimiento_id, combinacion_id, cantidad, signo) VALUES (:m, :c, :q, 1)"), {"m": mov_id, "c": c_id, "q": qty})
                        ins += 1
                    print(f"  Movimiento regenerado ({ins} lineas).")

print("Listo")
