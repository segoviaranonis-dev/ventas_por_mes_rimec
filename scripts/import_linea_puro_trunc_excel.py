"""
Carga PURA del pilar public.linea desde un Excel exclusivo de líneas.

Mapeo estricto (columnas del libro, tolerantes a mayúsculas / espacios en cabecera):
  · LINHA (o LINHA_ID)     → id (PK) y codigo_proveedor (mismo valor numérico)
  · TIPO_MARCA             → marca_id (obligatorio, sin NULL)
  · ID DE GENERO (variantes) → genero_id (obligatorio, sin NULL)
  · MARCA                  → texto; si hay columna descripcion y viene vacía, descripcion = MARCA;
                             si no hay descripcion, descripcion = MARCA (o «Línea {id}» si MARCA vacía)

Operación destructiva:
  TRUNCATE TABLE public.linea RESTART IDENTITY CASCADE
  (borra todas las filas de linea y las filas dependientes en tablas con ON DELETE CASCADE hacia linea).

Uso:
  python scripts/import_linea_puro_trunc_excel.py "C:\\Users\\hecto\\Downloads\\linea.xlsx" \\
      --proveedor-id 654 --i-confirm-truncate-linea-cascade

  python scripts/import_linea_puro_trunc_excel.py ruta.xlsx --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def norm_col(s: str) -> str:
    return "".join(c for c in str(s).strip().lower() if c.isalnum() or c == "_")


def rename_linea_puro(df: pd.DataFrame) -> pd.DataFrame:
    mapping: dict[str, str] = {}
    for c in df.columns:
        n = norm_col(c)
        if n in ("linha", "lnha", "linha_id", "linea", "lnea"):
            mapping[c] = "linha"
        elif n in ("tipo_marca", "tipomarca"):
            mapping[c] = "tipo_marca"
        elif n in ("iddegenero", "id_de_genero", "iddelgenero", "id_genero"):
            mapping[c] = "id_genero"
        elif n == "marca":
            mapping[c] = "marca"
        elif n in ("descripcion", "descricao", "descripcion_linea", "desc_linha"):
            mapping[c] = "descripcion_opt"
    return df.rename(columns=mapping)


def to_int_id(v) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s or s.lower() == "nan":
            return None
    try:
        x = float(v)
        if x != x:
            return None
        return int(x)
    except (TypeError, ValueError):
        return None


def str_cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _sql_text_lit(s: str) -> str:
    t = str(s).replace("'", "''")[:8000]
    return "'" + t + "'"


def main() -> None:
    import tomllib
    from urllib.parse import quote_plus

    ap = argparse.ArgumentParser(description="TRUNCATE CASCADE linea + carga desde linea.xlsx")
    ap.add_argument(
        "xlsx",
        nargs="?",
        default=str(Path.home() / "Downloads" / "linea.xlsx"),
    )
    ap.add_argument("--proveedor-id", type=int, default=654)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo valida Excel y muestra resumen; no toca la base.",
    )
    ap.add_argument(
        "--i-confirm-truncate-linea-cascade",
        action="store_true",
        help="Obligatorio para ejecutar TRUNCATE … CASCADE (operación destructiva).",
    )
    args = ap.parse_args()

    xlsx_path = Path(args.xlsx)
    if not xlsx_path.is_file():
        print(f"ERROR: no existe el archivo: {xlsx_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Leyendo Excel: {xlsx_path}", flush=True)
    df = pd.read_excel(xlsx_path, engine="openpyxl")
    df = rename_linea_puro(df)

    required = {"linha", "tipo_marca", "id_genero", "marca"}
    missing = required - set(df.columns)
    if missing:
        print(
            f"ERROR: faltan columnas obligatorias tras normalizar cabeceras: {sorted(missing)}. "
            f"Columnas vistas: {list(df.columns)}",
            file=sys.stderr,
        )
        sys.exit(1)

    bad: list[str] = []
    by_id: dict[int, dict[str, int | str]] = {}

    for idx, row in df.iterrows():
        lid = to_int_id(row["linha"])
        mid = to_int_id(row["tipo_marca"])
        gid = to_int_id(row["id_genero"])
        marca_txt = str_cell(row["marca"])
        desc_excel = str_cell(row["descripcion_opt"]) if "descripcion_opt" in df.columns else ""

        if lid is None:
            bad.append(f"fila Excel ~{idx + 2}: LINHA inválida ({row['linha']!r})")
            continue
        if mid is None:
            bad.append(f"fila Excel ~{idx + 2}: TIPO_MARCA inválido o ausente ({row['tipo_marca']!r})")
            continue
        if gid is None:
            bad.append(f"fila Excel ~{idx + 2}: ID DE GENERO inválido o ausente ({row['id_genero']!r})")
            continue

        descripcion = desc_excel if desc_excel else marca_txt
        if not descripcion:
            descripcion = f"Línea {lid}"

        by_id[int(lid)] = {
            "id": int(lid),
            "marca_id": int(mid),
            "genero_id": int(gid),
            "descripcion": descripcion[:4000],
        }

    if bad:
        print("ERROR: validación estricta (no se acepta NULL en marca_id ni genero_id):", file=sys.stderr)
        for b in bad[:40]:
            print(f"  - {b}", file=sys.stderr)
        if len(bad) > 40:
            print(f"  … y {len(bad) - 40} más.", file=sys.stderr)
        sys.exit(1)

    if not by_id:
        print("ERROR: no quedó ninguna fila válida tras parsear.", file=sys.stderr)
        sys.exit(1)

    final_rows = [by_id[k] for k in sorted(by_id.keys())]

    print(
        f"OK: {len(df)} filas en hoja → {len(final_rows)} líneas únicas por LINHA (última fila gana). "
        f"proveedor_id={args.proveedor_id}.",
        flush=True,
    )

    if args.dry_run:
        print("DRY-RUN: no se ejecutó TRUNCATE ni INSERT.", flush=True)
        for r in final_rows[:10]:
            print(f"  muestra: {r}", flush=True)
        return

    if not args.i_confirm_truncate_linea_cascade:
        print(
            "ERROR: para ejecutar TRUNCATE TABLE public.linea … CASCADE hay que pasar explícitamente:\n"
            "  --i-confirm-truncate-linea-cascade",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(ROOT / ".streamlit" / "secrets.toml", "rb") as f:
        cfg = tomllib.load(f)
    pg = cfg["postgres"]
    user = quote_plus(str(pg["user"]))
    pw = quote_plus(str(pg["password"]))
    eng = create_engine(
        f"postgresql+psycopg2://{user}:{pw}@{pg['host']}:{pg['port']}/{pg['dbname']}?sslmode=require",
        pool_pre_ping=True,
    )

    pid = int(args.proveedor_id)

    from scripts.lib.import_heartbeat import start_import_heartbeat, stop_import_heartbeat

    print("Latido activo: mensaje cada 60s mientras corre.\n", flush=True)
    estado = {"msg": "preparando TRUNCATE + INSERT linea"}
    stop_hb, hb_thread = start_import_heartbeat(lambda: estado["msg"], interval_sec=60)
    try:
        with eng.begin() as conn:
            estado["msg"] = "TRUNCATE TABLE linea CASCADE"
            print("Ejecutando TRUNCATE TABLE public.linea RESTART IDENTITY CASCADE …", flush=True)
            conn.execute(text("TRUNCATE TABLE public.linea RESTART IDENTITY CASCADE"))

            batch = 200
            for i in range(0, len(final_rows), batch):
                part = final_rows[i : i + batch]
                estado["msg"] = f"INSERT linea — {min(i + batch, len(final_rows)):,}/{len(final_rows):,}"
                vals = ",".join(
                    "({},{},{},{},{},{})".format(
                        int(r["id"]),
                        pid,
                        int(r["id"]),
                        _sql_text_lit(str(r["descripcion"])),
                        int(r["marca_id"]),
                        int(r["genero_id"]),
                    )
                    for r in part
                )
                conn.execute(
                    text(
                        f"""
                        INSERT INTO public.linea (id, proveedor_id, codigo_proveedor, descripcion, marca_id, genero_id)
                        VALUES {vals}
                        """
                    )
                )

            estado["msg"] = "ajuste secuencia linea.id"
            try:
                conn.execute(
                    text(
                        """
                        SELECT setval(
                            pg_get_serial_sequence('public.linea', 'id'),
                            GREATEST(1, COALESCE((SELECT MAX(id) FROM public.linea), 1))
                        )
                        """
                    )
                )
            except Exception:
                pass
    finally:
        stop_import_heartbeat(stop_hb, hb_thread)

    print("OK: COMMIT aplicado (linea truncada y repoblada).", flush=True)

    with eng.connect() as c:
        sample = c.execute(
            text(
                """
                SELECT id, proveedor_id, codigo_proveedor, descripcion, marca_id, genero_id
                FROM public.linea
                ORDER BY id
                LIMIT 10
                """
            )
        ).mappings().all()
        nulls = c.execute(
            text(
                """
                SELECT COUNT(*) AS n
                FROM public.linea
                WHERE marca_id IS NULL OR genero_id IS NULL
                """
            )
        ).scalar()

    print("\n=== Primeros 10 registros en public.linea (orden por id) ===", flush=True)
    for row in sample:
        print(dict(row), flush=True)

    if int(nulls or 0) > 0:
        print(f"ERROR: quedaron {nulls} filas con marca_id o genero_id NULL.", file=sys.stderr)
        sys.exit(1)

    print("\nOK: verificación — cero filas con marca_id o genero_id NULL.", flush=True)
    eng.dispose()


if __name__ == "__main__":
    main()
