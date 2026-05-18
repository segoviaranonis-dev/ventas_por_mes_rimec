"""
OT-DEPOSITO-WEB-506-001 I1: Auditar brecha traspaso_detalle vs movimiento_detalle.

Uso:
  python scripts/auditar_stock_traspaso_vs_movimiento.py --traspaso-id 2
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2

from scripts.backfill_combinacion_desde_ppd import _db_url


def main() -> bool:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traspaso-id", type=int, required=True)
    args = parser.parse_args()
    trp_id = args.traspaso_id

    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return False

    print("=" * 80)
    print(f"AUDITORIA: Traspaso {trp_id} vs Movimiento")
    print("=" * 80)
    print()

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Get traspaso info
    cur.execute("""
        SELECT numero_registro, estado, almacen_destino_id
        FROM traspaso
        WHERE id = %s
    """, (trp_id,))

    t_row = cur.fetchone()
    if not t_row:
        print(f"[ERROR] Traspaso {trp_id} no encontrado")
        return False

    t_nro, t_estado, t_almacen_destino = t_row
    print(f"[1] Traspaso: {t_nro}")
    print(f"    Estado: {t_estado}")
    print(f"    Almacen destino: {t_almacen_destino}")
    print()

    # Count traspaso_detalle
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(cantidad), 0)
        FROM traspaso_detalle
        WHERE traspaso_id = %s
    """, (trp_id,))

    td_rows, td_pares = cur.fetchone()
    print(f"[2] traspaso_detalle:")
    print(f"    Filas: {td_rows}")
    print(f"    Pares: {td_pares}")
    print()

    # Find movimiento for this traspaso
    cur.execute("""
        SELECT id, tipo, documento_ref
        FROM movimiento
        WHERE documento_ref = %s
        ORDER BY id
    """, (t_nro,))

    mov_rows = cur.fetchall()

    if not mov_rows:
        print(f"[3] movimiento: NO ENCONTRADO (documento_ref={t_nro})")
        print(f"    IMPLICACION: Traspaso no confirmado o ingreso no procesado")
        print()
        return True

    print(f"[3] movimiento: {len(mov_rows)} movimientos encontrados")
    for mov_id, mov_tipo, mov_ref in mov_rows:
        print(f"    mov_id={mov_id}, tipo={mov_tipo}, ref={mov_ref}")
    print()

    # Get movimiento_id for INGRESO_COMPRA
    mov_id = None
    for mid, mtipo, _ in mov_rows:
        if mtipo == "INGRESO_COMPRA":
            mov_id = mid
            break

    if not mov_id:
        print(f"[4] movimiento_detalle: NO ENCONTRADO (sin INGRESO_COMPRA)")
        print(f"    Movimientos disponibles: {[mt for _, mt, _ in mov_rows]}")
        return True

    # Count movimiento_detalle
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(cantidad * signo), 0)
        FROM movimiento_detalle
        WHERE movimiento_id = %s
    """, (mov_id,))

    md_rows, md_pares = cur.fetchone()
    print(f"[4] movimiento_detalle (mov_id={mov_id}):")
    print(f"    Filas: {md_rows}")
    print(f"    Pares: {md_pares}")
    print()

    # Delta
    delta = td_pares - md_pares
    print("=" * 80)
    print("[5] DELTA")
    print("=" * 80)
    print(f"  traspaso_detalle:    {td_pares} pares")
    print(f"  movimiento_detalle:  {md_pares} pares")
    print(f"  BRECHA:              {delta} pares")
    print()

    if delta == 0:
        print("  Status: + OK (sincronizado)")
        print()
        cur.close()
        conn.close()
        return True

    print(f"  Status: - FALTA sincronizar {delta} pares")
    print()

    # Find missing combinaciones
    print("[6] COMBINACIONES FALTANTES")
    print("-" * 80)

    cur.execute("""
        SELECT td.combinacion_id, td.cantidad AS qty_td,
               COALESCE(SUM(md.cantidad * md.signo), 0) AS qty_md,
               l.codigo_proveedor AS linea,
               r.codigo_proveedor AS ref,
               m.descripcion AS material,
               c.nombre AS color,
               t.talla_etiqueta AS talla
        FROM traspaso_detalle td
        LEFT JOIN movimiento_detalle md ON md.combinacion_id = td.combinacion_id
          AND md.movimiento_id = %s
        JOIN combinacion comb ON comb.id = td.combinacion_id
        JOIN linea l ON l.id = comb.linea_id
        JOIN referencia r ON r.id = comb.referencia_id
        LEFT JOIN material m ON m.id = comb.material_id
        LEFT JOIN color c ON c.id = comb.color_id
        JOIN talla t ON t.id = comb.talla_id
        WHERE td.traspaso_id = %s
        GROUP BY td.combinacion_id, td.cantidad, l.codigo_proveedor,
                 r.codigo_proveedor, m.descripcion, c.nombre, t.talla_etiqueta
        HAVING td.cantidad > COALESCE(SUM(md.cantidad * md.signo), 0)
        ORDER BY l.codigo_proveedor, r.codigo_proveedor, t.talla_etiqueta
    """, (mov_id, trp_id))

    missing = cur.fetchall()

    if missing:
        print(f"  Combinaciones con deficit: {len(missing)}")
        total_missing = 0
        for row in missing:
            comb_id, qty_td, qty_md, lin, ref, mat, col, talla = row
            deficit = qty_td - qty_md
            total_missing += deficit
            print(f"    comb_id={comb_id}: {lin}-{ref} {mat or ''}/{col or ''} t{talla}")
            print(f"      TD={qty_td}, MD={qty_md}, deficit={deficit}")

        print()
        print(f"  Total pares faltantes: {total_missing}")
    else:
        print("  No hay combinaciones faltantes (todas iguales)")

    print()
    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
