"""
Listar todos los PP con moleculas duplicadas para saneo masivo
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2


def _db_url() -> str | None:
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
    url = _db_url()
    if not url:
        print("[ERROR] No se pudo obtener DATABASE_URL")
        return 1

    dsn = url.replace("postgresql+psycopg2://", "postgres://").replace(
        "postgresql://", "postgres://"
    )
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    # Buscar PP con duplicados por molecula
    sql = """
        WITH duplicates AS (
            SELECT pedido_proveedor_id,
                   linea, referencia, material_code, color_code, grades_json::text,
                   COUNT(*) as n_duplicados
            FROM pedido_proveedor_detalle
            GROUP BY pedido_proveedor_id, linea, referencia,
                     material_code, color_code, grades_json::text
            HAVING COUNT(*) > 1
        )
        SELECT pp.id, pp.numero_registro, pp.estado,
               COUNT(DISTINCT CONCAT(d.linea, '|', d.referencia, '|',
                                     d.material_code, '|', d.color_code, '|', d.grades_json)) as moleculas_duplicadas,
               SUM(d.n_duplicados) as total_filas_duplicadas
        FROM duplicates d
        JOIN pedido_proveedor pp ON pp.id = d.pedido_proveedor_id
        GROUP BY pp.id, pp.numero_registro, pp.estado
        ORDER BY pp.id
    """

    cur.execute(sql)
    rows = cur.fetchall()

    print("=" * 80)
    print("PP CON MOLECULAS DUPLICADAS")
    print("=" * 80)
    print(f"Total PP afectados: {len(rows)}\n")

    if not rows:
        print("[OK] No hay PP con duplicados")
        cur.close()
        conn.close()
        return 0

    print("PP_ID | Numero          | Estado   | Moleculas_Dup | Filas_Dup")
    print("-" * 70)

    total_moleculas = 0
    total_filas = 0
    pps_to_clean = []

    for r in rows:
        pp_id, pp_nro, estado, mol_dup, filas_dup = r
        print(f"{pp_id:5} | {pp_nro:15} | {estado:8} | {mol_dup:13} | {filas_dup:9}")
        total_moleculas += mol_dup
        total_filas += filas_dup

        # Solo recomendar saneo en PP ABIERTO/ENVIADO
        if estado in ('ABIERTO', 'ENVIADO'):
            pps_to_clean.append(pp_id)

    print()
    print(f"TOTAL: {total_moleculas} moleculas duplicadas, {total_filas} filas totales")
    print()

    if pps_to_clean:
        print("=" * 80)
        print("RECOMENDACION SANEO (PP en estado ABIERTO/ENVIADO)")
        print("=" * 80)
        print(f"PP a sanear: {len(pps_to_clean)}")
        print()
        print("Comandos sugeridos (ejecutar uno por uno):")
        print()
        for pp_id in pps_to_clean:
            print(f"# PP_ID={pp_id}")
            print(f"python scripts\\sanear_ppd_duplicados_pp.py --pp-id {pp_id} --dry-run")
            print(f"python scripts\\sanear_ppd_duplicados_pp.py --pp-id {pp_id} --yes")
            print()
    else:
        print("[INFO] Todos los PP con duplicados estan en estado cerrado/comprado")
        print("       No se recomienda modificar datos historicos")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
