#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificacion: ETA vs Dato Duro (quincena_arribo_id)

Compara que la fecha ETA coincida con la quincena asignada:
- 15/05 -> 1ra Quincena de Mayo
- 30/05 -> 2da Quincena de Mayo
- etc.

Preparacion para desenchufar ETA completamente.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from core.database import get_dataframe
from datetime import datetime

print("=" * 80)
print("VERIFICACION: ETA vs DATO DURO (quincena_arribo_id)")
print("=" * 80)

# Mapa de descripción a mes/quincena esperados
QUINCENA_MAP = {
    "1ra Quincena de Enero": (1, 1, 15),
    "2da Quincena de Enero": (1, 2, 30),
    "1ra Quincena de Febrero": (2, 1, 15),
    "2da Quincena de Febrero": (2, 2, 28),
    "1ra Quincena de Marzo": (3, 1, 15),
    "2da Quincena de Marzo": (3, 2, 30),
    "1ra Quincena de Abril": (4, 1, 15),
    "2da Quincena de Abril": (4, 2, 30),
    "1ra Quincena de Mayo": (5, 1, 15),
    "2da Quincena de Mayo": (5, 2, 30),
    "1ra Quincena de Junio": (6, 1, 15),
    "2da Quincena de Junio": (6, 2, 30),
    "1ra Quincena de Julio": (7, 1, 15),
    "2da Quincena de Julio": (7, 2, 30),
    "1ra Quincena de Agosto": (8, 1, 15),
    "2da Quincena de Agosto": (8, 2, 30),
    "1ra Quincena de Septiembre": (9, 1, 15),
    "2da Quincena de Septiembre": (9, 2, 30),
    "1ra Quincena de Octubre": (10, 1, 15),
    "2da Quincena de Octubre": (10, 2, 30),
    "1ra Quincena de Noviembre": (11, 1, 15),
    "2da Quincena de Noviembre": (11, 2, 30),
    "1ra Quincena de Diciembre": (12, 1, 15),
    "2da Quincena de Diciembre": (12, 2, 30),
}

# 1. Obtener PPs con quincena asignada
df_pp = get_dataframe("""
    SELECT
        pp.id,
        pp.numero_registro,
        pp.fecha_arribo_estimada,
        pp.quincena_arribo_id,
        qa.descripcion as quincena_desc
    FROM pedido_proveedor pp
    LEFT JOIN quincena_arribo qa ON qa.id = pp.quincena_arribo_id
    WHERE pp.quincena_arribo_id IS NOT NULL
    ORDER BY pp.fecha_arribo_estimada
""")

if df_pp is None or df_pp.empty:
    print("\nNo hay PPs con quincena asignada")
    print("=" * 80)
    exit(0)

print(f"\n{len(df_pp)} PPs con quincena asignada\n")

# 2. Verificar coincidencia
inconsistencias = []

for _, row in df_pp.iterrows():
    pp_nro = row['numero_registro']
    eta = row['fecha_arribo_estimada']
    quincena_desc = row['quincena_desc']

    if not eta:
        inconsistencias.append(f"{pp_nro}: Tiene quincena pero NO tiene fecha ETA")
        continue

    # Buscar en mapa
    if quincena_desc not in QUINCENA_MAP:
        inconsistencias.append(f"{pp_nro}: Quincena desconocida '{quincena_desc}'")
        continue

    mes_esperado, quincena_num, dia_esperado = QUINCENA_MAP[quincena_desc]

    # Extraer fecha del ETA
    if isinstance(eta, str):
        eta_dt = datetime.fromisoformat(eta)
    else:
        eta_dt = eta

    eta_dia = eta_dt.day
    eta_mes = eta_dt.month
    eta_str = eta_dt.strftime('%d/%m/%Y')

    # Verificar coincidencia (tolerancia +/- 2 dias)
    coincide_mes = eta_mes == mes_esperado
    coincide_dia = abs(eta_dia - dia_esperado) <= 2

    if not (coincide_dia and coincide_mes):
        inconsistencias.append(
            f"{pp_nro}: ETA {eta_str} NO coincide con {quincena_desc}"
        )
    else:
        print(f"OK {pp_nro}: ETA {eta_str} = {quincena_desc}")

# 3. Resumen
print("\n" + "=" * 80)
if inconsistencias:
    print(f"ADVERTENCIA: {len(inconsistencias)} INCONSISTENCIAS DETECTADAS:")
    for inc in inconsistencias:
        print(f"  - {inc}")
else:
    print("TODAS LAS FECHAS ETA COINCIDEN CON LAS QUINCENAS ASIGNADAS")

print("=" * 80)

# 4. Mostrar PPs SIN quincena (aun con ETA)
df_sin_quincena = get_dataframe("""
    SELECT
        pp.id,
        pp.numero_registro,
        pp.fecha_arribo_estimada
    FROM pedido_proveedor pp
    WHERE pp.quincena_arribo_id IS NULL
      AND pp.fecha_arribo_estimada IS NOT NULL
      AND pp.estado IN ('ABIERTO', 'ENVIADO')
    ORDER BY pp.fecha_arribo_estimada
""")

if df_sin_quincena is not None and not df_sin_quincena.empty:
    print(f"\n{len(df_sin_quincena)} PPs SIN quincena asignada (pendientes de migrar):")
    for _, row in df_sin_quincena.iterrows():
        eta = datetime.fromisoformat(str(row['fecha_arribo_estimada']))
        print(f"  - {row['numero_registro']}: ETA {eta.strftime('%d/%m/%Y')}")
    print("\nEstos PPs necesitan que se les asigne quincena_arribo_id en Nexus Core")

print("=" * 80)
print("VERIFICACION COMPLETADA")
print("=" * 80)
