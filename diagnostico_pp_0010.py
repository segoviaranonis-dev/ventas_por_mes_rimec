#!/usr/bin/env python3
from core.database import get_dataframe

df = get_dataframe("""
    SELECT
        pp.estado,
        COUNT(ppd.id) as articulos,
        SUM(GREATEST(0, COALESCE(ppd.cantidad_pares,0) - COALESCE(ppd.pares_vendidos,0))) as saldo
    FROM pedido_proveedor pp
    LEFT JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
    WHERE pp.numero_registro = 'PP-2026-0010'
    GROUP BY pp.estado
""")

print("=== Diagnóstico PP-2026-0010 ===")
print(df.to_string())
