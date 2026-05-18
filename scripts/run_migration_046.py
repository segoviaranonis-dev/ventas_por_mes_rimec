#!/usr/bin/env python3
"""Aplica migración 046 (exclusividad línea por biblioteca)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import text  # noqa: E402

from core.database import engine  # noqa: E402

SQL_PATH = ROOT / "migrations" / "046_biblioteca_exclusividad_linea.sql"


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    print(f"Aplicando {SQL_PATH.name} …")
    with engine.begin() as conn:
        conn.execute(text(sql))
    print("OK — una línea solo puede estar en un caso por biblioteca.")


if __name__ == "__main__":
    main()
