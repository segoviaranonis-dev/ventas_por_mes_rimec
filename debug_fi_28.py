"""Debug FI 28 (1-PV001) para entender el problema"""
from core.database import get_dataframe

# Ver FI 28
fi_query = """
SELECT
    fi.id,
    fi.nro_factura,
    fi.lista_precio_id,
    fi.descuento_1,
    fi.descuento_2,
    fi.descuento_3,
    fi.descuento_4,
    fid.id as item_id,
    fid.precio_unit,
    fid.precio_neto,
    fid.subtotal,
    fid.pares,
    fid.linea_snapshot
FROM factura_interna fi
JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
WHERE fi.id = 28
LIMIT 1
"""

df = get_dataframe(fi_query)
print("=== FI 28 (1-PV001) ===")
print(df.to_string())

if not df.empty:
    row = df.iloc[0]
    print(f"\nLista precio: {row['lista_precio_id']}")
    print(f"Descuentos: {row['descuento_1']}% / {row['descuento_2']}% / {row['descuento_3']}% / {row['descuento_4']}%")
    print(f"\nPrimer item:")
    print(f"  Precio Unit (base): {row['precio_unit']:,.0f}")
    print(f"  Precio Neto (con desc): {row['precio_neto']:,.0f}")
    print(f"  Pares: {row['pares']}")
    print(f"  Subtotal: {row['subtotal']:,.0f}")

    # Calcular lo que DEBERÍA ser
    precio_con_desc = row['precio_unit'] * (1 - row['descuento_1']/100) if row['descuento_1'] else row['precio_unit']
    print(f"\nPrecio con descuento calculado: {precio_con_desc:,.0f}")
    print(f"¿Coincide con precio_neto? {abs(precio_con_desc - row['precio_neto']) < 1}")
