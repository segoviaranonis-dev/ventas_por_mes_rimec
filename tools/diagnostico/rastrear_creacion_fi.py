"""Rastrear cómo se creó la FI 1-PV010"""
from core.database import get_dataframe

# Ver de dónde viene esta FI
fi_query = """
SELECT
    fi.id,
    fi.nro_factura,
    fi.pedido_id,
    fi.pp_id,
    fi.lista_precio_id,
    fi.descuento_1,
    fi.descuento_2,
    fi.descuento_3,
    fi.descuento_4,
    fi.created_at,
    pvr.nro_pedido,
    pvr.lista_precio_id as pvr_lista,
    pvr.descuento_1 as pvr_desc1,
    pvr.descuento_2 as pvr_desc2,
    pvr.descuento_3 as pvr_desc3,
    pvr.descuento_4 as pvr_desc4
FROM factura_interna fi
LEFT JOIN pedido_venta_rimec pvr ON pvr.id = fi.pedido_id
WHERE fi.nro_factura = '1-PV010'
"""

df = get_dataframe(fi_query)
print("=== FI 1-PV010 - Origen ===")
print(df.to_string())

if not df.empty:
    pedido_id = df.iloc[0]['pedido_id']
    if pedido_id:
        print(f"\nViene del pedido: {df.iloc[0]['nro_pedido']}")
        print(f"Lista del pedido: {df.iloc[0]['pvr_lista']}")
        print(f"Descuentos del pedido: {df.iloc[0]['pvr_desc1']}% / {df.iloc[0]['pvr_desc2']}% / {df.iloc[0]['pvr_desc3']}% / {df.iloc[0]['pvr_desc4']}%")
    else:
        print("\nNo tiene pedido_id asociado (creada manualmente o antes de migración 029)")
