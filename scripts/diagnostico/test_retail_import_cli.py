#!/usr/bin/env python3
"""
Prueba import Retail desde terminal (sin Streamlit UI).
Uso:
  cd control_central
  python scripts/diagnostico/test_retail_import_cli.py "C:\\ruta\\VENTA y STOCK BZ+RC.xlsx"
  python scripts/diagnostico/test_retail_import_cli.py "archivo.xlsx" --dry-run
  python scripts/diagnostico/test_retail_import_cli.py "archivo.xlsx" --commit
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _engine():
    import tomllib
    from sqlalchemy import create_engine, text

    secrets = ROOT / ".streamlit" / "secrets.toml"
    if not secrets.is_file():
        raise SystemExit("Falta .streamlit/secrets.toml")
    data = tomllib.loads(secrets.read_text(encoding="utf-8"))
    pg = data.get("postgres") or {}
    url = pg.get("DATABASE_URL") or pg.get("url")
    if not url:
        user = pg.get("user")
        password = pg.get("password")
        host = pg.get("host")
        port = pg.get("port", 5432)
        dbname = pg.get("dbname")
        if not all([user, password, host, dbname]):
            raise SystemExit("Falta DATABASE_URL o campos postgres en secrets.toml")
        url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=require"
    eng = create_engine(url, pool_pre_ping=True)
    with eng.connect() as c:
        c.execute(text("SELECT 1"))
    return eng


def main() -> None:
    ap = argparse.ArgumentParser(description="Test import Retail st+vt+RC")
    ap.add_argument("xlsx", type=Path, help="Ruta al Excel")
    ap.add_argument("--dry-run", action="store_true", help="Solo normalizar + FK resolve, sin INSERT")
    ap.add_argument("--commit", action="store_true", help="Import real (reemplazo total)")
    args = ap.parse_args()
    if not args.xlsx.is_file():
        raise SystemExit(f"No existe: {args.xlsx}")

    import importlib

    retail = importlib.import_module("modules.balance_tiendas_retail.st_vt_rc_import")
    fk = importlib.import_module("modules.balance_tiendas_retail.fk_resolve")
    TIPO_V2_CALZADO = fk.TIPO_V2_CALZADO
    TIPO_V2_CONFECCIONES = fk.TIPO_V2_CONFECCIONES
    infer_proveedor_importacion_id = fk.infer_proveedor_importacion_id
    resolve_retail_fks = fk.resolve_retail_fks

    print(f"Build import: {retail.RETAIL_IMPORT_BUILD}")
    with open(args.xlsx, "rb") as f:
        raw, sheet, _meta = retail.read_excel_retail_sheet(f)
    print(f"Hoja: {sheet} | filas raw: {len(raw)}")

    norm, errs = retail.normalize_retail_dataframe(raw)
    diag = retail.diagnose_retail_import(raw, norm)
    ok, reasons = retail.assess_import_gate(norm, errs, diag)
    print(f"Gate import: {'OK' if ok else 'BLOQUEADO'}")
    if reasons:
        for r in reasons:
            print(f"  - {r}")
    if not ok:
        raise SystemExit(2)

    n_calz = int((norm["tipo_v2_id"] == TIPO_V2_CALZADO).sum())
    n_conf = int((norm["tipo_v2_id"] == TIPO_V2_CONFECCIONES).sum())
    print(f"tipo_v2: calzado={n_calz} confecciones={n_conf}")

    eng = _engine()
    from sqlalchemy import text

    with eng.connect() as c:
        provs = c.execute(
            text("SELECT id, codigo, nombre FROM public.proveedor_importacion ORDER BY id")
        ).fetchall()
    print("proveedor_importacion:")
    for p in provs:
        print(f"  id={p[0]} codigo={p[1]!r} nombre={p[2]!r}")

    sub_calz = norm[norm["tipo_v2_id"] == TIPO_V2_CALZADO]
    sub_conf = norm[norm["tipo_v2_id"] == TIPO_V2_CONFECCIONES]
    pid_all = infer_proveedor_importacion_id(eng, norm)
    pid_calz = infer_proveedor_importacion_id(eng, sub_calz) if len(sub_calz) else pid_all
    print(f"infer proveedor (todo el lote): {pid_all}")
    print(f"infer proveedor (solo calzado): {pid_calz}")

    if len(sub_conf):
        sample = sub_conf.head(3)[
            ["excel_tipo_v2", "linea_codigo_proveedor", "referencia_codigo_proveedor", "excel_material_code", "excel_color_code"]
        ]
        print("Muestra confecciones (3 filas):")
        print(sample.to_string(index=False))

    work = norm.copy()
    work["material_id"] = work["excel_material_code"]
    work["color_id"] = work["excel_color_code"]
    print("Resolviendo FKs (pilares)...")
    try:
        resolved, warns = resolve_retail_fks(eng, work)
        print(f"FK resolve OK — {len(warns)} avisos únicos (muestra 3): {warns[:3]}")
        print(
            f"linea_id null: {resolved['linea_id'].isna().sum()} | "
            f"ref null: {resolved['referencia_id'].isna().sum()} | "
            f"conf sin L+R esperado"
        )
        conf_mask = resolved["tipo_v2_id"] == TIPO_V2_CONFECCIONES
        if conf_mask.any():
            csub = resolved.loc[conf_mask, ["linea_id", "referencia_id", "material_id", "color_id"]]
            print(f"Confecciones — linea_id todos null: {csub['linea_id'].isna().all()}")
            print(f"Confecciones — ref_id todos null: {csub['referencia_id'].isna().all()}")
    except Exception as e:
        print(f"FK RESOLVE FALLO: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise SystemExit(3)

    if args.dry_run or not args.commit:
        print("Dry-run terminado (sin INSERT). Para import real: --commit")
        return

    print("INSERT reemplazo total...")
    try:
        bid, n_del, n_ins = retail.insert_batch(
            eng,
            norm,
            batch_label="CLI-TEST",
            archivo_origen=args.xlsx.name,
            excel_sheet=sheet or retail.EXCEL_SHEET_RETAIL,
            created_by="cli-test",
            replace_all=True,
        )
        total = retail.count_all_rows(eng)
        print(f"OK batch={bid[:8]}… deleted={n_del} inserted={n_ins} total_tabla={total}")
    except Exception as e:
        print(f"INSERT FALLO: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise SystemExit(4)


if __name__ == "__main__":
    main()
