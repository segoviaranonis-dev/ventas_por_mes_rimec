#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificar duplicados FI por PP"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_dataframe

print("=" * 70)
print("  VERIFICACION DUPLICADOS FI POR PP")
print("=" * 70 + "\n")

# 1. Buscar duplicados
print("[1] Buscando duplicados (mismo nro_factura en mismo PP)...\n")
df_dup = get_dataframe("""
    SELECT pp_id, nro_factura, COUNT(*) as cantidad
    FROM factura_interna
    GROUP BY pp_id, nro_factura
    HAVING COUNT(*) > 1
    ORDER BY pp_id, nro_factura
""")

if df_dup is not None and not df_dup.empty:
    print("[CRITICO] DUPLICADOS ENCONTRADOS:")
    print(df_dup.to_string(index=False))
else:
    print("[OK] No hay duplicados - cada nro_factura es unico por PP")

print("\n" + "-" * 70 + "\n")

# 2. Verificar caso especifico 9-PV001
print("[2] Verificando caso especifico: 9-PV001\n")
df_9pv001 = get_dataframe("""
    SELECT
        fi.id,
        fi.nro_factura,
        fi.pp_id,
        pp.numero_registro AS nro_pp,
        fi.estado,
        fi.total_pares,
        cv.descp_cliente AS cliente,
        vv.descp_usuario AS vendedor,
        fi.marca,
        fi.caso,
        fi.total_monto,
        fi.created_at
    FROM factura_interna fi
    LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
    LEFT JOIN cliente_v2 cv ON cv.id_cliente = fi.cliente_id
    LEFT JOIN usuario_v2 vv ON vv.id_usuario = fi.vendedor_id
    WHERE fi.nro_factura = '9-PV001'
""")

if df_9pv001 is not None and not df_9pv001.empty:
    print("[OK] 9-PV001 encontrada:\n")
    for col in df_9pv001.columns:
        print(f"  {col:15}: {df_9pv001.iloc[0][col]}")
else:
    print("[ERROR] 9-PV001 no encontrada")

print("\n" + "-" * 70)
print("[OK] Verificacion completada\n")
