# Consultar v_stock_rimec para ver si encuentra los items del PP-0010

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("CONSULTA: v_stock_rimec para items del PP-0010")
print("="*80 + "\n")

# Consultar la vista para los items específicos
query = """
    SELECT
        det_id,
        pp_nro,
        pp_estado,
        descp_marca,
        linea_codigo,
        referencia_codigo,
        material_code,
        color_code,
        nombre,
        cantidad_pares,
        pares_vendidos,
        saldo_pares,
        lpn,
        lpc02,
        lpc03,
        lpc04,
        caso_precio,
        caso_id,
        descp_caso
    FROM public.v_stock_rimec
    WHERE pp_nro = 'PP-2026-0010'
    ORDER BY det_id
"""

df = get_dataframe(query)

if df is not None and not df.empty:
    print(f"[OK] Se encontraron {len(df)} item(s) en v_stock_rimec:\n")

    for idx, row in df.iterrows():
        print(f"\n--- Item det_id: {row['det_id']} ---")
        print(f"  PP: {row['pp_nro']} ({row['pp_estado']})")
        print(f"  Marca: {row['descp_marca']}")
        print(f"  SKU: {row['linea_codigo']}:{row['referencia_codigo']}")
        print(f"  Material: {row['material_code']}, Color: {row['color_code']}")
        print(f"  Nombre: {row['nombre']}")
        print(f"  Pares: {row['cantidad_pares']} | Vendidos: {row['pares_vendidos']} | Saldo: {row['saldo_pares']}")

        # Lo importante: los precios
        if row['lpn'] is not None:
            print(f"  [OK] PRECIOS:")
            print(f"      LPN: {row['lpn']}")
            print(f"      LPC02: {row['lpc02']}")
            print(f"      LPC03: {row['lpc03']}")
            print(f"      LPC04: {row['lpc04']}")
            print(f"      Caso: {row['caso_precio']} (ID: {row['caso_id']})")
        else:
            print(f"  [ERROR] SIN PRECIOS - lpn es NULL")

    # Resumen
    print(f"\n{'='*80}")
    print(f"RESUMEN:")
    con_precio = df['lpn'].notna().sum()
    sin_precio = df['lpn'].isna().sum()
    print(f"  Items con precio: {con_precio}")
    print(f"  Items sin precio: {sin_precio}")

else:
    print("[ERROR] NO se encontraron items del PP-2026-0010 en v_stock_rimec")
    print("\nPosibles causas:")
    print("1. El estado del pedido no es ABIERTO o ENVIADO")
    print("2. El saldo de pares es 0")
    print("3. La vista tiene algún filtro que excluye estos items")

print("\n" + "="*80)
