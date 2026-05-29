#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reparación: Anular FIs huérfanas (RESERVADAS con pedido RECHAZADO)

PROBLEMA: Antes del fix, rechazar un pedido no anulaba sus FIs automáticamente.
SOLUCIÓN: Buscar FIs RESERVADAS cuyo pedido está RECHAZADO y anularlas.
"""
from core.database import get_dataframe
from modules.aprobacion_pedidos.logic import anular_fi
from core.database import DBInspector

print("=" * 80)
print("REPARACION: FIs huerfanas (RESERVADAS con pedido RECHAZADO)")
print("=" * 80)

# 1. Buscar FIs huérfanas
df = get_dataframe("""
    SELECT
        fi.id as fi_id,
        fi.nro_factura,
        fi.pedido_id,
        pvr.nro_pedido,
        pvr.estado as pedido_estado,
        pvr.motivo_rechazo,
        fi.total_pares,
        fi.marca,
        fi.caso
    FROM factura_interna fi
    LEFT JOIN pedido_venta_rimec pvr ON pvr.id = fi.pedido_id
    WHERE fi.estado = 'RESERVADA'
      AND pvr.estado = 'RECHAZADO'
    ORDER BY fi.id
""")

if df is None or df.empty:
    print("\nOK - No hay FIs huerfanas")
    print("=" * 80)
    exit(0)

print(f"\nFIs huerfanas encontradas: {len(df)}")
print("\n" + df.to_string(index=False))

# 2. Confirmar acción
print("\n" + "=" * 80)
respuesta = input("Anular TODAS estas FIs? (si/NO): ").strip().lower()

if respuesta != 'si':
    print("Operacion cancelada por el usuario")
    print("=" * 80)
    exit(0)

# 3. Anular cada FI
print("\n" + "=" * 80)
print("ANULANDO FIs...")
print("=" * 80)

anuladas_ok = []
errores = []

for _, row in df.iterrows():
    fi_id = int(row['fi_id'])
    nro_fi = row['nro_factura']
    nro_pedido = row['nro_pedido']
    motivo_rechazo = row['motivo_rechazo'] or "Sin motivo"

    print(f"\nAnulando {nro_fi} (pedido {nro_pedido})...")

    motivo = f"Pedido {nro_pedido} fue rechazado: {motivo_rechazo}"
    ok, msg = anular_fi(fi_id, motivo=motivo)

    if ok:
        print(f"  OK - {msg}")
        anuladas_ok.append(nro_fi)
    else:
        print(f"  ERROR - {msg}")
        errores.append(f"{nro_fi}: {msg}")

# 4. Resumen
print("\n" + "=" * 80)
print("RESUMEN:")
print(f"  Anuladas exitosamente: {len(anuladas_ok)}")
if anuladas_ok:
    for nro in anuladas_ok:
        print(f"    - {nro}")

if errores:
    print(f"  Errores: {len(errores)}")
    for err in errores:
        print(f"    - {err}")
else:
    print("  Sin errores")

print("=" * 80)
print("REPARACION COMPLETADA")
print("=" * 80)
