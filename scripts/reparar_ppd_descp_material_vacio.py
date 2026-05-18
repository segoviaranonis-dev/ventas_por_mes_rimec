"""
OT-DEPOSITO-WEB-506-001 P1: Reparar ppd.descp_material vacio desde material.descripcion.

UPDATE pedido_proveedor_detalle
SET descp_material = material.descripcion
WHERE (descp_material IS NULL OR TRIM(descp_material) = '')
  AND (material_code IS NOT NULL OR id_material IS NOT NULL)
  AND material.descripcion IS NOT NULL

Incluye ppd_id=202 con material_code=31855.

Uso:
  python scripts/reparar_ppd_descp_material_vacio.py --pp-id 1 --dry-run
  python scripts/reparar_ppd_descp_material_vacio.py --pp-id 1 --yes
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
    print(f"REPARAR ppd.descp_material vacio (pp_id={pp_id})")
    print("MODE:", "DRY RUN" if dry_run else "EXECUTE")
    print("=" * 80)
    print()

    conn = psycopg2.connect(db_url)
    if not dry_run:
        conn.autocommit = False
    cur = conn.cursor()

    # Get PP info
    cur.execute("""
        SELECT numero_registro, proveedor_importacion_id
        FROM pedido_proveedor
        WHERE id = %s
    """, (pp_id,))

    pp_row = cur.fetchone()
    if not pp_row:
        print(f"[ERROR] PP {pp_id} no encontrado")
        return False

    pp_nro, prov_id = pp_row
    print(f"[1] PP: {pp_nro} (proveedor_id={prov_id})")
    print()

    # Find PPD rows with empty descp_material but valid material_code
    print("[2] Buscar PPD con descp_material vacio y material_code valido")

    cur.execute("""
        SELECT ppd.id, ppd.linea, ppd.referencia,
               ppd.material_code, ppd.id_material, ppd.descp_material
        FROM pedido_proveedor_detalle ppd
        WHERE ppd.pedido_proveedor_id = %s
          AND (ppd.descp_material IS NULL OR TRIM(ppd.descp_material) = '')
          AND (ppd.material_code IS NOT NULL OR ppd.id_material IS NOT NULL)
        ORDER BY ppd.id
    """, (pp_id,))

    ppd_rows = cur.fetchall()

    if not ppd_rows:
        print("    No se encontraron filas para reparar")
        print()
        cur.close()
        conn.close()
        return True

    print(f"    Encontrados: {len(ppd_rows)} PPD con descp_material vacio")
    print()

    # For each, try to get material.descripcion
    print("[3] Resolver material.descripcion desde material_code")
    print("-" * 80)

    reparados = 0
    no_encontrados = []

    for ppd_id, linea, ref, mat_code, mat_id, mat_desc in ppd_rows:
        # Try by material_code first
        descripcion = None

        if mat_code is not None:
            cur.execute("""
                SELECT descripcion
                FROM material
                WHERE proveedor_id = %s AND codigo_proveedor = %s
                LIMIT 1
            """, (prov_id, mat_code))

            m_row = cur.fetchone()
            if m_row and m_row[0]:
                descripcion = m_row[0]

        # Fallback: try by id_material (less reliable)
        if not descripcion and mat_id is not None:
            cur.execute("""
                SELECT descripcion
                FROM material
                WHERE id = %s
                LIMIT 1
            """, (mat_id,))

            m_row = cur.fetchone()
            if m_row and m_row[0]:
                descripcion = m_row[0]

        if descripcion:
            if dry_run:
                print(f"  [DRY] ppd_id={ppd_id}: linea={linea}, ref={ref}")
                print(f"        material_code={mat_code} -> \"{descripcion}\"")
                reparados += 1
            else:
                cur.execute("""
                    UPDATE pedido_proveedor_detalle
                    SET descp_material = %s
                    WHERE id = %s
                """, (descripcion, ppd_id))
                reparados += 1
                print(f"  UPDATE ppd_id={ppd_id}: \"{descripcion}\"")
        else:
            no_encontrados.append((ppd_id, linea, ref, mat_code, mat_id))

    print()
    print(f"[4] Resumen:")
    print(f"    Reparados:      {reparados}")
    print(f"    No encontrados: {len(no_encontrados)}")

    if no_encontrados:
        print()
        print("    PPD sin material.descripcion:")
        for ppd_id, lin, ref, mat_code, mat_id in no_encontrados[:10]:
            print(f"      ppd_id={ppd_id}: {lin}-{ref} mat_code={mat_code} mat_id={mat_id}")

    print()

    if not dry_run and reparados > 0:
        conn.commit()
        print("[OK] Transaction committed")
    elif dry_run:
        print("[DRY RUN] Sin cambios")
    else:
        print("[INFO] No habia filas para reparar")

    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
