import json
import ast
import time
import ast
from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

def _get_or_create_material(conn, descripcion, prov_id):
    if not descripcion: return None
    row = conn.execute(text("SELECT id FROM material WHERE descripcion = :d"), {"d": descripcion}).fetchone()
    if row: return row[0]
    return conn.execute(text("INSERT INTO material (descripcion, proveedor_id, codigo_proveedor) VALUES (:d, :p, 'SYS') RETURNING id"), {"d": descripcion, "p": prov_id}).fetchone()[0]

def _get_or_create_color(conn, nombre, prov_id):
    if not nombre: return None
    # Buscar color existente por nombre
    row = conn.execute(text("SELECT id FROM color WHERE nombre = :n"), {"n": nombre}).fetchone()
    if row: return row[0]

    # Buscar codigo_proveedor correcto desde pedido_proveedor_detalle (columna color_code)
    ppd_row = conn.execute(text(
        "SELECT DISTINCT color_code::bigint FROM pedido_proveedor_detalle WHERE descp_color = :n AND color_code IS NOT NULL LIMIT 1"
    ), {"n": nombre}).fetchone()
    codigo_prov = ppd_row[0] if ppd_row else 0  # Usar 0 como placeholder si no existe

    # Crear nuevo color con codigo correcto
    return conn.execute(text(
        "INSERT INTO color (nombre, codigo_proveedor, proveedor_id) VALUES (:n, :c, :p) RETURNING id"
    ), {"n": nombre, "c": codigo_prov, "p": prov_id}).fetchone()[0]

def _get_or_create_talla(conn, etiqueta, prov_id):
    if not etiqueta: return None
    row = conn.execute(text("SELECT id FROM talla WHERE talla_etiqueta = :t"), {"t": str(etiqueta)}).fetchone()
    if row: return row[0]
    return conn.execute(text("INSERT INTO talla (talla_etiqueta, sistema, orden_visual, proveedor_id, codigo_proveedor, talla_valor) VALUES (:t, 'BR', :ov, :p, 'SYS', 'SYS') RETURNING id"), {"t": str(etiqueta), "ov": int(etiqueta) if str(etiqueta).isdigit() else 99, "p": prov_id}).fetchone()[0]

with engine.begin() as conn:
    prov_row = conn.execute(text("SELECT id FROM proveedor_importacion LIMIT 1")).fetchone()
    prov_id = prov_row[0] if prov_row else 1
    trps = conn.execute(text("SELECT id, estado, snapshot_json, numero_registro FROM traspaso WHERE NOT EXISTS (SELECT 1 FROM traspaso_detalle td WHERE td.traspaso_id = traspaso.id)")).fetchall()
    
    for t_id, estado, snap_raw, numero in trps:
        print(f"Fixing {numero} (ID: {t_id}) - Estado: {estado}")
        if not snap_raw: continue
        try:
            if isinstance(snap_raw, str):
                try:
                    snap = json.loads(snap_raw)
                except:
                    snap = ast.literal_eval(snap_raw)
            else:
                snap = snap_raw
        except:
            continue
            
        items = snap.get("items", [])
        total_inserted = 0
        for item in items:
            l_cod = item.get("linea")
            r_cod = item.get("referencia")
            m_des = item.get("material")
            c_nom = item.get("color")
            tallas = item.get("tallas", {})
            
            l_id = conn.execute(text("SELECT id FROM linea WHERE codigo_proveedor = :l"), {"l": l_cod}).fetchone()
            r_id = conn.execute(text("SELECT id FROM referencia WHERE codigo_proveedor = :r"), {"r": r_cod}).fetchone()
            if not l_id or not r_id:
                print(f"  Line/Ref missing: {l_cod} / {r_cod}")
                continue
            l_id = l_id[0]
            r_id = r_id[0]
            
            m_id = _get_or_create_material(conn, m_des, prov_id)
            c_id = _get_or_create_color(conn, c_nom, prov_id)
            
            for t_key, qty in tallas.items():
                qty = int(qty or 0)
                if qty <= 0: continue
                t_val = t_key.replace("t", "")
                t_id_db = _get_or_create_talla(conn, t_val, prov_id)
                
                # Get or create combinacion
                comb = conn.execute(text("SELECT id FROM combinacion WHERE linea_id=:l AND referencia_id=:r AND material_id=:m AND color_id=:c AND talla_id=:t"), 
                    {"l": l_id, "r": r_id, "m": m_id, "c": c_id, "t": t_id_db}).fetchone()
                
                if comb:
                    comb_id = comb[0]
                else:
                    comb_id = conn.execute(text("INSERT INTO combinacion (linea_id, referencia_id, material_id, color_id, talla_id, activo_web) VALUES (:l, :r, :m, :c, :t, false) RETURNING id"), 
                        {"l": l_id, "r": r_id, "m": m_id, "c": c_id, "t": t_id_db}).fetchone()[0]
                
                # Insert traspaso_detalle
                conn.execute(text("INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad) VALUES (:trp, :cmb, :qty)"), 
                    {"trp": t_id, "cmb": comb_id, "qty": qty})
                total_inserted += 1
                
        print(f"  Inserted {total_inserted} lines into traspaso_detalle")
        
        # If CONFIRMADO, insert into movimiento_detalle
        if estado == "CONFIRMADO":
            # Check if there's a movimiento for this traspaso
            mov = conn.execute(text("SELECT id FROM movimiento WHERE documento_ref = :doc"), {"doc": numero}).fetchone()
            if not mov:
                mov_id = conn.execute(text("INSERT INTO movimiento (tipo, fecha, almacen_origen_id, almacen_destino_id, documento_ref, estado) VALUES ('INGRESO_COMPRA', CURRENT_DATE, 3, 1, :doc, 'CONFIRMADO') RETURNING id"), {"doc": numero}).fetchone()[0]
            else:
                mov_id = mov[0]
                
            # Copy details
            lines = conn.execute(text("SELECT combinacion_id, cantidad FROM traspaso_detalle WHERE traspaso_id = :trp"), {"trp": t_id}).fetchall()
            ins = 0
            for c_id, qty in lines:
                conn.execute(text("INSERT INTO movimiento_detalle (movimiento_id, combinacion_id, cantidad, signo) VALUES (:m, :c, :q, 1)"), {"m": mov_id, "c": c_id, "q": qty})
                ins += 1
            print(f"  Inserted {ins} lines into movimiento_detalle")
