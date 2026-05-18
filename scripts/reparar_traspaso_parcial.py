"""
OT-TRASPASO-504-001 R3: Reparar traspaso parcial con duplicados
Consolida traspaso_detalle cuando hay múltiples filas con mismo (traspaso_id, combinacion_id)
"""
import psycopg2
import sys
from datetime import datetime

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def main():
    traspaso_id = None

    # Parse args
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--traspaso-id' and i + 1 < len(sys.argv):
            traspaso_id = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    if not traspaso_id:
        print("[ERROR] Especificar --traspaso-id <id>")
        return False

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("=" * 80)
    print(f"REPARAR TRASPASO PARCIAL (traspaso_id={traspaso_id})")
    print("=" * 80)
    print()

    # 1. Check if traspaso exists
    print("[1] VERIFICAR TRASPASO")
    print("-" * 80)
    cur.execute("""
        SELECT id, numero_registro, estado, compra_legal_id
        FROM traspaso
        WHERE id = %s
    """, (traspaso_id,))

    t_row = cur.fetchone()
    if not t_row:
        print(f"[ERROR] Traspaso {traspaso_id} not found")
        return False

    t_id, t_nro, t_estado, cl_id = t_row
    print(f"  Traspaso: {t_nro} (id={t_id})")
    print(f"  Estado: {t_estado}")
    print(f"  Compra Legal: {cl_id or 'N/A'}")

    print()

    # 2. Check for duplicates
    print("[2] DETECTAR DUPLICADOS")
    print("-" * 80)
    cur.execute("""
        SELECT
            combinacion_id,
            COUNT(*) AS count,
            SUM(cantidad) AS total_qty,
            STRING_AGG(CAST(id AS TEXT), ', ') AS td_ids
        FROM traspaso_detalle
        WHERE traspaso_id = %s
        GROUP BY combinacion_id
        HAVING COUNT(*) > 1
    """, (traspaso_id,))

    dup_rows = cur.fetchall()
    if not dup_rows:
        print("  [OK] Sin duplicados detectados")
        print("  No se requiere reparación")
        return True

    print(f"  [!!] {len(dup_rows)} combinaciones duplicadas:")
    for dup in dup_rows:
        comb_id, count, total_qty, td_ids = dup
        print(f"    combinacion_id={comb_id}: {count} ocurrencias, qty total={total_qty}")
        print(f"      td.id: {td_ids}")

    print()

    # 3. Consolidate duplicates
    print("[3] CONSOLIDAR DUPLICADOS")
    print("-" * 80)
    print("  Acción: DELETE duplicados + INSERT consolidado por combinacion_id")

    try:
        # Start transaction
        cur.execute("BEGIN")

        # Build consolidated rows
        cur.execute("""
            SELECT combinacion_id, SUM(cantidad) AS total_qty
            FROM traspaso_detalle
            WHERE traspaso_id = %s
            GROUP BY combinacion_id
        """, (traspaso_id,))

        consolidated = cur.fetchall()
        print(f"  Total combinaciones únicas: {len(consolidated)}")

        # Delete all existing rows
        cur.execute("""
            DELETE FROM traspaso_detalle
            WHERE traspaso_id = %s
        """, (traspaso_id,))
        print(f"  Deleted all rows for traspaso_id={traspaso_id}")

        # Insert consolidated rows
        inserted = 0
        for comb_id, total_qty in consolidated:
            cur.execute("""
                INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
                VALUES (%s, %s, %s)
            """, (traspaso_id, comb_id, int(total_qty)))
            inserted += 1

        print(f"  Inserted {inserted} consolidated rows")

        # Commit transaction
        cur.execute("COMMIT")
        print("  [OK] Transaction committed")

    except Exception as e:
        cur.execute("ROLLBACK")
        print(f"  [ERROR] Transaction rolled back: {e}")
        return False

    print()

    # 4. Verify repair
    print("[4] VERIFICAR REPARACION")
    print("-" * 80)
    cur.execute("""
        SELECT
            combinacion_id,
            COUNT(*) AS count
        FROM traspaso_detalle
        WHERE traspaso_id = %s
        GROUP BY combinacion_id
        HAVING COUNT(*) > 1
    """, (traspaso_id,))

    remaining_dups = cur.fetchall()
    if remaining_dups:
        print(f"  [!!] {len(remaining_dups)} duplicados restantes!")
        return False
    else:
        print("  [OK] 0 duplicados restantes")

    cur.execute("""
        SELECT COUNT(*) AS total_rows, SUM(cantidad) AS total_qty
        FROM traspaso_detalle
        WHERE traspaso_id = %s
    """, (traspaso_id,))

    final_row = cur.fetchone()
    if final_row:
        total_rows, total_qty = final_row
        print(f"  Total rows: {total_rows}")
        print(f"  Total qty: {total_qty}")

    print()
    print("=" * 80)
    print("REPARACION COMPLETA")
    print("=" * 80)

    cur.close()
    conn.close()
    return True

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
