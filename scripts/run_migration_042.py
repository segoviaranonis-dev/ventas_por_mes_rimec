#!/usr/bin/env python3
"""Aplica migración 042 (codigos en linea_referencia) en Supabase."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import text  # noqa: E402

from core.database import engine  # noqa: E402
from scripts.lib.import_heartbeat import (  # noqa: E402
    start_import_heartbeat,
    stop_import_heartbeat,
)

SQL_PATH = ROOT / "migrations" / "042_linea_referencia_codigos_proveedor.sql"


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    print(f"Aplicando {SQL_PATH.name} …")
    print("Latido activo: mensaje cada 60s mientras corre.\n")
    estado = {"msg": "migración 042 — ALTER + backfill linea_referencia"}
    stop_hb, hb_thread = start_import_heartbeat(lambda: estado["msg"], interval_sec=60)
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    finally:
        stop_import_heartbeat(stop_hb, hb_thread)
    print("OK — columnas codigo_proveedor en linea_referencia listas.")
    print("Opcional: python scripts/import_pilares_linea_lr_excel.py  (rellena códigos denormalizados)")


if __name__ == "__main__":
    main()
