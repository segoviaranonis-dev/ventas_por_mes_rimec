"""
ORDEN DE TRABAJO 009: DIAGNÓSTICO COMPLETO DE PRECIOS
URGENCIA: CRÍTICA
DESCRIPCIÓN: Verificar TODOS los pedidos y detectar discrepancias de precios
"""

from core.database import get_dataframe, engine
from sqlalchemy import text as sqlt
import pandas as pd

print("="*80)
print("DIAGNÓSTICO COMPLETO DE PRECIOS - ORDEN DE TRABAJO 009")
print("="*80)

# Mapeo de listas de precio a columnas en v_stock_rimec
LP_MAP = {1: "lpn", 2: "lpc02", 3: "lpc03", 4: "lpc04"}

# 1. Obtener TODAS las FIs con sus items
query = """
SELECT
    fi.id as fi_id,
    fi.nro_factura,
    fi.estado,
    fi.lista_precio_id,
    fi.descuento_1,
    fi.descuento_2,
    fi.descuento_3,
    fi.descuento_4,
    fid.id as item_id,
    fid.precio_unit,
    fid.precio_neto,
    fid.pares,
    fid.subtotal,
    fid.linea_snapshot
FROM factura_interna fi
JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
WHERE fi.estado IN ('RESERVADA', 'CONFIRMADA')
ORDER BY fi.id, fid.id
"""

print("\n[1/3] Obteniendo datos de facturas internas...")
df = get_dataframe(query)

if df.empty:
    print("No hay facturas para verificar.")
    exit(0)

print(f"   - {len(df)} items encontrados en {df['fi_id'].nunique()} facturas")

# 2. Parsear snapshots y obtener códigos
print("\n[2/3] Parseando snapshots y extrayendo códigos...")
import json
import ast

def parse_snapshot(snapshot_val):
    """Parsea el snapshot (JSON o dict string)"""
    if not snapshot_val:
        return {}
    try:
        if isinstance(snapshot_val, dict):
            return snapshot_val
        elif isinstance(snapshot_val, str):
            try:
                return json.loads(snapshot_val)
            except:
                return ast.literal_eval(snapshot_val)
    except:
        return {}

snapshots = df['linea_snapshot'].apply(parse_snapshot)
df['linea_codigo'] = snapshots.apply(lambda s: s.get('linea_codigo', ''))
df['ref_codigo'] = snapshots.apply(lambda s: s.get('ref_codigo', ''))

# Filtrar items sin códigos válidos
df_valid = df[(df['linea_codigo'] != '') & (df['ref_codigo'] != '')].copy()
print(f"   - {len(df_valid)} items con códigos válidos")

# 3. Obtener precios correctos de v_stock_rimec
print("\n[3/3] Consultando precios correctos en v_stock_rimec...")

# Crear lista única de (linea, ref)
productos_unicos = df_valid[['linea_codigo', 'ref_codigo']].drop_duplicates()

precios_stock = {}
for _, row in productos_unicos.iterrows():
    linea = row['linea_codigo']
    ref = row['ref_codigo']

    stock_query = sqlt("""
        SELECT lpn, lpc02, lpc03, lpc04
        FROM v_stock_rimec
        WHERE linea_codigo = :linea AND referencia_codigo = :ref
        LIMIT 1
    """)

    with engine.connect() as conn:
        result = conn.execute(stock_query, {"linea": linea, "ref": ref}).fetchone()

        if result:
            precios_stock[f"{linea}-{ref}"] = {
                1: float(result[0]) if result[0] and str(result[0]) != 'None' else 0,
                2: float(result[1]) if result[1] and str(result[1]) != 'None' else 0,
                3: float(result[2]) if result[2] and str(result[2]) != 'None' else 0,
                4: float(result[3]) if result[3] and str(result[3]) != 'None' else 0,
            }

print(f"   - Precios obtenidos para {len(precios_stock)} productos")

# 4. Comparar precios
print("\n" + "="*80)
print("RESULTADOS DEL DIAGNÓSTICO")
print("="*80)

errores = []
correctos = 0

for idx, row in df_valid.iterrows():
    producto_key = f"{row['linea_codigo']}-{row['ref_codigo']}"

    if producto_key not in precios_stock:
        errores.append({
            'fi_id': row['fi_id'],
            'nro_factura': row['nro_factura'],
            'estado': row['estado'],
            'item_id': row['item_id'],
            'producto': producto_key,
            'error': 'Producto no encontrado en v_stock_rimec',
            'precio_fi': row['precio_unit'],
            'precio_correcto': None,
            'diferencia': None
        })
        continue

    lista_id = int(row['lista_precio_id'])
    precio_correcto = precios_stock[producto_key].get(lista_id, 0)
    precio_fi = float(row['precio_unit'])

    # Calcular precio con descuentos aplicados
    precio_con_descuentos = precio_correcto
    for desc in [row['descuento_1'], row['descuento_2'], row['descuento_3'], row['descuento_4']]:
        if desc and desc > 0:
            precio_con_descuentos = precio_con_descuentos * (1 - desc / 100)

    # Comparar (tolerancia de 1 Gs por redondeos)
    if abs(precio_fi - precio_con_descuentos) > 1:
        errores.append({
            'fi_id': row['fi_id'],
            'nro_factura': row['nro_factura'],
            'estado': row['estado'],
            'item_id': row['item_id'],
            'producto': producto_key,
            'error': 'Precio incorrecto',
            'precio_fi': precio_fi,
            'precio_correcto': precio_con_descuentos,
            'diferencia': precio_fi - precio_con_descuentos,
            'precio_base': precio_correcto,
            'lista_id': lista_id
        })
    else:
        correctos += 1

# Reporte
print(f"\nItems correctos: {correctos}")
print(f"Items con errores: {len(errores)}")

if errores:
    print("\n" + "-"*80)
    print("DETALLE DE ERRORES")
    print("-"*80)

    df_errores = pd.DataFrame(errores)

    # Agrupar por factura
    for fi_id in df_errores['fi_id'].unique():
        errores_fi = df_errores[df_errores['fi_id'] == fi_id]
        fi_info = errores_fi.iloc[0]

        print(f"\nFACTURA: {fi_info['nro_factura']} (ID:{fi_id}) - Estado: {fi_info['estado']}")
        print(f"Items con error: {len(errores_fi)}")

        for _, err in errores_fi.iterrows():
            print(f"  - {err['producto']}: "
                  f"FI={err['precio_fi']:,.0f} | "
                  f"Correcto={err['precio_correcto']:,.0f} | "
                  f"Dif={err['diferencia']:,.0f}")

    print("\n" + "="*80)
    print("RESUMEN POR ESTADO")
    print("="*80)
    resumen = df_errores.groupby('estado').size()
    for estado, count in resumen.items():
        print(f"{estado}: {count} items con error")

    print("\n" + "="*80)
    print(f"TOTAL: {len(df_errores['fi_id'].unique())} facturas afectadas")
    print("="*80)

    # Guardar reporte
    df_errores.to_csv('diagnostico_precios_errores.csv', index=False)
    print("\nReporte guardado en: diagnostico_precios_errores.csv")

print("\nDIAGNÓSTICO COMPLETADO")
