#!/usr/bin/env python3
"""Aplica migración 043 (contenedor líneas por evento) en Supabase."""
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

SQL_PATH = ROOT / "migrations" / "043_contenedor_lineas_evento.sql"


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    print(f"Aplicando {SQL_PATH.name} …")
    estado = {"msg": "migración 043 — contenedor líneas por evento"}
    stop_hb, hb_thread = start_import_heartbeat(lambda: estado["msg"], interval_sec=60)
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    finally:
        stop_import_heartbeat(stop_hb, hb_thread)
    print("OK — contenedor de líneas por listado listo.")


if __name__ == "__main__":
    main()
