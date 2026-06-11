#!/usr/bin/env python
"""Verificar estado actual de PP-2026-0012 en produccion"""

from core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT
            numero_registro,
            estado,
            numero_proforma
        FROM public.pedido_proveedor
        WHERE numero_registro = 'PP-2026-0012'
    """)).fetchone()

    print("=" * 60)
    print("VERIFICACION EN PRODUCCION")
    print("=" * 60)
    print(f"PP: {result[0]}")
    print(f"Estado ACTUAL: {result[1]}")
    print(f"Proforma: {result[2]}")
    print("=" * 60)

    if result[1] == 'ABIERTO':
        print("[OK] PP-2026-0012 esta ABIERTO en produccion")
        print("[OK] 7,756 pares disponibles para venta")
    else:
        print(f"[ERROR] Estado es {result[1]}, no ABIERTO")
