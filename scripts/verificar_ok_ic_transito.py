#!/usr/bin/env python3
"""Checklist go/no-go: IC + stock tránsito web RIMEC. Escribe scripts/verificar_ok_ic_transito.log"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from decouple import UndefinedValueError, config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

LOG = ROOT / "scripts" / "verificar_ok_ic_transito.log"
PROV = 654


def _db_url() -> str:
    try:
        u = config("DATABASE_URL")
        if u:
            return u
    except UndefinedValueError:
        pass
    p = ROOT / ".streamlit" / "secrets.toml"
    if p.is_file():
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
    raise SystemExit("DATABASE_URL o secrets.toml [postgres]")


def main() -> None:
    eng = create_engine(_db_url())
    lines: list[str] = []
    stops: list[str] = []
    warns: list[str] = []

    def ok(m: str) -> None:
        lines.append(f"  [OK] {m}")

    def stop(m: str) -> None:
        lines.append(f"  [STOP] {m}")
        stops.append(m)

    def warn(m: str) -> None:
        lines.append(f"  [AVISO] {m}")
        warns.append(m)

    lines.append("")
    lines.append("=" * 60)
    lines.append(f"VERIFICACIÓN IC + TRÁNSITO WEB — {datetime.now():%Y-%m-%d %H:%M:%S}")
    lines.append("=" * 60)

    with eng.connect() as c:
        # Pilares
        lines.append("\n── Pilares (654) ──")
        n_linea = c.execute(
            text("SELECT COUNT(*) FROM linea WHERE proveedor_id=:p"), {"p": PROV}
        ).scalar()
        n_lr = c.execute(
            text("SELECT COUNT(*) FROM linea_referencia WHERE proveedor_id=:p"), {"p": PROV}
        ).scalar()
        ok(f"linea: {n_linea}")
        ok(f"linea_referencia: {n_lr}")
        if int(n_linea or 0) < 100:
            stop("Pocas líneas — completar import pilares.")

        # Listado real
        lines.append("\n── Listado precios (evento 1) ──")
        ev = c.execute(
            text(
                """
                SELECT id, nombre_evento, estado,
                       (SELECT COUNT(*) FROM precio_lista WHERE evento_id = pe.id) AS n_skus
                FROM precio_evento pe ORDER BY id LIMIT 1
                """
            )
        ).mappings().first()
        if not ev:
            stop("No hay precio_evento — cargar listado en Motor.")
        else:
            ok(f"Evento {ev['id']}: {ev['nombre_evento']} | estado={ev['estado']} | SKUs={ev['n_skus']}")
            if str(ev["estado"]).lower() != "cerrado":
                stop(
                    "Evento NO está CERRADO — IC solo lista eventos cerrados. "
                    "Cerrar en Motor Paso 5."
                )
            if int(ev["n_skus"] or 0) < 1:
                stop("precio_lista vacío para el evento.")

        # IC / PP operativo
        lines.append("\n── Operación ──")
        n_ic = c.execute(text("SELECT COUNT(*) FROM intencion_compra")).scalar()
        n_pp = c.execute(text("SELECT COUNT(*) FROM pedido_proveedor")).scalar()
        n_ppd = c.execute(text("SELECT COUNT(*) FROM pedido_proveedor_detalle")).scalar()
        lines.append(f"  IC: {n_ic} | PP: {n_pp} | pp_detalle: {n_ppd}")

        # Vista web
        lines.append("\n── Web RIMEC (v_stock_rimec) ──")
        try:
            n_vs = c.execute(text("SELECT COUNT(*) FROM v_stock_rimec")).scalar()
            ok(f"v_stock_rimec filas: {n_vs}")
            if int(n_ppd or 0) > 0 and int(n_vs or 0) == 0:
                warn("Hay pp_detalle pero vista vacía — ejecutar scripts/fix_v_stock_rimec.py")
        except Exception as e:
            warn(f"v_stock_rimec no accesible: {e}")

        n_comb = c.execute(text("SELECT COUNT(*) FROM combinacion")).scalar()
        if int(n_comb or 0) == 0:
            ok("combinacion=0 es normal antes del primer F9 (web usa pp_detalle)")

        # Migración 042
        has042 = c.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema='public' AND table_name='linea_referencia'
                  AND column_name='codigo_proveedor'
                """
            )
        ).scalar()
        if int(has042 or 0) == 0:
            warn("Migración 042 pendiente (codigo_proveedor en linea_referencia)")

    lines.append("\n── VEREDICTO ──")
    if stops:
        lines.append("  RESULTADO: NO OK — corregir [STOP] antes de IC + tránsito.")
        for s in stops:
            lines.append(f"    · {s}")
    else:
        lines.append("  RESULTADO: OK — puede continuar Intención de Compra y carga tránsito.")
        if warns:
            lines.append("  Avisos (no bloquean):")
            for w in warns:
                lines.append(f"    · {w}")
    lines.append("=" * 60)

    out = "\n".join(lines)
    print(out, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(out + "\n")


if __name__ == "__main__":
    main()
