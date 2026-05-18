"""
OT-COMBINACION-505-001 Fase 2 R1: Backfill combinacion desde pedido_proveedor_detalle.

Alineado con modules/compra_legal/logic.py::_resolve_combinacion_id:
  - referencia (no linea_referencia) en combinacion.referencia_id
  - material/color por descripcion/nombre
  - talla por talla_etiqueta
  - combinacion sin proveedor_id, activo_web=false

Uso:
  python scripts/backfill_combinacion_desde_ppd.py --pp-id 1 --dry-run
  python scripts/backfill_combinacion_desde_ppd.py --pp-id 1 --yes
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2


def _db_url() -> str | None:
    from urllib.parse import quote_plus

    try:
        from decouple import config

        u = config("DATABASE_URL")
        if u:
            return u.replace("postgresql+psycopg2://", "postgresql://")
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
                        f"postgresql://{quote_plus(user)}:{quote_plus(pwd)}"
                        f"@{host}:{port}/{db}"
                    )
        except Exception:
            pass
    return None


# Códigos negativos estables: no colisionan con F9 del proveedor (positivos).
_SYNTH_COLOR_BASE = -9_000_000_000
_SYNTH_MAT_BASE = -8_000_000_000


def _synthetic_codigo(proveedor_id: int, label: str, base: int) -> int:
    key = f"{proveedor_id}|{label.strip().upper()}"
    h = zlib.crc32(key.encode("utf-8")) & 0x7FFFFFFF
    return base - h


def _normalize_codigo(codigo) -> int | None:
    if codigo is None:
        return None
    s = str(codigo).strip()
    if not s or s.lower() in ("none", "null"):
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def get_or_create_talla(cur, etiqueta: str) -> int:
    etiqueta = str(etiqueta).strip()
    cur.execute(
        "SELECT id FROM talla WHERE talla_etiqueta = %s LIMIT 1",
        (etiqueta,),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])

    talla_valor = int(etiqueta) if etiqueta.isdigit() else None
    cur.execute(
        """
        INSERT INTO talla (talla_valor, talla_etiqueta, sistema, activo)
        VALUES (%s, %s, 'NUMERICO', true)
        RETURNING id
        """,
        (talla_valor, etiqueta),
    )
    row = cur.fetchone()
    return int(row[0])


def get_or_create_referencia(cur, proveedor_id: int, linea_id: int, ref_cod) -> int:
    cur.execute(
        """
        SELECT id FROM referencia
        WHERE proveedor_id = %s AND linea_id = %s AND codigo_proveedor::text = %s
        LIMIT 1
        """,
        (proveedor_id, linea_id, str(ref_cod)),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])

    cur.execute(
        """
        INSERT INTO referencia (proveedor_id, linea_id, codigo_proveedor)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (proveedor_id, linea_id, str(ref_cod)),
    )
    return int(cur.fetchone()[0])


def get_or_create_material(
    cur, proveedor_id: int, codigo, descripcion: str
) -> int | None:
    if not descripcion and codigo is None:
        return None
    desc_clean = (descripcion or "").strip()
    cod = _normalize_codigo(codigo)
    if cod is None and desc_clean:
        cod = _synthetic_codigo(proveedor_id, desc_clean, _SYNTH_MAT_BASE)

    if cod is not None:
        cur.execute(
            """
            SELECT id FROM material
            WHERE proveedor_id = %s AND codigo_proveedor = %s
            LIMIT 1
            """,
            (proveedor_id, cod),
        )
        row = cur.fetchone()
        if row:
            mat_id = int(row[0])
            if desc_clean:
                cur.execute(
                    "UPDATE material SET descripcion = %s WHERE id = %s AND (descripcion IS NULL OR descripcion = '')",
                    (desc_clean, mat_id),
                )
            return mat_id
    if desc_clean:
        cur.execute(
            """
            SELECT id FROM material
            WHERE proveedor_id = %s AND descripcion = %s
            LIMIT 1
            """,
            (proveedor_id, desc_clean),
        )
        row = cur.fetchone()
        if row:
            return int(row[0])
    if cod is None:
        return None
    cur.execute(
        """
        INSERT INTO material (proveedor_id, codigo_proveedor, descripcion)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (proveedor_id, cod, desc_clean or None),
    )
    return int(cur.fetchone()[0])


def get_or_create_color(cur, proveedor_id: int, codigo, nombre: str) -> int | None:
    if not nombre and codigo is None:
        return None
    nom_clean = (nombre or "").strip()
    cod = _normalize_codigo(codigo)
    if cod is None and nom_clean:
        cod = _synthetic_codigo(proveedor_id, nom_clean, _SYNTH_COLOR_BASE)

    if cod is not None:
        cur.execute(
            """
            SELECT id FROM color
            WHERE proveedor_id = %s AND codigo_proveedor = %s
            LIMIT 1
            """,
            (proveedor_id, cod),
        )
        row = cur.fetchone()
        if row:
            return int(row[0])
    if nom_clean:
        cur.execute(
            """
            SELECT id FROM color
            WHERE proveedor_id = %s AND nombre = %s
            LIMIT 1
            """,
            (proveedor_id, nom_clean),
        )
        row = cur.fetchone()
        if row:
            return int(row[0])
    if cod is None:
        return None
    cur.execute(
        """
        INSERT INTO color (proveedor_id, codigo_proveedor, nombre)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (proveedor_id, cod, nom_clean or None),
    )
    return int(cur.fetchone()[0])


def get_or_insert_combinacion(
    cur,
    linea_id: int,
    ref_id: int,
    mat_id: int,
    col_id: int,
    talla_id: int,
) -> int:
    cur.execute(
        """
        SELECT id FROM combinacion
        WHERE linea_id = %s AND referencia_id = %s
          AND material_id = %s AND color_id = %s AND talla_id = %s
        LIMIT 1
        """,
        (linea_id, ref_id, mat_id, col_id, talla_id),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])

    cur.execute(
        """
        INSERT INTO combinacion (
            linea_id, referencia_id, material_id, color_id, talla_id, activo_web
        )
        VALUES (%s, %s, %s, %s, %s, false)
        RETURNING id
        """,
        (linea_id, ref_id, mat_id, col_id, talla_id),
    )
    return int(cur.fetchone()[0])


def main() -> bool:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pp-id", type=int, required=True)
    parser.add_argument("--yes", action="store_true", help="Ejecutar escrituras")
    parser.add_argument("--dry-run", action="store_true", help="Solo simular (default)")
    args = parser.parse_args()
    dry_run = not args.yes

    db_url = _db_url()
    if not db_url:
        print("[ERROR] DATABASE_URL no configurada (secrets.toml o .env)")
        return False

    pp_id = args.pp_id
    print("=" * 80)
    print(f"BACKFILL COMBINACION desde PPD (pp_id={pp_id})")
    print("MODE:", "DRY RUN" if dry_run else "EXECUTE")
    print("=" * 80)

    conn = psycopg2.connect(db_url)
    conn.autocommit = dry_run
    cur = conn.cursor()

    cur.execute(
        """
        SELECT pp.id, pp.numero_registro, pp.proveedor_importacion_id
        FROM pedido_proveedor pp
        WHERE pp.id = %s
        """,
        (pp_id,),
    )
    pp_row = cur.fetchone()
    if not pp_row:
        print(f"[ERROR] PP {pp_id} not found")
        return False

    _, pp_nro, proveedor_id = pp_row
    print(f"[1] PP: {pp_nro} proveedor_id={proveedor_id}")

    cur.execute(
        """
        SELECT
            ppd.id, ppd.linea, ppd.referencia,
            ppd.material_code, ppd.id_material, ppd.descp_material,
            ppd.color_code, ppd.id_color, ppd.descp_color,
            ppd.grades_json
        FROM pedido_proveedor_detalle ppd
        WHERE ppd.pedido_proveedor_id = %s
        """,
        (pp_id,),
    )
    ppd_rows = cur.fetchall()
    print(f"[2] PPD rows: {len(ppd_rows)}")

    stats = {
        "combinaciones_nuevas": 0,
        "combinaciones_existentes": 0,
        "tallas_nuevas": 0,
        "referencias_nuevas": 0,
        "colores_sinteticos": 0,
        "errores": [],
    }

    for (
        ppd_id,
        linea_cod,
        ref_cod,
        mat_code,
        mat_cod,
        descp_material,
        col_code,
        col_cod,
        descp_color,
        grades_json,
    ) in ppd_rows:
        if not dry_run:
            cur.execute("SAVEPOINT sp_ppd")
        try:
            mat_src = mat_code if mat_code is not None else mat_cod
            col_src = col_code if col_code is not None else col_cod
            cur.execute(
                """
                SELECT l.id FROM linea l
                WHERE l.codigo_proveedor::text = %s AND l.proveedor_id = %s
                LIMIT 1
                """,
                (str(linea_cod), proveedor_id),
            )
            l_row = cur.fetchone()
            if not l_row:
                stats["errores"].append(f"ppd_id={ppd_id}: linea {linea_cod} no encontrada")
                continue
            linea_id = int(l_row[0])

            if not grades_json:
                continue
            grades = (
                json.loads(grades_json)
                if isinstance(grades_json, str)
                else grades_json
            ) or {}

            col_sin_codigo = (
                _normalize_codigo(col_src) is None and bool((descp_color or "").strip())
            )

            for talla_str, qty in grades.items():
                if int(qty or 0) <= 0:
                    continue
                etiqueta = str(talla_str).strip()

                if dry_run:
                    cur.execute(
                        "SELECT id FROM talla WHERE talla_etiqueta = %s LIMIT 1",
                        (etiqueta,),
                    )
                    if not cur.fetchone():
                        stats["tallas_nuevas"] += 1
                    cur.execute(
                        """
                        SELECT c.id
                        FROM combinacion c
                        JOIN referencia r ON r.id = c.referencia_id
                        JOIN material mat ON mat.id = c.material_id
                        JOIN color col ON col.id = c.color_id
                        JOIN talla tl ON tl.id = c.talla_id
                        WHERE c.linea_id = %s
                          AND r.codigo_proveedor::text = %s
                          AND mat.descripcion = %s
                          AND col.nombre = %s
                          AND tl.talla_etiqueta = %s
                        LIMIT 1
                        """,
                        (
                            linea_id,
                            str(ref_cod),
                            (descp_material or "").strip(),
                            (descp_color or "").strip(),
                            etiqueta,
                        ),
                    )
                    if cur.fetchone():
                        stats["combinaciones_existentes"] += 1
                    else:
                        stats["combinaciones_nuevas"] += 1
                    continue

                cur.execute(
                    "SELECT id FROM talla WHERE talla_etiqueta = %s LIMIT 1",
                    (etiqueta,),
                )
                talla_existed = bool(cur.fetchone())
                talla_id = get_or_create_talla(cur, etiqueta)
                if not talla_existed:
                    stats["tallas_nuevas"] += 1

                cur.execute(
                    """
                    SELECT id FROM referencia
                    WHERE proveedor_id = %s AND linea_id = %s
                      AND codigo_proveedor::text = %s
                    LIMIT 1
                    """,
                    (proveedor_id, linea_id, str(ref_cod)),
                )
                ref_existed = bool(cur.fetchone())
                ref_id = get_or_create_referencia(
                    cur, proveedor_id, linea_id, ref_cod
                )
                if not ref_existed:
                    stats["referencias_nuevas"] += 1

                if col_sin_codigo:
                    stats["colores_sinteticos"] += 1
                    col_sin_codigo = False
                mat_id = get_or_create_material(
                    cur, proveedor_id, mat_src, descp_material or ""
                )
                col_id = get_or_create_color(
                    cur, proveedor_id, col_src, descp_color or ""
                )
                if mat_id is None or col_id is None:
                    stats["errores"].append(
                        f"ppd_id={ppd_id} talla={etiqueta}: material/color faltante"
                    )
                    continue

                cur.execute(
                    """
                    SELECT id FROM combinacion
                    WHERE linea_id = %s AND referencia_id = %s
                      AND material_id = %s AND color_id = %s AND talla_id = %s
                    LIMIT 1
                    """,
                    (linea_id, ref_id, mat_id, col_id, talla_id),
                )
                existed = bool(cur.fetchone())
                get_or_insert_combinacion(
                    cur, linea_id, ref_id, mat_id, col_id, talla_id
                )
                if existed:
                    stats["combinaciones_existentes"] += 1
                else:
                    stats["combinaciones_nuevas"] += 1

            if not dry_run:
                cur.execute("RELEASE SAVEPOINT sp_ppd")

        except Exception as e:
            if not dry_run:
                cur.execute("ROLLBACK TO SAVEPOINT sp_ppd")
            stats["errores"].append(f"ppd_id={ppd_id}: {e}")

    print()
    print("STATS")
    print(f"  combinaciones nuevas:     {stats['combinaciones_nuevas']}")
    print(f"  combinaciones existentes: {stats['combinaciones_existentes']}")
    print(f"  tallas nuevas:            {stats['tallas_nuevas']}")
    print(f"  referencias nuevas:       {stats['referencias_nuevas']}")
    print(f"  colores cod. sintético:   {stats['colores_sinteticos']}")
    print(f"  errores:                  {len(stats['errores'])}")
    for err in stats["errores"][:10]:
        print(f"    - {err}")

    if not dry_run:
        conn.commit()
        print("\n[OK] Transaction committed")
    else:
        print("\n[DRY RUN] Sin cambios")

    cur.close()
    conn.close()
    return len(stats["errores"]) == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
