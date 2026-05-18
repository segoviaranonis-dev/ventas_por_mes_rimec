#!/usr/bin/env python3
"""
Auditoria proforma Excel vs parser oficial vs pedido_proveedor_detalle.

Objetivo: encontrar causa RAIZ de duplicados (ej. 7320/239 con 8 filas en BD).
No modifica datos. Usa parse_proforma() del modulo PP (misma logica que Nexus).

Uso:
  python scripts/auditar_proforma_excel_pp.py "C:\\Users\\hecto\\Downloads\\faturaProforma_7447_2026.xlsx SIN DESC.xlsx"
  python scripts/auditar_proforma_excel_pp.py --linea 7320 --ref 239
  python scripts/auditar_proforma_excel_pp.py archivo.xlsx --sin-db
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pandas as pd  # noqa: E402

from modules.pedido_proveedor.logic import parse_proforma  # noqa: E402


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


def _grades_key(g) -> str:
    if g is None or (isinstance(g, float) and pd.isna(g)):
        return "{}"
    if isinstance(g, str):
        try:
            g = json.loads(g)
        except Exception:
            return g.strip()
    if isinstance(g, dict):
        return json.dumps(g, sort_keys=True, ensure_ascii=False)
    return str(g)


def _mol_key(row: dict) -> str:
    """Clave canonica molécula importadora: linea + ref + material + color + curva."""
    return "|".join([
        str(row.get("linea_cod") or row.get("linea") or "").strip(),
        str(row.get("ref_cod") or row.get("referencia") or "").strip(),
        str(row.get("material_code") or "").strip(),
        str(row.get("color_code") or "").strip(),
        _grades_key(row.get("grades_json")),
    ])


def _color_key(row: dict) -> str:
    return "|".join([
        str(row.get("linea_cod") or row.get("linea") or "").strip(),
        str(row.get("ref_cod") or row.get("referencia") or "").strip(),
        str(row.get("material_code") or "").strip(),
        str(row.get("color_code") or "").strip(),
    ])


def _print_dupes(title: str, rows: list[dict], key_fn) -> None:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[key_fn(r)].append(r)
    dupes = {k: v for k, v in buckets.items() if len(v) > 1}
    print(f"\n--- {title} ---")
    print(f"Filas totales: {len(rows)} | Claves unicas: {len(buckets)} | Claves duplicadas: {len(dupes)}")
    if not dupes:
        print("  (sin duplicados por esta clave)")
        return
    for k, group in sorted(dupes.items(), key=lambda x: -len(x[1]))[:20]:
        parts = k.split("|")
        label = f"linea={parts[0]} ref={parts[1]} mat={parts[2]} col={parts[3]}"
        if len(parts) > 4:
            label += f" grades={parts[4][:60]}..."
        print(f"\n  DUPLICADO x{len(group)}: {label}")
        for g in group:
            item = g.get("item", g.get("fila_origen_f9", g.get("id", "?")))
            boxes = g.get("boxes", g.get("cantidad_cajas", "?"))
            pairs = g.get("pairs", g.get("cantidad_pares", "?"))
            color = g.get("color", g.get("descp_color", ""))
            print(f"    item/fila={item} boxes={boxes} pairs={pairs} color={color}")


def _raw_excel_items(path: Path, linea: str | None, ref: str | None) -> list[dict]:
    """Filas crudas del Excel con ITEM numerico (sin pasar por logica de tallas)."""
    try:
        df = pd.read_excel(path, header=None, engine="openpyxl")
    except Exception as e:
        print(f"[RAW] No se pudo leer Excel: {e}")
        return []
    out = []
    for i in range(len(df)):
        row = df.iloc[i]
        # buscar columna ITEM (heuristica: fila con STYLE e ITEM en cabecera cercana)
        item = row.iloc[0] if len(row) else None
        try:
            item_n = int(float(item))
        except (TypeError, ValueError):
            continue
        style = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else ""
        if "." not in style and linea:
            continue
        linea_cod, ref_cod = "", ""
        if "." in style:
            a, _, b = style.partition(".")
            linea_cod, ref_cod = a.strip(), b.strip()
        if linea and linea_cod != linea:
            continue
        if ref and ref_cod != ref:
            continue
        boxes = 0
        pairs = 0
        try:
            boxes = int(float(row.iloc[10])) if len(row) > 10 else 0
        except (TypeError, ValueError):
            pass
        try:
            pairs = int(float(row.iloc[11])) if len(row) > 11 else 0
        except (TypeError, ValueError):
            pass
        out.append({
            "excel_row": i + 1,
            "item": item_n,
            "style_code": style,
            "linea_cod": linea_cod,
            "ref_cod": ref_cod,
            "material_code": str(int(float(row.iloc[4]))) if len(row) > 4 and pd.notna(row.iloc[4]) else "",
            "color_code": str(int(float(row.iloc[6]))) if len(row) > 6 and pd.notna(row.iloc[6]) else "",
            "color": str(row.iloc[7]).strip() if len(row) > 7 else "",
            "boxes": boxes,
            "pairs": pairs,
        })
    return out


def _fetch_ppd(linea: str, ref: str, proforma_hint: str | None) -> list[dict]:
    import psycopg2

    url = _db_url()
    if not url:
        return []
    # psycopg2 needs postgres:// not postgresql+psycopg2://
    dsn = url.replace("postgresql+psycopg2://", "postgres://").replace(
        "postgresql://", "postgres://"
    )
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    sql = """
        SELECT ppd.id, pp.numero_registro, pp.numero_proforma,
               ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code,
               ppd.descp_color, ppd.cantidad_cajas, ppd.cantidad_pares,
               ppd.grades_json::text, ppd.fila_origen_f9
        FROM pedido_proveedor_detalle ppd
        JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        WHERE ppd.linea = %s AND ppd.referencia = %s
          AND pp.estado IN ('ABIERTO', 'ENVIADO')
    """
    params: list = [linea, ref]
    if proforma_hint:
        sql += " AND (pp.numero_proforma ILIKE %s OR pp.numero_proforma ILIKE %s)"
        params.extend([f"%{proforma_hint}%", f"%{proforma_hint.replace('-', '')}%"])
    sql += " ORDER BY ppd.id"
    cur.execute(sql, params)
    rows = []
    for r in cur.fetchall():
        try:
            gj = json.loads(r[10]) if r[10] else {}
        except Exception:
            gj = {}
        rows.append({
            "id": r[0],
            "pp_nro": r[1],
            "proforma": r[2],
            "linea": r[3],
            "referencia": r[4],
            "material_code": str(r[5] or ""),
            "color_code": str(r[6] or ""),
            "descp_color": r[7],
            "cantidad_cajas": r[8],
            "cantidad_pares": r[9],
            "grades_json": gj,
            "fila_origen_f9": r[11],
            "linea_cod": r[3],
            "ref_cod": r[4],
        })
    cur.close()
    conn.close()
    return rows


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Auditar proforma Excel vs PP vs BD")
    ap.add_argument(
        "excel",
        nargs="?",
        default=r"C:\Users\hecto\Downloads\faturaProforma_7447_2026.xlsx SIN DESC.xlsx",
        help="Ruta al .xlsx de fatura proforma",
    )
    ap.add_argument("--linea", default="7320", help="Linea a focalizar (ej. 7320)")
    ap.add_argument("--ref", default="239", help="Referencia a focalizar (ej. 239)")
    ap.add_argument("--proforma", default="", help="Filtro proforma en BD (ej. 7441 o 7447)")
    ap.add_argument("--sin-db", action="store_true", help="Solo Excel + parser, sin Supabase")
    args = ap.parse_args()

    path = Path(args.excel)
    print("=" * 72)
    print("AUDITORIA PROFORMA — normalizacion molécula (linea+ref+material+color+grades)")
    print("=" * 72)
    print(f"Archivo: {path}")
    print(f"Existe:  {path.is_file()}")
    if not path.is_file():
        print("\n[ERROR] No se encuentra el archivo. Copialo o pasa la ruta correcta.")
        return 1

    raw = path.read_bytes()
    df, total_pares, err = parse_proforma(raw)
    if err:
        print(f"\n[ERROR] parse_proforma: {err}")
        return 1

    print(f"\n[OK] Parser oficial: {len(df)} filas | {total_pares:,} pares totales")

    parsed = df.to_dict("records")
    foco = [r for r in parsed if str(r.get("linea_cod")) == args.linea and str(r.get("ref_cod")) == args.ref]
    print(f"\nFoco {args.linea}/{args.ref}: {len(foco)} filas tras parse_proforma")

    _print_dupes("DUPLICADOS EN PARSEO (clave molécula completa)", parsed, _mol_key)
    _print_dupes("DUPLICADOS EN PARSEO (solo color, sin grades)", parsed, _color_key)

    if foco:
        _print_dupes(f"FOCO {args.linea}/{args.ref} — molécula", foco, _mol_key)
        print(f"\nDetalle foco parser ({len(foco)} filas):")
        print("item | boxes | pairs | mat | color_code | color | grade_range")
        for r in foco:
            gj = r.get("grades_json") or {}
            print(
                f"{r.get('item','?'):>4} | {r.get('boxes',0):>5} | {r.get('pairs',0):>5} | "
                f"{r.get('material_code',''):>6} | {r.get('color_code',''):>10} | "
                f"{str(r.get('color',''))[:14]:14} | {r.get('grade_range','')}"
            )
            print(f"       grades_json: {_grades_key(gj)}")

    raw_rows = _raw_excel_items(path, args.linea, args.ref)
    print(f"\n[RAW Excel] Filas con ITEM numerico y style {args.linea}.{args.ref}: {len(raw_rows)}")
    if raw_rows:
        c_boxes = Counter(r["boxes"] for r in raw_rows)
        c_pairs = Counter(r["pairs"] for r in raw_rows)
        print(f"  Distribucion BOXES en Excel (col K): {dict(c_boxes)}")
        print(f"  Distribucion PAIRS en Excel (col L): {dict(c_pairs)}")
        for r in raw_rows:
            print(
                f"  fila_excel={r['excel_row']} item={r['item']} boxes={r['boxes']} "
                f"pairs={r['pairs']} color={r['color']} code={r['color_code']}"
            )

    # Comparacion Excel raw vs parser
    if raw_rows and foco:
        print("\n--- COMPARACION RAW vs PARSER ---")
        if len(raw_rows) == len(foco):
            print(f"  Misma cantidad de filas: {len(raw_rows)}")
        else:
            print(f"  DISTINTO: Excel raw ITEM filas={len(raw_rows)} | parser={len(foco)}")
            print("  -> El parser puede estar fusionando/separando filas (revisar filas separadoras de tallas)")

    if args.sin_db:
        print("\n(--sin-db: no se consulto Supabase)")
        _veredicto(len(foco), raw_rows, None)
        return 0

    hint = args.proforma or "744"
    ppd = _fetch_ppd(args.linea, args.ref, hint if hint else None)
    print(f"\n[BD] pedido_proveedor_detalle {args.linea}/{args.ref}: {len(ppd)} filas")
    if ppd:
        proformas = sorted({str(p.get("proforma") or "") for p in ppd})
        print(f"  Proformas en BD: {proformas}")
        _print_dupes("DUPLICADOS EN BD (molécula)", ppd, _mol_key)
        print("\nDetalle BD:")
        for p in ppd:
            print(
                f"  id={p['id']} pp={p['pp_nro']} proforma={p['proforma']} "
                f"cajas={p['cantidad_cajas']} pares={p['cantidad_pares']} "
                f"color={p['descp_color']} fila_f9={p.get('fila_origen_f9')}"
            )
            print(f"    grades: {_grades_key(p.get('grades_json'))}")

    _veredicto(len(foco), raw_rows, ppd, len(parsed))
    return 0


def _veredicto(n_foco: int, raw_rows: list, ppd: list | None, n_parsed: int | None = None) -> None:
    print("\n" + "=" * 72)
    print("VEREDICTO (causa raiz)")
    print("=" * 72)
    n_ppd = len(ppd) if ppd is not None else None
    n_raw = len(raw_rows)

    if n_raw > 0 and n_foco == n_raw and (n_ppd is None or n_ppd == n_foco):
        if n_foco > 1:
            print(
                "El EXCEL trae varias filas ITEM con cajas>0 para el mismo modelo/color/curva.\n"
                "No es bug del catalogo web: el importador persiste lo que el Excel declara.\n"
                "Normalizacion: 1 molécula = 1 fila en proforma OR consolidar al importar."
            )
        else:
            print("Excel y parser coherentes con 1 fila para el foco.")
    elif n_ppd is not None and n_ppd > n_foco and n_foco <= 1:
        print(
            f"BD tiene {n_ppd} filas pero el Excel auditado solo {n_foco} para el foco.\n"
            "Posible: otro archivo de proforma se importo (ej. 7441 vs 7447), o reimport doble.\n"
            "Revisar numero_proforma en PP y fila_origen_f9."
        )
    elif n_ppd is not None and n_ppd > n_foco > 1:
        print(
            f"Parser produce {n_foco} filas; BD tiene {n_ppd}.\n"
            "Causa probable: CARGA DUPLICADA (boton proforma 2+ veces) sin vaciar ppd antes."
        )
    elif n_foco > 1 and n_raw <= 1:
        print(
            "Parser genera mas filas que ITEM visibles en Excel raw.\n"
            "Causa probable: filas SEPARADORAS de tallas o logica parse_proforma."
        )
    else:
        print("Revisar tablas arriba. Caso no clasificado automaticamente.")

    if n_parsed and n_foco and n_parsed != n_foco:
        print(f"Nota: total parser={n_parsed}, foco={n_foco}")


if __name__ == "__main__":
    raise SystemExit(main())
