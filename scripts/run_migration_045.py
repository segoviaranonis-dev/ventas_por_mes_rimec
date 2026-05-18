#!/usr/bin/env python3
"""Aplica migración 045 (línea en varios casos de la misma biblioteca)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import text  # noqa: E402

from core.database import engine  # noqa: E402

SQL_PATH = ROOT / "migrations" / "045_biblioteca_linea_multi_caso.sql"


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    print(f"Aplicando {SQL_PATH.name} …")
    with engine.begin() as conn:
        conn.execute(text(sql))
    print("OK — una línea puede estar en varios casos de la biblioteca.")


if __name__ == "__main__":
    main()
