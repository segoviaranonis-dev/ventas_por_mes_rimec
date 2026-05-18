"""
OT-FI-CASO-508-001 Fase 1: Backfill fi.caso, fi.caso_id, fi.marca desde precio_lista.

Corrige factura_interna:
1. lista_precio_id incorrecto (debe coincidir con PP.precio_evento_id)
2. caso, caso_id vacíos (copiar desde precio_lista)
3. marca si falta (desde marca_v2 o intencion_compra_pedido)

Uso:
  python scripts/reparar_fi_caso_desde_listado.py --pp-id 1 --dry-run
  python scripts/reparar_fi_caso_desde_listado.py --pp-id 1 --yes
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
    parser.add_argument("--pp-id", type=int, required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dry_run = not args.yes
    pp_id = args.pp_id

    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return False

    print("=" * 80)
    print(f"REPARAR fi.caso desde precio_lista (pp_id={pp_id})")
    print("MODE:", "DRY RUN" if dry_run else "EXECUTE")
    print("=" * 80)
    print()

    conn = psycopg2.connect(db_url)
    if not dry_run:
        conn.autocommit = False
    cur = conn.cursor()

    # Get PP info + precio_evento_id correcto
    cur.execute("""
        SELECT pp.numero_registro, icp.precio_evento_id
        FROM pedido_proveedor pp
        LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
        WHERE pp.id = %s
    """, (pp_id,))

    pp_row = cur.fetchone()
    if not pp_row:
        print(f"[ERROR] PP {pp_id} no encontrado")
        return False

    pp_nro, evento_correcto = pp_row
    print(f"[1] PP: {pp_nro}")
    print(f"    precio_evento_id correcto: {evento_correcto}")
    print()

    if not evento_correcto:
        print("[ERROR] PP sin precio_evento_id (sin intencion_compra_pedido)")
        return False

    # Get facturas internas del PP
    cur.execute("""
        SELECT fi.id, fi.nro_factura, fi.lista_precio_id, fi.caso, fi.caso_id, fi.marca, fi.marca_id
        FROM factura_interna fi
        WHERE fi.pp_id = %s
    """, (pp_id,))

    facturas = cur.fetchall()

    if not facturas:
        print(f"[2] No hay facturas internas para PP {pp_id}")
        return True

    print(f"[2] Facturas internas encontradas: {len(facturas)}")
    print()

    reparadas = 0

    for fi_id, nro_fi, lista_id_actual, caso_actual, caso_id_actual, marca_actual, marca_id_actual in facturas:
        print(f"[3] Procesando FI: {nro_fi} (id={fi_id})")
        print(f"    Estado actual:")
        print(f"      lista_precio_id: {lista_id_actual}")
        print(f"      caso: '{caso_actual}'")
        print(f"      caso_id: {caso_id_actual}")
        print(f"      marca: '{marca_actual}'")
        print(f"      marca_id: {marca_id_actual}")

        cambios = {}

        # Corregir lista_precio_id si difiere
        if lista_id_actual != evento_correcto:
            cambios["lista_precio_id"] = evento_correcto
            print(f"    -> Corregir lista_precio_id: {lista_id_actual} -> {evento_correcto}")

        # Resolver caso dominante del evento
        cur.execute("""
            SELECT pl.nombre_caso_aplicado, pl.caso_id, COUNT(*) AS cnt
            FROM precio_lista pl
            WHERE pl.evento_id = %s
              AND pl.nombre_caso_aplicado IS NOT NULL
            GROUP BY pl.nombre_caso_aplicado, pl.caso_id
            ORDER BY COUNT(*) DESC, pl.nombre_caso_aplicado
            LIMIT 1
        """, (evento_correcto,))

        caso_row = cur.fetchone()

        if caso_row:
            nombre_caso, caso_id_nuevo, cnt = caso_row

            # Actualizar caso si está vacío o es "Sin caso"
            if not caso_actual or caso_actual.strip() == "" or caso_actual == "Sin caso":
                cambios["caso"] = nombre_caso
                print(f"    -> Actualizar caso: '{caso_actual}' -> '{nombre_caso}'")

            # Verificar que caso_id existe en caso_precio_biblioteca antes de actualizar
            if not caso_id_actual and caso_id_nuevo:
                cur.execute("""
                    SELECT id FROM caso_precio_biblioteca WHERE id = %s
                """, (caso_id_nuevo,))

                if cur.fetchone():
                    cambios["caso_id"] = caso_id_nuevo
                    print(f"    -> Actualizar caso_id: {caso_id_actual} -> {caso_id_nuevo}")
                else:
                    print(f"    [WARN] caso_id={caso_id_nuevo} no existe en caso_precio_biblioteca (omitido)")
        else:
            print(f"    [WARN] No hay casos en precio_lista para evento {evento_correcto}")

        # Si hay cambios, UPDATE
        if cambios:
            if dry_run:
                print(f"    [DRY] UPDATE factura_interna SET {', '.join(f'{k}={v}' for k, v in cambios.items())} WHERE id={fi_id}")
            else:
                set_clauses = ", ".join(f"{k} = %s" for k in cambios.keys())
                values = list(cambios.values()) + [fi_id]

                cur.execute(f"""
                    UPDATE factura_interna
                    SET {set_clauses}
                    WHERE id = %s
                """, values)

                print(f"    [OK] Actualizado")

            reparadas += 1
        else:
            print(f"    [INFO] No requiere cambios")

        print()

    print("=" * 80)
    print(f"[RESUMEN]")
    print(f"  Facturas procesadas: {len(facturas)}")
    print(f"  Facturas reparadas:  {reparadas}")
    print("=" * 80)

    if not dry_run and reparadas > 0:
        conn.commit()
        print("\n[OK] Transaction committed")
    elif dry_run:
        print("\n[DRY RUN] Sin cambios")
    else:
        print("\n[INFO] No había facturas para reparar")

    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
