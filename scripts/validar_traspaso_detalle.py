"""
Validar traspaso_detalle: duplicados, pares, combinaciones.
"""
import psycopg2
import sys

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"


def main():
    traspaso_id = None
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
    print(f"VALIDACION traspaso_detalle (traspaso_id={traspaso_id})")
    print("=" * 80)
    print()

    # C1: Total combinaciones en tabla
    cur.execute("SELECT COUNT(*) FROM combinacion")
    total_comb = cur.fetchone()[0]
    print(f"[C1] Total combinaciones: {total_comb}")
    print(f"     Status: {'+ PASS' if total_comb > 0 else '- FAIL'}")
    print()

    # C2: Pares en traspaso_detalle
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(cantidad), 0)
        FROM traspaso_detalle
        WHERE traspaso_id = %s
    """, (traspaso_id,))
    rows, pares = cur.fetchone()
    print(f"[C2] Traspaso_detalle: {rows} rows, {pares} pares")
    print(f"     Status: {'+ PASS' if pares >= 30 else '- FAIL (expected ~40-44)'}")
    print()

    # C3: Duplicados (traspaso_id, combinacion_id)
    cur.execute("""
        SELECT combinacion_id, COUNT(*)
        FROM traspaso_detalle
        WHERE traspaso_id = %s
        GROUP BY combinacion_id
        HAVING COUNT(*) > 1
    """, (traspaso_id,))
    dupes = cur.fetchall()
    print(f"[C3] Duplicados (traspaso_id, combinacion_id): {len(dupes)}")
    if dupes:
        print("     Status: - FAIL")
        for comb_id, cnt in dupes[:10]:
            print(f"       combinacion_id={comb_id}: {cnt} rows")
    else:
        print("     Status: + PASS")
    print()

    # Extra: Detalle por combinacion_id
    cur.execute("""
        SELECT td.combinacion_id, td.cantidad,
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
        ORDER BY l.codigo_proveedor, r.codigo_proveedor, t.talla_etiqueta
    """, (traspaso_id,))

    print("[DETALLE] Traspaso_detalle rows:")
    for row in cur.fetchall():
        comb_id, qty, linea, ref, mat, col, talla = row
        print(f"  {linea}-{ref} {mat or ''}/{col or ''} t{talla}: {qty} pares (comb_id={comb_id})")

    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
