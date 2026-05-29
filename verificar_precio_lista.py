"""Verificar precio de lista vs precio en FI"""
from core.database import get_dataframe

# Obtener FI
fi_query = """
SELECT id, nro_factura, lista_precio_id, descuento_1, descuento_2, descuento_3, descuento_4
FROM factura_interna
WHERE nro_factura = '1-PV010'
"""
fi_df = get_dataframe(fi_query)
print("=== FI 1-PV010 ===")
print(f"Lista precio ID: {fi_df.iloc[0]['lista_precio_id']}")
print(f"Descuentos: {fi_df.iloc[0]['descuento_1']}% / {fi_df.iloc[0]['descuento_2']}% / {fi_df.iloc[0]['descuento_3']}% / {fi_df.iloc[0]['descuento_4']}%")

# Obtener item
item_query = """
SELECT
    fid.precio_unit,
    fid.precio_neto,
    fid.linea_snapshot
FROM factura_interna_detalle fid
WHERE fid.factura_id = :fi_id
ORDER BY fid.id
LIMIT 1
"""
item_df = get_dataframe(item_query, {"fi_id": int(fi_df.iloc[0]['id'])})

if not item_df.empty:
    import json
    import ast

    snapshot_text = str(item_df.iloc[0]['linea_snapshot'])
    try:
        snapshot = json.loads(snapshot_text)
    except:
        snapshot = ast.literal_eval(snapshot_text)
    linea = snapshot['linea_codigo']
    ref = snapshot['ref_codigo']

    print(f"\n=== Item {linea}-{ref} ===")
    print(f"Precio Unit en FI: {item_df.iloc[0]['precio_unit']:,.0f}")
    print(f"Precio Neto en FI: {item_df.iloc[0]['precio_neto']:,.0f}")

    # Buscar precio en v_stock_rimec
    stock_query = """
    SELECT lpn, lpc02, lpc03, lpc04
    FROM v_stock_rimec
    WHERE linea_codigo = :linea AND referencia_codigo = :ref
    LIMIT 1
    """
    stock_df = get_dataframe(stock_query, {"linea": linea, "ref": ref})

    if not stock_df.empty:
        print(f"\n=== Precios en v_stock_rimec ===")
        lpn = float(stock_df.iloc[0]['lpn']) if stock_df.iloc[0]['lpn'] and str(stock_df.iloc[0]['lpn']) != 'None' else 0
        lpc02 = float(stock_df.iloc[0]['lpc02']) if stock_df.iloc[0]['lpc02'] and str(stock_df.iloc[0]['lpc02']) != 'None' else 0
        lpc03 = float(stock_df.iloc[0]['lpc03']) if stock_df.iloc[0]['lpc03'] and str(stock_df.iloc[0]['lpc03']) != 'None' else 0
        lpc04 = float(stock_df.iloc[0]['lpc04']) if stock_df.iloc[0]['lpc04'] and str(stock_df.iloc[0]['lpc04']) != 'None' else 0

        print(f"LPN (Lista 1): {lpn:,.0f}")
        print(f"LPC02 (Lista 2): {lpc02:,.0f}")
        print(f"LPC03 (Lista 3): {lpc03:,.0f}")
        print(f"LPC04 (Lista 4): {lpc04:,.0f}")

        # Determinar qué lista se usó
        lista_id = int(fi_df.iloc[0]['lista_precio_id'])
        precio_lista_map = {
            1: lpn,
            2: lpc02,
            3: lpc03,
            4: lpc04
        }
        precio_lista_original = precio_lista_map.get(lista_id, 0)

        print(f"\n=== Análisis ===")
        print(f"Precio de Lista (LPC03): {precio_lista_original:,.0f}")
        print(f"Precio Unit en FI: {item_df.iloc[0]['precio_unit']:,.0f}")
        print(f"Diferencia: {precio_lista_original - item_df.iloc[0]['precio_unit']:,.0f}")

        if precio_lista_original > 0:
            descuento_real = ((precio_lista_original - item_df.iloc[0]['precio_unit']) / precio_lista_original) * 100
            print(f"Descuento real aplicado: {descuento_real:.2f}%")
