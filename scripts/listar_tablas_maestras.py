#!/usr/bin/env python3
"""
Listar tablas maestras disponibles
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
              AND (
                table_name LIKE '%genero%'
                OR table_name LIKE '%marca%'
                OR table_name LIKE '%estilo%'
                OR table_name LIKE '%tipo%'
              )
            ORDER BY table_name
        """))

        print("Tablas maestras disponibles:")
        for row in result:
            print(f"  - {row[0]}")

if __name__ == "__main__":
    main()
