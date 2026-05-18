#!/usr/bin/env python3
"""
Conteo oficial — Carga real Fase 1 (pilares importadora).

Uso:
  python scripts/carga_real_fase1_conteo.py
  python scripts/carga_real_fase1_conteo.py --proveedor-id 654 --etiqueta ANTES
  python scripts/carga_real_fase1_conteo.py --etiqueta DESPUES_IMPORT

Escribe siempre en scripts/carga_real_conteo.log
"""
from __future__ import annotations

import argparse
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

LOG_PATH = ROOT / "scripts" / "carga_real_conteo.log"
DEFAULT_PROVEEDOR = 654


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
    raise SystemExit("Definí DATABASE_URL o .streamlit/secrets.toml [postgres]")


def _scalar(conn, sql: str, **params) -> int:
    return int(conn.execute(text(sql), params).scalar() or 0)


def recolectar_conteos(conn, proveedor_id: int) -> dict[str, int | str]:
    pid = proveedor_id
    return {
        "linea_total": _scalar(conn, "SELECT COUNT(*) FROM public.linea"),
        "linea_proveedor": _scalar(
            conn,
            "SELECT COUNT(*) FROM public.linea WHERE proveedor_id = :p AND activo IS NOT FALSE",
            p=pid,
        ),
        "referencia_total": _scalar(conn, "SELECT COUNT(*) FROM public.referencia"),
        "referencia_proveedor": _scalar(
            conn,
            "SELECT COUNT(*) FROM public.referencia WHERE proveedor_id = :p AND activo IS NOT FALSE",
            p=pid,
        ),
        "linea_referencia_total": _scalar(
            conn, "SELECT COUNT(*) FROM public.linea_referencia"
        ),
        "linea_referencia_proveedor": _scalar(
            conn,
            "SELECT COUNT(*) FROM public.linea_referencia WHERE proveedor_id = :p",
            p=pid,
        ),
        "pares_lr_distintos": _scalar(
            conn,
            """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT linea_id, referencia_id
                FROM public.linea_referencia
                WHERE proveedor_id = :p
            ) t
            """,
            p=pid,
        ),
        "material_total": _scalar(conn, "SELECT COUNT(*) FROM public.material"),
        "material_activo": _scalar(
            conn,
            "SELECT COUNT(*) FROM public.material WHERE activo IS NOT FALSE",
        ),
        "color_total": _scalar(conn, "SELECT COUNT(*) FROM public.color"),
        "color_activo": _scalar(
            conn,
            "SELECT COUNT(*) FROM public.color WHERE activo IS NOT FALSE",
        ),
        "talla_total": _scalar(conn, "SELECT COUNT(*) FROM public.talla"),
        "combinacion_total": _scalar(conn, "SELECT COUNT(*) FROM public.combinacion"),
        "precio_evento": _scalar(conn, "SELECT COUNT(*) FROM public.precio_evento"),
        "precio_lista": _scalar(conn, "SELECT COUNT(*) FROM public.precio_lista"),
    }


def formatear_reporte(conteos: dict, proveedor_id: int, etiqueta: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "",
        "=" * 62,
        f"CARGA REAL — CONTEO PILARES [{etiqueta}]",
        f"{ts} · proveedor_id = {proveedor_id} (Beira Rio)",
        "=" * 62,
        "",
        "── Solicitado por Dirección ──",
        f"  línea (proveedor {proveedor_id}):     {conteos['linea_proveedor']:,}",
        f"  referencia (proveedor {proveedor_id}): {conteos['referencia_proveedor']:,}",
        f"  línea + referencia (tabla L+R):        {conteos['linea_referencia_proveedor']:,}",
        f"  pares distintos (linea_id, ref_id):    {conteos['pares_lr_distintos']:,}",
        f"  material (catálogo):                   {conteos['material_total']:,}",
        f"  color (catálogo):                      {conteos['color_total']:,}",
        "",
        "── Contexto catálogo global ──",
        f"  línea (total todos proveedores):       {conteos['linea_total']:,}",
        f"  referencia (total):                    {conteos['referencia_total']:,}",
        f"  linea_referencia (total):              {conteos['linea_referencia_total']:,}",
        f"  material activo:                       {conteos['material_activo']:,}",
        f"  color activo:                          {conteos['color_activo']:,}",
        f"  talla (grada / pilar 5):               {conteos['talla_total']:,}",
        f"  combinacion (5 FK):                    {conteos['combinacion_total']:,}",
        "",
        "── Motor de precios (contadores reiniciados) ──",
        f"  precio_evento:                         {conteos['precio_evento']:,}",
        f"  precio_lista:                          {conteos['precio_lista']:,}",
        "",
        "Nota: material/color masivos suelen crecer con F9/proforma;",
        "      Fase 1 Excel carga línea + L+R.",
        "=" * 62,
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Conteo pilares — carga real Fase 1")
    ap.add_argument("--proveedor-id", type=int, default=DEFAULT_PROVEEDOR)
    ap.add_argument("--etiqueta", default="SNAPSHOT", help="ANTES | DESPUES_IMPORT | …")
    args = ap.parse_args()

    engine = create_engine(_db_url())
    with engine.connect() as conn:
        conteos = recolectar_conteos(conn, args.proveedor_id)

    reporte = formatear_reporte(conteos, args.proveedor_id, args.etiqueta)
    print(reporte, flush=True)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(reporte)
        f.write("\n")

    print(f"\nLog append: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    main()
