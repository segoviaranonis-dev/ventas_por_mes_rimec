"""Comprobaciones de esquema para linea_referencia (migración 042)."""
from __future__ import annotations

from sqlalchemy import text

from core.database import engine

_LR_CODIGOS_CACHE: bool | None = None


def linea_referencia_tiene_codigos_proveedor(conn=None) -> bool:
    """True si existen codigo_proveedor / linea_codigo_proveedor / referencia_codigo_proveedor."""
    global _LR_CODIGOS_CACHE
    if _LR_CODIGOS_CACHE is not None and conn is None:
        return _LR_CODIGOS_CACHE
    q = text(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'linea_referencia'
          AND column_name = 'codigo_proveedor'
        LIMIT 1
        """
    )
    if conn is not None:
        return conn.execute(q).fetchone() is not None
    with engine.connect() as c:
        _LR_CODIGOS_CACHE = c.execute(q).fetchone() is not None
    return _LR_CODIGOS_CACHE


def mensaje_si_falta_migracion_042() -> str | None:
    if linea_referencia_tiene_codigos_proveedor():
        return None
    return (
        "Falta la migración **042** (`codigo_proveedor` en `linea_referencia`). "
        "Ejecutá: `python scripts/run_migration_042.py`"
    )
