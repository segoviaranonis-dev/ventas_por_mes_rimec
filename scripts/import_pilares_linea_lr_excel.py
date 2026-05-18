"""
Importa pilares linea + referencia + linea_referencia desde dos Excel.

Arquitectura (2026-05):
  · El caso comercial NO vive en linea.caso_id — solo en precio_evento / precio_evento_caso.
  · Este script NO escribe caso_id en linea.

Archivos:
  linea.xlsx — LINHA, marca (código + nombre), género (código + descripción)
  linea_referencia.xlsx — línea, referencia, estilo, tipo_1 (códigos + descripciones)

Uso:
  python scripts/import_pilares_linea_lr_excel.py
  python scripts/import_pilares_linea_lr_excel.py --dry-run
  python scripts/import_pilares_linea_lr_excel.py --linea "C:\\...\\linea.xlsx" --lr "C:\\...\\linea_referencia.xlsx"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.database import engine  # noqa: E402
from scripts.lib.import_heartbeat import (  # noqa: E402
    start_import_heartbeat,
    stop_import_heartbeat,
)
from modules.rimec_engine.ley_genero import (  # noqa: E402
    genero_codigo_por_marca,
    lookup_genero_id,
    resolver_genero_id_por_marca,
)

DEFAULT_LINEA = Path(r"C:\Users\hecto\Downloads\hasta el 15052026\linea.xlsx")
DEFAULT_LR = Path(r"C:\Users\hecto\Downloads\hasta el 15052026\linea_referencia.xlsx")
DEFAULT_PROVEEDOR = 654


def norm_col(s: str) -> str:
    return "".join(c for c in str(s).strip().lower() if c.isalnum() or c == "_")


def to_int(v) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        f = float(str(v).strip().replace(",", "."))
        if f != f:
            return None
        return int(f)
    except (ValueError, TypeError):
        return None


def to_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none", "") else s


def rename_linea_df(df: pd.DataFrame) -> pd.DataFrame:
    m = {}
    for c in df.columns:
        n = norm_col(c)
        if n in ("linha", "linea", "codigo_linea", "codigo_proveedor"):
            m[c] = "linea"
        elif "codigo" in n and "marca" in n:
            m[c] = "marca_codigo"
        elif "descripcion" in n and "marca" in n:
            m[c] = "marca_nombre"
        elif "codigo" in n and "genero" in n:
            m[c] = "genero_codigo"
        elif "descripcion" in n and "genero" in n:
            m[c] = "genero_nombre"
    return df.rename(columns=m)


def rename_lr_df(df: pd.DataFrame) -> pd.DataFrame:
    m = {}
    for c in df.columns:
        n = norm_col(c)
        if n in ("linea", "linha"):
            m[c] = "linea"
        elif n in ("referencia", "ref"):
            m[c] = "referencia"
        elif "codigo" in n and "estilo" in n:
            m[c] = "estilo_codigo"
        elif n == "estilo" or ("grupo" in n and "estilo" in n):
            m[c] = "estilo_nombre"
        elif "codigo" in n and "tipo" in n:
            m[c] = "tipo1_codigo"
        elif "descripcion" in n and "tipo" in n:
            m[c] = "tipo1_nombre"
    return df.rename(columns=m)


def _proveedor_codigo(conn, proveedor_id: int) -> str | None:
    row = conn.execute(
        text(
            "SELECT codigo::text FROM proveedor_importacion WHERE id = :p LIMIT 1"
        ),
        {"p": proveedor_id},
    ).fetchone()
    return str(row[0]).strip() if row and row[0] is not None else None


def _resolve_marca_id(conn, codigo, nombre: str) -> int | None:
    cid = to_int(codigo)
    nom = to_str(nombre).upper()
    if cid is not None:
        row = conn.execute(
            text("SELECT id_marca FROM marca_v2 WHERE id_marca = :id LIMIT 1"),
            {"id": cid},
        ).fetchone()
        if row:
            return int(row[0])
    if nom:
        row = conn.execute(
            text(
                """
                SELECT id_marca FROM marca_v2
                WHERE upper(btrim(descp_marca)) = :n LIMIT 1
                """
            ),
            {"n": nom},
        ).fetchone()
        if row:
            return int(row[0])
    return None


def _resolve_genero_id(conn, codigo, nombre: str, marca_nombre: str = "") -> int | None:
    cid = to_int(codigo)
    nom = to_str(nombre).upper()
    if cid is not None:
        row = conn.execute(
            text(
                """
                SELECT id FROM genero
                WHERE id = :id AND COALESCE(activo, true) LIMIT 1
                """
            ),
            {"id": cid},
        ).fetchone()
        if row:
            return int(row[0])
    if nom:
        gid = lookup_genero_id(conn, nom)
        if gid:
            return gid
    if marca_nombre:
        ley = genero_codigo_por_marca(marca_nombre)
        if ley:
            return lookup_genero_id(conn, ley)
    return None


def _get_linea_id(conn, proveedor_id: int, cod_linea: int) -> int | None:
    row = conn.execute(
        text(
            """
            SELECT id FROM linea
            WHERE proveedor_id = :p AND codigo_proveedor = :c LIMIT 1
            """
        ),
        {"p": proveedor_id, "c": cod_linea},
    ).fetchone()
    return int(row[0]) if row else None


def _upsert_linea(
    conn,
    proveedor_id: int,
    cod_linea: int,
    marca_id: int | None,
    genero_id: int | None,
) -> int:
    lid = _get_linea_id(conn, proveedor_id, cod_linea)
    if lid is None:
        row = conn.execute(
            text(
                """
                INSERT INTO linea (proveedor_id, codigo_proveedor, marca_id, genero_id, activo)
                VALUES (:p, :c, :m, :g, true)
                RETURNING id
                """
            ),
            {"p": proveedor_id, "c": cod_linea, "m": marca_id, "g": genero_id},
        ).fetchone()
        return int(row[0])
    conn.execute(
        text(
            """
            UPDATE linea
            SET marca_id = COALESCE(:m, marca_id),
                genero_id = COALESCE(:g, genero_id),
                activo = true
            WHERE id = :lid
            """
        ),
        {"m": marca_id, "g": genero_id, "lid": lid},
    )
    return lid


def _upsert_referencia(conn, proveedor_id: int, linea_id: int, cod_ref: int) -> int:
    row = conn.execute(
        text(
            """
            SELECT id FROM referencia
            WHERE proveedor_id = :p AND linea_id = :l AND codigo_proveedor = :r
            LIMIT 1
            """
        ),
        {"p": proveedor_id, "l": linea_id, "r": cod_ref},
    ).fetchone()
    if row:
        return int(row[0])
    row = conn.execute(
        text(
            """
            INSERT INTO referencia (proveedor_id, linea_id, codigo_proveedor)
            VALUES (:p, :l, :r)
            RETURNING id
            """
        ),
        {"p": proveedor_id, "l": linea_id, "r": cod_ref},
    ).fetchone()
    return int(row[0])


def _upsert_maestro_estilo(conn, ge_id: int, nombre: str) -> None:
    conn.execute(
        text(
            """
            INSERT INTO grupo_estilo_v2 (id_grupo_estilo, descp_grupo_estilo)
            VALUES (:id, :d)
            ON CONFLICT (id_grupo_estilo) DO UPDATE
            SET descp_grupo_estilo = EXCLUDED.descp_grupo_estilo
            """
        ),
        {"id": ge_id, "d": nombre[:2000]},
    )


def _upsert_maestro_tipo1(conn, t1_id: int, nombre: str) -> None:
    conn.execute(
        text(
            """
            INSERT INTO tipo_1 (id_tipo_1, descp_tipo_1)
            VALUES (:id, :d)
            ON CONFLICT (id_tipo_1) DO UPDATE
            SET descp_tipo_1 = EXCLUDED.descp_tipo_1
            """
        ),
        {"id": t1_id, "d": nombre[:2000]},
    )


def _lr_has_codigo_cols(conn) -> bool:
    row = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'linea_referencia'
              AND column_name IN (
                  'codigo_proveedor', 'linea_codigo_proveedor', 'referencia_codigo_proveedor'
              )
            """
        )
    ).scalar()
    return int(row or 0) >= 3


def _upsert_linea_referencia(
    conn,
    proveedor_id: int,
    proveedor_cod: str | None,
    linea_id: int,
    ref_id: int,
    linea_cod: int,
    ref_cod: int,
    ge_id: int,
    t1_id: int,
    estilo_txt: str,
    tipo_txt: str,
    *,
    with_codigos: bool,
) -> None:
    if with_codigos:
        sql = """
            INSERT INTO linea_referencia (
                linea_id, referencia_id, proveedor_id,
                codigo_proveedor, linea_codigo_proveedor, referencia_codigo_proveedor,
                grupo_estilo_id, tipo_1_id,
                descp_grupo_estilo, descp_tipo_1, activo
            ) VALUES (
                :lid, :rid, :pid,
                :pcod, :lc, :rc,
                :ge, :t1,
                :dge, :dt1, true
            )
            ON CONFLICT (linea_id, referencia_id) DO UPDATE SET
                proveedor_id = EXCLUDED.proveedor_id,
                codigo_proveedor = EXCLUDED.codigo_proveedor,
                linea_codigo_proveedor = EXCLUDED.linea_codigo_proveedor,
                referencia_codigo_proveedor = EXCLUDED.referencia_codigo_proveedor,
                grupo_estilo_id = EXCLUDED.grupo_estilo_id,
                tipo_1_id = EXCLUDED.tipo_1_id,
                descp_grupo_estilo = EXCLUDED.descp_grupo_estilo,
                descp_tipo_1 = EXCLUDED.descp_tipo_1,
                activo = true
        """
        params = {
            "lid": linea_id,
            "rid": ref_id,
            "pid": proveedor_id,
            "pcod": proveedor_cod,
            "lc": linea_cod,
            "rc": ref_cod,
            "ge": ge_id,
            "t1": t1_id,
            "dge": estilo_txt,
            "dt1": tipo_txt,
        }
    else:
        sql = """
            INSERT INTO linea_referencia (
                linea_id, referencia_id, proveedor_id,
                grupo_estilo_id, tipo_1_id,
                descp_grupo_estilo, descp_tipo_1, activo
            ) VALUES (
                :lid, :rid, :pid,
                :ge, :t1,
                :dge, :dt1, true
            )
            ON CONFLICT (linea_id, referencia_id) DO UPDATE SET
                proveedor_id = EXCLUDED.proveedor_id,
                grupo_estilo_id = EXCLUDED.grupo_estilo_id,
                tipo_1_id = EXCLUDED.tipo_1_id,
                descp_grupo_estilo = EXCLUDED.descp_grupo_estilo,
                descp_tipo_1 = EXCLUDED.descp_tipo_1,
                activo = true
        """
        params = {
            "lid": linea_id,
            "rid": ref_id,
            "pid": proveedor_id,
            "ge": ge_id,
            "t1": t1_id,
            "dge": estilo_txt,
            "dt1": tipo_txt,
        }
    conn.execute(text(sql), params)


def import_linea_file(
    conn,
    path: Path,
    proveedor_id: int,
    status_holder: dict[str, str] | None = None,
) -> dict:
    df = rename_linea_df(pd.read_excel(path, engine="openpyxl"))
    req = {"linea"}
    if req - set(df.columns):
        raise SystemExit(f"linea.xlsx: faltan columnas {req - set(df.columns)}")

    stats = {"lineas": 0, "errores": []}
    n_rows = len(df)
    for i, (_, row) in enumerate(df.iterrows()):
        if status_holder is not None and i > 0 and i % 250 == 0:
            status_holder["msg"] = f"linea.xlsx — fila {i:,}/{n_rows:,} ({stats['lineas']:,} OK)"
        cod = to_int(row.get("linea"))
        if cod is None:
            continue
        marca_nom = to_str(row.get("marca_nombre"))
        mid = _resolve_marca_id(conn, row.get("marca_codigo"), marca_nom)
        gid = _resolve_genero_id(
            conn,
            row.get("genero_codigo"),
            row.get("genero_nombre"),
            marca_nom,
        )
        if mid is None:
            stats["errores"].append(f"Línea {cod}: marca no resuelta ({marca_nom})")
            continue
        if gid is None:
            stats["errores"].append(f"Línea {cod}: género no resuelto")
            continue
        ley_gid = resolver_genero_id_por_marca(conn, marca_nom)
        if ley_gid and ley_gid != gid:
            gid = ley_gid
        _upsert_linea(conn, proveedor_id, cod, mid, gid)
        stats["lineas"] += 1
    return stats


def import_lr_file(
    conn,
    path: Path,
    proveedor_id: int,
    proveedor_cod: str | None,
    *,
    with_codigos: bool,
    status_holder: dict[str, str] | None = None,
) -> dict:
    df = rename_lr_df(pd.read_excel(path, engine="openpyxl"))
    req = {"linea", "referencia", "estilo_codigo", "tipo1_codigo"}
    if req - set(df.columns):
        raise SystemExit(f"linea_referencia.xlsx: faltan columnas {req - set(df.columns)}")

    stats = {"lr": 0, "errores": []}
    n_rows = len(df)
    for i, (_, row) in enumerate(df.iterrows()):
        if status_holder is not None and i > 0 and i % 500 == 0:
            status_holder["msg"] = (
                f"linea_referencia.xlsx — fila {i:,}/{n_rows:,} ({stats['lr']:,} OK)"
            )
        lc = to_int(row.get("linea"))
        rc = to_int(row.get("referencia"))
        ge = to_int(row.get("estilo_codigo"))
        t1 = to_int(row.get("tipo1_codigo"))
        if None in (lc, rc, ge, t1):
            continue
        dge = to_str(row.get("estilo_nombre")) or f"Estilo {ge}"
        dt1 = to_str(row.get("tipo1_nombre")) or f"Tipo {t1}"

        _upsert_maestro_estilo(conn, ge, dge)
        _upsert_maestro_tipo1(conn, t1, dt1)

        linea_id = _get_linea_id(conn, proveedor_id, lc)
        if linea_id is None:
            stats["errores"].append(
                f"L+R {lc}-{rc}: línea {lc} no existe — importá linea.xlsx primero"
            )
            continue
        ref_id = _upsert_referencia(conn, proveedor_id, linea_id, rc)
        _upsert_linea_referencia(
            conn,
            proveedor_id,
            proveedor_cod,
            linea_id,
            ref_id,
            lc,
            rc,
            ge,
            t1,
            dge,
            dt1,
            with_codigos=with_codigos,
        )
        stats["lr"] += 1
    return stats


def run_import_pilares(
    linea_path: Path,
    lr_path: Path,
    proveedor_id: int,
    *,
    dry_run: bool = False,
    log: callable | None = print,
) -> dict:
    """
    Importa linea.xlsx + linea_referencia.xlsx.
    · linea: marca_id, genero_id (NO caso_id, NO grupo_estilo_id obligatorio).
    · linea_referencia: grupo_estilo_id, tipo_1_id (fuente canónica de estilo para filtros web).
    """
    _log = log or (lambda *_a, **_k: None)
    if not linea_path.is_file():
        raise FileNotFoundError(f"No existe: {linea_path}")
    if not lr_path.is_file():
        raise FileNotFoundError(f"No existe: {lr_path}")

    _log("Caso comercial: solo en precio_evento / biblioteca — este import NO escribe linea.caso_id.")

    if dry_run:
        df_l = rename_linea_df(pd.read_excel(linea_path, engine="openpyxl"))
        df_r = rename_lr_df(pd.read_excel(lr_path, engine="openpyxl"))
        return {
            "dry_run": True,
            "linea_filas": len(df_l),
            "lr_filas": len(df_r),
            "linea_cols": list(df_l.columns),
            "lr_cols": list(df_r.columns),
            "lineas": 0,
            "lr": 0,
            "errores_linea": [],
            "errores_lr": [],
        }

    pid = int(proveedor_id)
    estado = {"msg": "preparando import"}
    stop_hb, hb_thread = start_import_heartbeat(lambda: estado["msg"], interval_sec=60)
    st_l: dict = {"lineas": 0, "errores": []}
    st_lr: dict = {"lr": 0, "errores": []}
    try:
        estado["msg"] = "conectando a Supabase…"
        with engine.begin() as conn:
            pcod = _proveedor_codigo(conn, pid)
            with_cod = _lr_has_codigo_cols(conn)
            if not with_cod:
                _log(
                    "AVISO: migración 042 pendiente — codigos denormalizados en linea_referencia."
                )

            estado["msg"] = f"importando {linea_path.name}"
            _log(f"1/2 {linea_path.name} …")
            st_l = import_linea_file(conn, linea_path, pid, status_holder=estado)
            for e in st_l["errores"]:
                _log(f"   línea: {e}")

            estado["msg"] = f"importando {lr_path.name}"
            _log(f"2/2 {lr_path.name} …")
            st_lr = import_lr_file(
                conn, lr_path, pid, pcod, with_codigos=with_cod, status_holder=estado
            )
            for e in st_lr["errores"]:
                _log(f"   L+R: {e}")
    finally:
        stop_import_heartbeat(stop_hb, hb_thread)

    return {
        "dry_run": False,
        "lineas": int(st_l.get("lineas", 0)),
        "lr": int(st_lr.get("lr", 0)),
        "errores_linea": list(st_l.get("errores") or []),
        "errores_lr": list(st_lr.get("errores") or []),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Import pilares linea + linea_referencia")
    ap.add_argument("--linea", type=Path, default=DEFAULT_LINEA)
    ap.add_argument("--lr", type=Path, default=DEFAULT_LR)
    ap.add_argument("--proveedor-id", type=int, default=DEFAULT_PROVEEDOR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        out = run_import_pilares(
            args.linea, args.lr, int(args.proveedor_id), dry_run=True, log=print
        )
        print(f"linea: {out['linea_filas']} filas | {out['linea_cols']}")
        print(f"lr: {out['lr_filas']} filas | {out['lr_cols']}")
        return

    out = run_import_pilares(args.linea, args.lr, int(args.proveedor_id), log=print)
    print(f"\nListo — líneas: {out['lineas']:,} | L+R: {out['lr']:,}")


if __name__ == "__main__":
    main()
