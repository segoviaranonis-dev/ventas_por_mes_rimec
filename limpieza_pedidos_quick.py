"""Limpieza rápida de pedidos web de prueba"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Contar pedidos antes
    cur.execute("SELECT COUNT(*) FROM pedido_venta_rimec")
    count_before = cur.fetchone()[0]
    print(f"[INFO] Pedidos antes: {count_before}")

    if count_before == 0:
        print("[OK] No hay pedidos para eliminar")
        cur.close()
        conn.close()
        return

    # 2. TRUNCATE CASCADE (borra todo y las FKs relacionadas)
    print("[1/1] Vaciando tablas con TRUNCATE CASCADE...")
    try:
        cur.execute("TRUNCATE TABLE pedido_venta_rimec CASCADE")
        conn.commit()
        print("[OK] Tablas vaciadas")
    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
        # Fallback: borrar manualmente en orden
        print("[FALLBACK] Borrando manualmente...")
        cur.execute("DELETE FROM factura_interna_detalle")
        print(f"  - Detalles: {cur.rowcount}")
        cur.execute("DELETE FROM factura_interna")
        print(f"  - Facturas: {cur.rowcount}")
        cur.execute("DELETE FROM pedido_venta_rimec")
        print(f"  - Pedidos: {cur.rowcount}")
        conn.commit()

    # 3. Verificar
    cur.execute("SELECT COUNT(*) FROM pedido_venta_rimec")
    count_after = cur.fetchone()[0]
    print(f"\n[VERIFICACION] Pedidos despues: {count_after}")

    if count_after == 0:
        print("[EXITO] Todos los pedidos fueron eliminados")
    else:
        print(f"[ADVERTENCIA] Quedan {count_after} pedidos")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
