#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investigar por que PV001 no aparece en Pedido Proveedor
"""

import os
import sys
from pathlib import Path

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_dataframe

print("=" * 70)
print("  INVESTIGACION PV001 - FACTURA INTERNA")
print("=" * 70 + "\n")

# 1. Buscar cualquier PV001
print("[1] Buscando FI con 'PV001' en el numero...\n")
df_pv001 = get_dataframe("""
    SELECT
        id,
        nro_factura,
        pp_id,
        pedido_id,
        estado,
        marca,
        caso,
        total_pares,
        total_monto,
        created_at
    FROM factura_interna
    WHERE nro_factura ILIKE '%PV001%'
    ORDER BY pp_id, id
""")

if df_pv001 is not None and not df_pv001.empty:
    print(f"[OK] Encontradas {len(df_pv001)} FI con PV001:\n")
    print(df_pv001.to_string(index=False))
    print("\n" + "-" * 60 + "\n")
else:
    print("[ERROR] NO se encontro ninguna FI con PV001\n")
    print("-" * 60 + "\n")

# 2. Contar FI por estado
print("[2] Contando FI por estado...\n")
df_estados = get_dataframe("""
    SELECT estado, COUNT(*)::int AS cantidad
    FROM factura_interna
    GROUP BY estado
    ORDER BY cantidad DESC
""")

if df_estados is not None and not df_estados.empty:
    print(df_estados.to_string(index=False))
    print("\n" + "-" * 60 + "\n")

# 3. Listar ultimas 20 FI creadas
print("[3] Ultimas 20 FI creadas (orden actual de la pantalla)...\n")
df_ultimas = get_dataframe("""
    SELECT
        id,
        nro_factura,
        pp_id,
        estado,
        total_pares,
        TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at
    FROM factura_interna
    ORDER BY created_at DESC, nro_factura
    LIMIT 20
""")

if df_ultimas is not None and not df_ultimas.empty:
    print(df_ultimas.to_string(index=False))
    print("\n" + "-" * 60 + "\n")

# 4. Extraer numero PV y ordenar descendente
print("[4] FI ordenadas por numero PV descendente (orden correcto)...\n")
df_pv_order = get_dataframe("""
    SELECT
        id,
        nro_factura,
        pp_id,
        estado,
        total_pares,
        TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
        CAST(regexp_replace(nro_factura, '.*PV0*', '') AS INTEGER) AS pv_numero
    FROM factura_interna
    WHERE nro_factura ~* 'PV[0-9]+'
    ORDER BY pv_numero DESC
    LIMIT 20
""")

if df_pv_order is not None and not df_pv_order.empty:
    print(df_pv_order.to_string(index=False))
    print("\n" + "-" * 60 + "\n")

# 5. Si PV001 existe, mostrar detalles
if df_pv001 is not None and not df_pv001.empty:
    pv001_row = df_pv001.iloc[0]
    print("[5] Detalles de PV001:\n")
    print(f"   ID:           {pv001_row['id']}")
    print(f"   Numero:       {pv001_row['nro_factura']}")
    print(f"   PP ID:        {pv001_row['pp_id']}")
    print(f"   Estado:       {pv001_row['estado']}")
    print(f"   Marca:        {pv001_row['marca']}")
    print(f"   Total pares:  {pv001_row['total_pares']}")
    print(f"   Total monto:  {pv001_row['total_monto']}")
    print(f"   Creada:       {pv001_row['created_at']}")
    print("\n" + "-" * 60 + "\n")

print("[OK] Investigacion completada\n")
