"""Ejecuta migration 007 — corrige factura_interna_detalle."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.database import engine
from sqlalchemy import text

SQL = """
ALTER TABLE factura_interna_detalle
  ALTER COLUMN ppd_id DROP NOT NULL;

ALTER TABLE factura_interna_detalle
  ADD COLUMN IF NOT EXISTS precio_neto    NUMERIC,
  ADD COLUMN IF NOT EXISTS linea_snapshot JSONB;
"""

with engine.begin() as conn:
    for stmt in SQL.strip().split(";"):
        s = stmt.strip()
        if s:
            conn.execute(text(s))
            print(f"OK: {s[:60]}...")

print("\nMigración 007 completada.")
