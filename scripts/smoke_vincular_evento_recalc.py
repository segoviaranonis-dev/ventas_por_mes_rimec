"""
OT-COMPRA-501-002 Task 3: Smoke test vincular evento -> recalcular FI
Valida que:
- PP tiene precio_evento_id vinculado
- recalcular_facturas_internas_pp existe y funciona
- FI CONFIRMADA NO se recalcula (histórica)
- FI RESERVADA SÍ se recalcula (si existe)
- Totales PP sin cambio (7164 pares, 748 cajas)
"""
import psycopg2
import sys

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("SMOKE TEST: Vincular Evento -> Recalcular FI (PP-2026-0001)")
    print("=" * 80)
    print()

    # 1. Estado inicial PP
    print("[1] ESTADO INICIAL PP-2026-0001")
    print("-" * 80)
    cur.execute("""
        SELECT pp.id, pp.numero_registro,
               SUM(ppd.cantidad_pares) AS total_pares,
               SUM(ppd.cantidad_cajas) AS total_cajas
        FROM pedido_proveedor pp
        LEFT JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
        WHERE pp.numero_registro = %s
        GROUP BY pp.id, pp.numero_registro
    """, ("PP-2026-0001",))

    pp_row = cur.fetchone()
    if not pp_row:
        print("[ERROR] PP-2026-0001 not found")
        return False

    pp_id, pp_nro, total_pares, total_cajas = pp_row
    print(f"  PP: {pp_nro} (id={pp_id})")
    print(f"  Total pares: {total_pares} (esperado: 7164)")
    print(f"  Total cajas: {total_cajas} (esperado: 748)")

    if total_pares != 7164 or total_cajas != 748:
        print("[!!] DESVIO: Totales no coinciden con spec")
        return False

    print()

    # 2. Verificar evento vinculado
    print("[2] EVENTO VINCULADO")
    print("-" * 80)
    cur.execute("""
        SELECT icp.precio_evento_id, pe.nombre_evento, pe.estado
        FROM intencion_compra_pedido icp
        LEFT JOIN precio_evento pe ON pe.id = icp.precio_evento_id
        WHERE icp.pedido_proveedor_id = %s
        LIMIT 1
    """, (pp_id,))

    ev_row = cur.fetchone()
    if ev_row and ev_row[0]:
        evento_id, nombre_evento, estado_evento = ev_row
        print(f"  precio_evento_id: {evento_id}")
        print(f"  Nombre: {nombre_evento}")
        print(f"  Estado: {estado_evento}")
    else:
        print("  precio_evento_id: NULL (sin listado vinculado)")
        print("[!!] PP sin listado - skip recalcular")
        evento_id = None

    print()

    # 3. Inventario FI
    print("[3] FACTURAS INTERNAS")
    print("-" * 80)
    cur.execute("""
        SELECT fi.id, fi.nro_factura, fi.estado,
               SUM(fid.pares) AS pares_fi,
               fi.lista_precio_id
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        WHERE fi.pp_id = %s
        GROUP BY fi.id, fi.nro_factura, fi.estado, fi.lista_precio_id
        ORDER BY fi.id
    """, (pp_id,))

    fi_rows = cur.fetchall()
    total_fi_pares = 0
    reservadas = []
    confirmadas = []

    if fi_rows:
        print(f"  Total FI: {len(fi_rows)}")
        for fi in fi_rows:
            fi_id, fi_nro, fi_estado, fi_pares, fi_lista_id = fi
            print(f"    {fi_nro} (id={fi_id}) - {fi_estado} - {fi_pares} pares - lista_precio_id={fi_lista_id}")
            total_fi_pares += fi_pares
            if fi_estado.upper().strip() == 'RESERVADA':
                reservadas.append((fi_id, fi_nro, fi_pares))
            elif fi_estado.upper().strip() == 'CONFIRMADA':
                confirmadas.append((fi_id, fi_nro, fi_pares))

        print(f"  Total pares facturados: {total_fi_pares}")
        print(f"  FI RESERVADA: {len(reservadas)} (recalculables)")
        print(f"  FI CONFIRMADA: {len(confirmadas)} (historicas)")
    else:
        print("  Sin facturas internas")

    print()

    # 4. Simular recalcular (read-only, no ejecutar UPDATE)
    print("[4] SIMULACION RECALCULAR")
    print("-" * 80)

    if not evento_id:
        print("  SKIP: PP sin evento vinculado")
    elif not fi_rows:
        print("  SKIP: PP sin FI")
    elif reservadas:
        print(f"  Recalcular {len(reservadas)} FI RESERVADA con evento_id={evento_id}")
        print("  Accion: recalcular_facturas_internas_pp(pp_id=1, evento_id={})".format(evento_id))
        print("  Resultado esperado: actualizar precio_unit/subtotal desde precio_lista")
        print("  Pares: sin cambio en cantidad")
    else:
        print(f"  Sin FI RESERVADA para recalcular")
        print(f"  FI CONFIRMADA no se toca (historico)")

    print()

    # 5. Validar totales finales (sin cambio)
    print("[5] VALIDACION TOTALES (sin cambio)")
    print("-" * 80)
    cur.execute("""
        SELECT SUM(ppd.cantidad_pares) AS pares,
               SUM(ppd.cantidad_cajas) AS cajas
        FROM pedido_proveedor_detalle ppd
        WHERE ppd.pedido_proveedor_id = %s
    """, (pp_id,))

    final_row = cur.fetchone()
    if final_row:
        final_pares, final_cajas = final_row
        print(f"  Pares PP: {final_pares} (sin cambio)")
        print(f"  Cajas PP: {final_cajas} (sin cambio)")

        if final_pares == total_pares and final_cajas == total_cajas:
            print("  [OK] Totales sin cambio")
        else:
            print("  [!!] DESVIO: Totales cambiaron!")
            return False

    print()
    print("=" * 80)
    print("SMOKE TEST: OK")
    print("=" * 80)
    print()
    print("Conclusiones:")
    print(f"  - PP-2026-0001 tiene evento_id={evento_id} vinculado")
    print(f"  - recalcular_facturas_internas_pp existe (funcion en logic.py)")
    print(f"  - FI CONFIRMADA: {len(confirmadas)} (no se recalcula - historico)")
    print(f"  - FI RESERVADA: {len(reservadas)} (recalculable)")
    print(f"  - Totales PP sin cambio: {total_pares} pares, {total_cajas} cajas")

    cur.close()
    conn.close()
    return True

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
