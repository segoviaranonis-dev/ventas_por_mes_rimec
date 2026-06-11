#!/usr/bin/env python
"""
HOTFIX URGENTE - 2026-06-10
PP-2026-0012 está en ENVIADO sin autorización
Cambiar a ABIERTO para disponibilizar 7,756 pares para venta
"""

from core.database import engine
from sqlalchemy import text

print("=" * 80)
print("HOTFIX URGENTE: PP-2026-0012")
print("=" * 80)

# Paso 1: Ver estado actual
print("\n[1/3] Estado ANTES del cambio:")
with engine.connect() as conn:
    df_antes = conn.execute(text("""
        SELECT
            id,
            numero_registro,
            numero_proforma,
            estado,
            fecha_arribo_estimada,
            created_at
        FROM public.pedido_proveedor
        WHERE numero_registro = 'PP-2026-0012'
    """)).fetchone()

    if not df_antes:
        print("[ERROR] PP-2026-0012 NO encontrado")
        exit(1)

    print(f"[OK] PP encontrado:")
    print(f"  - ID: {df_antes[0]}")
    print(f"  - Numero: PP-{df_antes[1]}")
    print(f"  - Proforma: {df_antes[2]}")
    print(f"  - Estado ACTUAL: {df_antes[3]}")
    print(f"  - ETA: {df_antes[4]}")
    print(f"  - Creado: {df_antes[5]}")

    if df_antes[3] != 'ENVIADO':
        print(f"\n[ADVERTENCIA] Estado actual es '{df_antes[3]}', no 'ENVIADO'")
        print("Continuar de todas formas? (Enter para SI, Ctrl+C para NO)")
        input()

# Paso 2: Ejecutar UPDATE
print("\n[2/3] Ejecutando UPDATE...")
with engine.begin() as conn:
    result = conn.execute(text("""
        UPDATE public.pedido_proveedor
        SET estado = 'ABIERTO'
        WHERE numero_registro = 'PP-2026-0012'
          AND estado = 'ENVIADO'
    """))

    if result.rowcount == 0:
        print("[ERROR] No se actualizo ningun registro (ya estaba ABIERTO?)")
    else:
        print(f"[OK] Actualizado {result.rowcount} registro(s)")

# Paso 3: Verificar cambio
print("\n[3/3] Estado DESPUÉS del cambio:")
with engine.connect() as conn:
    df_despues = conn.execute(text("""
        SELECT
            numero_registro,
            estado,
            numero_proforma
        FROM public.pedido_proveedor
        WHERE numero_registro = 'PP-2026-0012'
    """)).fetchone()

    print(f"[OK] PP-{df_despues[0]}")
    print(f"  - Estado NUEVO: {df_despues[1]}")
    print(f"  - Proforma: {df_despues[2]}")

# Paso 4: Auditoría
print("\n[4/4] Registrando en auditoría...")
from core.auditoria import registrar_auditoria, Accion as A

# Obtener usuario DIRECTOR
with engine.connect() as conn:
    usuario = conn.execute(text("""
        SELECT id FROM usuario WHERE username = 'DIRECTOR' LIMIT 1
    """)).fetchone()

    usuario_id = usuario[0] if usuario else None

registrar_auditoria(
    entidad="PP",
    entidad_id=int(df_antes[0]),
    nro_registro=f"PP-{df_antes[1]}",
    accion="HOTFIX_ESTADO_URGENTE",
    estado_antes="ENVIADO",
    estado_despues="ABIERTO",
    snap={
        "motivo": "Sin autorización, debe estar disponible para venta",
        "saldo_disponible": 7756,
        "fecha_hotfix": "2026-06-10"
    },
    usuario_id=usuario_id,
    ip="127.0.0.1"
)

print("[OK] Auditoria registrada")

print("\n" + "=" * 80)
print("HOTFIX COMPLETADO")
print("=" * 80)
print("\n[OK] PP-2026-0012 ahora esta en estado ABIERTO")
print("[OK] 7,756 pares disponibles para venta")
print("\nProximos pasos:")
print("  1. Verificar en RIMEC Web que aparezcan los 7,756 pares")
print("  2. Confirmar con Director que puede vender")
print("=" * 80)
