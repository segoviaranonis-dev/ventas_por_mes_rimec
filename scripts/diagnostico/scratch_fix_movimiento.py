from sqlalchemy import create_engine, text

db_url = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(db_url)

with engine.begin() as conn:
    # Obtener traspasos CONFIRMADOS
    trps = conn.execute(text("""
        SELECT t.id, t.numero_registro
        FROM traspaso t
        WHERE t.estado = 'CONFIRMADO'
    """)).fetchall()

    for trp_id, numero_registro in trps:
        mov = conn.execute(text("SELECT id FROM movimiento WHERE documento_ref = :doc"), {"doc": numero_registro}).fetchone()
        if mov:
            mov_id = mov[0]
            # Delete old
            conn.execute(text("DELETE FROM movimiento_detalle WHERE movimiento_id = :mid"), {"mid": mov_id})
            
            # Re-insert from updated traspaso_detalle
            lines = conn.execute(text("SELECT combinacion_id, cantidad FROM traspaso_detalle WHERE traspaso_id = :trp"), {"trp": trp_id}).fetchall()
            ins = 0
            for c_id, qty in lines:
                conn.execute(text("INSERT INTO movimiento_detalle (movimiento_id, combinacion_id, cantidad, signo) VALUES (:m, :c, :q, 1)"), {"m": mov_id, "c": c_id, "q": qty})
                ins += 1
            print(f"Movimiento {mov_id} (Traspaso {numero_registro}) regenerado ({ins} lineas).")

print("Listo")
