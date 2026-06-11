#!/usr/bin/env python
"""
HOTFIX URGENTE - 2026-06-10 PARTE 2
PP-2026-0012 esta ABIERTO pero sigue vinculado a Compra
Desvincular de compra_legal_pedido
"""

from core.database import engine
from sqlalchemy import text

print("=" * 80)
print("HOTFIX PARTE 2: DESVINCULAR PP-2026-0012 DE COMPRA")
print("=" * 80)

# Paso 1: Ver vinculaciones actuales
print("\n[1/3] Vinculaciones ANTES:")
with engine.connect() as conn:
    vinculaciones = conn.execute(text("""
        SELECT
            clp.id,
            clp.compra_legal_id,
            cl.numero_registro AS cl_numero,
            pp.numero_registro AS pp_numero,
            pp.estado AS pp_estado
        FROM compra_legal_pedido clp
        JOIN compra_legal cl ON cl.id = clp.compra_legal_id
        JOIN pedido_proveedor pp ON pp.id = clp.pedido_proveedor_id
        WHERE pp.numero_registro = 'PP-2026-0012'
    """)).fetchall()

    if not vinculaciones:
        print("[INFO] PP-2026-0012 NO esta vinculado a ninguna compra")
        print("No hay nada que desvincular")
        exit(0)

    for v in vinculaciones:
        print(f"  Vinculacion ID={v[0]}")
        print(f"    CL: {v[2]} (ID={v[1]})")
        print(f"    PP: {v[3]} (estado={v[4]})")

# Paso 2: Desvincular
print("\n[2/3] Desvinculando...")
with engine.begin() as conn:
    result = conn.execute(text("""
        DELETE FROM compra_legal_pedido
        WHERE pedido_proveedor_id = (
            SELECT id FROM pedido_proveedor
            WHERE numero_registro = 'PP-2026-0012'
        )
    """))

    print(f"[OK] Eliminadas {result.rowcount} vinculacion(es)")

# Paso 3: Verificar
print("\n[3/3] Verificacion DESPUES:")
with engine.connect() as conn:
    vinculaciones_despues = conn.execute(text("""
        SELECT COUNT(*) as cnt
        FROM compra_legal_pedido clp
        JOIN pedido_proveedor pp ON pp.id = clp.pedido_proveedor_id
        WHERE pp.numero_registro = 'PP-2026-0012'
    """)).fetchone()

    if vinculaciones_despues[0] == 0:
        print("[OK] PP-2026-0012 ya NO esta vinculado a ninguna compra")
    else:
        print(f"[ERROR] Aun quedan {vinculaciones_despues[0]} vinculaciones")

print("\n" + "=" * 80)
print("HOTFIX PARTE 2 COMPLETADO")
print("=" * 80)
print("\n[OK] PP-2026-0012 desvinculado de Compra")
print("[OK] Ya NO aparecera en modulo Compra")
print("[OK] Estado: ABIERTO, disponible para venta")
print("=" * 80)
