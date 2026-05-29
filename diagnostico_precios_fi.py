"""Diagnóstico: Ver precios de FI 1-PV010"""
from core.database import get_dataframe

# FI 1-PV010
fi_query = """
SELECT id, nro_factura, lista_precio_id, descuento_1, descuento_2, descuento_3, descuento_4
FROM factura_interna
WHERE nro_factura = '1-PV010'
"""

fi_df = get_dataframe(fi_query)
print("=== Factura Interna ===")
print(fi_df.to_string())

if not fi_df.empty:
    fi_id = int(fi_df.iloc[0]['id'])

    # Items de la FI
    items_query = """
    SELECT
        fid.id,
        fid.cajas,
        fid.pares,
        fid.precio_unit,
        fid.precio_neto,
        fid.subtotal,
        fid.linea_snapshot::text as snapshot_text
    FROM factura_interna_detalle fid
    WHERE fid.factura_id = :fi_id
    ORDER BY fid.id
    """

    items_df = get_dataframe(items_query, {"fi_id": fi_id})
    print("\n=== Items de la FI ===")
    print(items_df.to_string())

    # Analizar el primer item
    if not items_df.empty:
        print("\n=== Análisis del primer item ===")
        item = items_df.iloc[0]
        print(f"Cajas: {item['cajas']}")
        print(f"Pares: {item['pares']}")
        print(f"Precio Unit (base): {item['precio_unit']:,.0f}")
        print(f"Precio Neto (con desc): {item['precio_neto']:,.0f}")
        print(f"Subtotal: {item['subtotal']:,.0f}")
        print(f"Snapshot: {item['snapshot_text'][:200]}...")

        # Calcular el descuento aplicado
        if item['precio_unit'] > 0:
            descuento_pct = ((item['precio_unit'] - item['precio_neto']) / item['precio_unit']) * 100
            print(f"\nDescuento aplicado: {descuento_pct:.2f}%")
            print(f"Subtotal calculado (precio_neto * pares): {item['precio_neto'] * item['pares']:,.0f}")
