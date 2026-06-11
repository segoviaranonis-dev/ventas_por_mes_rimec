#!/usr/bin/env python
"""Buscar PP-2026-0012 en diferentes formatos"""

from core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Buscar con LIKE
    df = conn.execute(text("""
        SELECT
            id,
            numero_registro,
            numero_proforma,
            estado
        FROM public.pedido_proveedor
        WHERE numero_registro LIKE '%0012%'
           OR numero_proforma LIKE '%0012%'
        LIMIT 10
    """)).fetchall()

    print("Resultados con '0012':")
    for row in df:
        print(f"  ID={row[0]}, numero_registro={row[1]}, proforma={row[2]}, estado={row[3]}")

    # Buscar todos los PP de 2026
    df2 = conn.execute(text("""
        SELECT
            id,
            numero_registro,
            numero_proforma,
            estado
        FROM public.pedido_proveedor
        WHERE numero_registro LIKE '2026%'
        ORDER BY numero_registro DESC
        LIMIT 20
    """)).fetchall()

    print("\nUltimos 20 PPs de 2026:")
    for row in df2:
        print(f"  PP-{row[1]} (proforma={row[2]}, estado={row[3]})")
