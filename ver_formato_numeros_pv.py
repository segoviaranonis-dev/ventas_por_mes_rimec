#!/usr/bin/env python3
"""Ver formato de numeros PV en FIs vs Pedidos"""
from core.database import get_dataframe

print("FORMATO DE NUMEROS PV:")
print("=" * 80)

# Ver FIs con sus pedidos
df = get_dataframe("""
    SELECT
        fi.nro_factura as fi_numero,
        pvr.nro_pedido as pedido_numero,
        pvr.estado,
        fi.total_pares,
        fi.created_at
    FROM factura_interna fi
    LEFT JOIN pedido_venta_rimec pvr ON pvr.id = fi.pedido_id
    WHERE fi.estado = 'CONFIRMADA'
    ORDER BY fi.created_at DESC
    LIMIT 20
""")

if df is not None and not df.empty:
    print(df.to_string(index=False))
else:
    print("No hay datos")
