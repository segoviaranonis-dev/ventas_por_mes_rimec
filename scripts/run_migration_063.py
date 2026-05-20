"""
Ejecuta migración 063 — FKs dimensionales en registro_st_vt_rc_reposicion.
OT-PILARES-LEYES-IMPORTACION-001

Usa el mismo patrón de conexión que reset_focal_ic_pp_listados.py:
  DATABASE_URL (.env vía decouple) ó .streamlit/secrets.toml [postgres].

Uso:
  python scripts/run_migration_063.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402

from scripts.backfill_combinacion_desde_ppd import _db_url  # noqa: E402


SQL_PATH = ROOT / "migrations" / "063_registro_st_vt_rc_fk_dimensionales.sql"


def main() -> int:
    db_url = _db_url()
    if not db_url:
        print("[ERROR] DATABASE_URL no configurada (.env / .streamlit/secrets.toml)")
        return 1

    if not SQL_PATH.is_file():
        print(f"[ERROR] No se encontró {SQL_PATH}")
        return 1

    sql = SQL_PATH.read_text(encoding="utf-8")

    print("=" * 78)
    print(f"[063] Ejecutando {SQL_PATH.name}")
    print("=" * 78)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print("[063] OK Migracion aplicada en una transaccion.")
    except Exception as e:
        conn.rollback()
        print(f"[063] ERROR ROLLBACK por error: {e}")
        conn.close()
        return 2

    print()
    print("[063] Verificación de backfill:")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*)                                          AS total,
                COUNT(linea_id)                                   AS con_linea,
                COUNT(referencia_id)                              AS con_referencia,
                COUNT(marca_id)                                   AS con_marca,
                COUNT(genero_id)                                  AS con_genero,
                COUNT(grupo_estilo_id)                            AS con_estilo,
                COUNT(tipo_1_id)                                  AS con_tipo1,
                COUNT(material_id)                                AS con_material,
                COUNT(color_id)                                   AS con_color
            FROM public.registro_st_vt_rc_reposicion
            """
        )
        row = cur.fetchone()
        if row:
            (total, c_l, c_r, c_m, c_g, c_e, c_t, c_mat, c_col) = row

            def pct(n: int) -> str:
                return f"{(n / total * 100):.1f}%" if total else "n/a"

            print(f"  total           : {total}")
            print(f"  linea_id        : {c_l} ({pct(c_l)})")
            print(f"  referencia_id   : {c_r} ({pct(c_r)})")
            print(f"  marca_id        : {c_m} ({pct(c_m)})")
            print(f"  genero_id       : {c_g} ({pct(c_g)})")
            print(f"  grupo_estilo_id : {c_e} ({pct(c_e)})")
            print(f"  tipo_1_id       : {c_t} ({pct(c_t)})")
            print(f"  material_id     : {c_mat} ({pct(c_mat)})")
            print(f"  color_id        : {c_col} ({pct(c_col)})")

    conn.close()
    print()
    print("[063] Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
