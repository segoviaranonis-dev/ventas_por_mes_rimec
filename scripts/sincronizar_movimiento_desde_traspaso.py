"""
OT-DEPOSITO-WEB-506-001 R1-R4: Sincronizar movimiento_detalle desde traspaso_detalle.

Idempotente: solo inserta el delta faltante.

Uso:
  python scripts/sincronizar_movimiento_desde_traspaso.py --traspaso-id 2 --dry-run
  python scripts/sincronizar_movimiento_desde_traspaso.py --traspaso-id 2 --yes
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2

from scripts.backfill_combinacion_desde_ppd import _db_url


def main() -> bool:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traspaso-id", type=int, required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dry_run = not args.yes
    trp_id = args.traspaso_id

    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return False

    print("=" * 80)
    print(f"SINCRONIZAR movimiento_detalle desde traspaso_detalle (id={trp_id})")
    print("MODE:", "DRY RUN" if dry_run else "EXECUTE")
    print("=" * 80)
    print()

    conn = psycopg2.connect(db_url)
    if not dry_run:
        conn.autocommit = False
    cur = conn.cursor()

    # Get traspaso
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

    # Find or create movimiento
    cur.execute("""
        SELECT id
        FROM movimiento
        WHERE documento_ref = %s AND tipo = 'INGRESO_COMPRA'
        LIMIT 1
    """, (t_nro,))

    mov_row = cur.fetchone()

    if mov_row:
        mov_id = mov_row[0]
        print(f"[2] Movimiento existente: mov_id={mov_id}")
    else:
        if t_estado != "CONFIRMADO":
            print(f"[ERROR] Traspaso no CONFIRMADO (estado={t_estado})")
            print("    No se puede crear movimiento para traspaso no confirmado")
            return False

        if dry_run:
            print(f"[2] [DRY] Se crearia movimiento INGRESO_COMPRA para {t_nro}")
            mov_id = -1  # Dummy
        else:
            # Create movimiento
            cur.execute("""
                INSERT INTO movimiento (
                    tipo, documento_ref, almacen_destino_id, notas
                )
                VALUES (
                    'INGRESO_COMPRA', %s, %s, 'Ingreso desde traspaso (sync auto)'
                )
                RETURNING id
            """, (t_nro, t_almacen_destino))

            mov_id = cur.fetchone()[0]
            print(f"[2] Movimiento creado: mov_id={mov_id}")

    print()

    # Get delta combinaciones
    print("[3] Calculando delta por combinacion_id")

    if mov_id == -1:  # Dry-run sin movimiento
        cur.execute("""
            SELECT td.combinacion_id, td.cantidad AS qty_td,
                   0 AS qty_md,
                   l.codigo_proveedor AS linea,
                   r.codigo_proveedor AS ref,
                   m.descripcion AS material,
                   c.nombre AS color,
                   t.talla_etiqueta AS talla
            FROM traspaso_detalle td
            JOIN combinacion comb ON comb.id = td.combinacion_id
            JOIN linea l ON l.id = comb.linea_id
            JOIN referencia r ON r.id = comb.referencia_id
            LEFT JOIN material m ON m.id = comb.material_id
            LEFT JOIN color c ON c.id = comb.color_id
            JOIN talla t ON t.id = comb.talla_id
            WHERE td.traspaso_id = %s
            ORDER BY td.combinacion_id
        """, (trp_id,))
    else:
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
            ORDER BY td.combinacion_id
        """, (mov_id, trp_id))

    rows = cur.fetchall()

    insertados = 0
    total_pares = 0

    for row in rows:
        comb_id, qty_td, qty_md, lin, ref, mat, col, talla = row
        delta = qty_td - qty_md

        if delta <= 0:
            continue

        total_pares += delta

        if dry_run:
            print(f"  [DRY] INSERT: comb_id={comb_id} ({lin}-{ref} {mat or ''}/{col or ''} t{talla})")
            print(f"        cantidad={delta} (TD={qty_td}, MD={qty_md})")
            insertados += 1
        else:
            cur.execute("""
                INSERT INTO movimiento_detalle (movimiento_id, combinacion_id, cantidad, signo)
                VALUES (%s, %s, %s, 1)
            """, (mov_id, comb_id, delta))
            insertados += 1
            print(f"  INSERT: comb_id={comb_id} ({lin}-{ref} t{talla}), cantidad={delta}")

    print()
    print(f"[4] Resumen:")
    print(f"    Filas insertadas: {insertados}")
    print(f"    Pares agregados:  {total_pares}")
    print()

    if not dry_run and insertados > 0:
        conn.commit()
        print("[OK] Transaction committed")
    elif dry_run:
        print("[DRY RUN] Sin cambios")
    else:
        print("[INFO] No habia delta para insertar")

    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
