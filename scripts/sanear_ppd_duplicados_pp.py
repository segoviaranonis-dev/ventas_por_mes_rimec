"""
Sanear duplicados de pedido_proveedor_detalle basados en molecula.
Modulo 500: 1 molecula = 1 fila ppd.

Uso:
  python scripts/sanear_ppd_duplicados_pp.py --pp-id 1 --dry-run
  python scripts/sanear_ppd_duplicados_pp.py --pp-id 1 --yes
"""
import argparse
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2
import json


def _db_url() -> str | None:
    """Obtener URL desde secrets.toml o .env"""
    from urllib.parse import quote_plus

    try:
        from decouple import config
        u = config("DATABASE_URL")
        if u:
            return u
    except Exception:
        pass
    p = ROOT / ".streamlit" / "secrets.toml"
    if p.is_file():
        try:
            import tomllib
            with p.open("rb") as f:
                pg = tomllib.load(f).get("postgres")
            if isinstance(pg, dict):
                user = pg.get("user") or pg.get("username")
                pwd = pg.get("password")
                host = pg.get("host", "localhost")
                port = pg.get("port", 5432)
                db = pg.get("database") or pg.get("dbname")
                if user and pwd and db:
                    return (
                        f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(pwd)}"
                        f"@{host}:{port}/{db}"
                    )
        except Exception:
            pass
    return None


def main():
    ap = argparse.ArgumentParser(description="Sanear duplicados de ppd por molecula")
    ap.add_argument("--pp-id", type=int, required=True, help="ID del pedido_proveedor")
    ap.add_argument("--linea", default=None, help="Filtro opcional por linea (ej. 7320)")
    ap.add_argument("--ref", default=None, help="Filtro opcional por referencia (ej. 239)")
    ap.add_argument("--dry-run", action="store_true", help="Solo mostrar preview, sin DELETE")
    ap.add_argument("--yes", action="store_true", help="Ejecutar DELETE (requerido para ejecutar)")
    args = ap.parse_args()

    if not args.dry_run and not args.yes:
        print("[ERROR] Debes pasar --dry-run (preview) o --yes (ejecutar DELETE)")
        return 1

    url = _db_url()
    if not url:
        print("[ERROR] No se pudo obtener DATABASE_URL desde secrets.toml o .env")
        return 1

    dsn = url.replace("postgresql+psycopg2://", "postgres://").replace(
        "postgresql://", "postgres://"
    )
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    # Construir WHERE
    where_parts = ["pedido_proveedor_id = %s"]
    params = [args.pp_id]
    if args.linea:
        where_parts.append("linea = %s")
        params.append(args.linea)
    if args.ref:
        where_parts.append("referencia = %s")
        params.append(args.ref)
    where_clause = " AND ".join(where_parts)

    # Preview: identificar duplicados
    sql_preview = f"""
        SELECT id, linea, referencia, material_code, color_code, descp_color,
               cantidad_cajas, cantidad_pares, grades_json::text, fila_origen_f9,
               ROW_NUMBER() OVER (
                 PARTITION BY pedido_proveedor_id, linea, referencia,
                              material_code, color_code, grades_json::text
                 ORDER BY id
               ) AS rn
        FROM pedido_proveedor_detalle
        WHERE {where_clause}
        ORDER BY linea, referencia, material_code, color_code, grades_json::text, id
    """
    cur.execute(sql_preview, params)
    rows = cur.fetchall()

    if not rows:
        print(f"[INFO] No se encontraron filas para PP {args.pp_id}")
        cur.close()
        conn.close()
        return 0

    duplicates = [r for r in rows if r[10] > 1]  # rn > 1
    unique = [r for r in rows if r[10] == 1]

    print("=" * 80)
    print(f"PREVIEW: pedido_proveedor_detalle (PP_ID={args.pp_id})")
    print("=" * 80)
    print(f"Total filas: {len(rows)}")
    print(f"Filas unicas (rn=1): {len(unique)}")
    print(f"Filas duplicadas (rn>1): {len(duplicates)}")
    print()

    if len(duplicates) == 0:
        print("[OK] No hay duplicados para eliminar")
        cur.close()
        conn.close()
        return 0

    # Agrupar por molecula para mostrar resumen
    from collections import defaultdict
    mol_groups = defaultdict(list)
    for r in rows:
        mol_key = f"{r[1]}|{r[2]}|{r[3]}|{r[4]}|{r[8]}"  # linea|ref|mat|col|grades
        mol_groups[mol_key].append(r)

    print("MOLECULAS CON DUPLICADOS:")
    print("-" * 80)
    for mol_key, group in mol_groups.items():
        if len(group) > 1:
            first = group[0]
            linea, ref, mat, col, descp = first[1], first[2], first[3], first[4], first[5]
            total_cajas = sum(r[6] for r in group)
            total_pares = sum(r[7] for r in group)
            print(f"  {linea}/{ref} {mat}-{col} {descp}")
            print(f"    {len(group)} filas duplicadas | Total: {total_cajas} cjs / {total_pares} pares")
            for r in group:
                marker = "[MANTENER]" if r[10] == 1 else "[ELIMINAR]"
                print(f"      id={r[0]} rn={r[10]} cajas={r[6]} pares={r[7]} fila_f9={r[9]} {marker}")
            print()

    if args.dry_run:
        print("=" * 80)
        print("[DRY-RUN] No se ejecuto ningun DELETE. Use --yes para ejecutar.")
        print("=" * 80)
        cur.close()
        conn.close()
        return 0

    # Ejecutar UPDATE + DELETE
    if args.yes:
        print("=" * 80)
        print(f"[EJECUTANDO] Consolidacion de moleculas duplicadas...")
        print("=" * 80)

        # Paso 1: UPDATE la fila rn=1 con suma de cajas/pares de todas las duplicadas
        for mol_key, group in mol_groups.items():
            if len(group) > 1:
                first_id = group[0][0]  # id de la fila rn=1
                total_cajas = sum(r[6] for r in group)
                total_pares = sum(r[7] for r in group)
                total_fob = sum(float(r[6] * r[7]) for r in group if r[6] and r[7])  # Aproximado

                linea, ref = group[0][1], group[0][2]
                print(f"  UPDATE id={first_id} ({linea}/{ref}): {total_cajas} cjs / {total_pares} pares")

                cur.execute(
                    """
                    UPDATE pedido_proveedor_detalle
                    SET cantidad_cajas = %s,
                        cantidad_pares = %s,
                        cantidad = %s
                    WHERE id = %s
                    """,
                    (total_cajas, total_pares, total_pares, first_id)
                )

        conn.commit()
        print(f"[OK] {len([g for g in mol_groups.values() if len(g) > 1])} moleculas consolidadas")

        # Paso 2: DELETE filas duplicadas (rn>1)
        print(f"\n[EJECUTANDO] DELETE de {len(duplicates)} filas duplicadas...")
        ids_to_delete = [r[0] for r in duplicates]
        cur.execute(
            "DELETE FROM pedido_proveedor_detalle WHERE id = ANY(%s)",
            (ids_to_delete,)
        )
        conn.commit()
        print(f"[OK] {cur.rowcount} filas eliminadas")

        # Verificar
        cur.execute(
            f"SELECT COUNT(*) FROM pedido_proveedor_detalle WHERE {where_clause}",
            params
        )
        count_after = cur.fetchone()[0]
        print(f"[VERIFICACION] Filas restantes: {count_after} (esperado: {len(unique)})")

        if count_after == len(unique):
            print("[EXITO] Duplicados eliminados correctamente")
        else:
            print(f"[ADVERTENCIA] Count no coincide. Revisar manualmente.")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
