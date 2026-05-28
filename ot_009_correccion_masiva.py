"""
ORDEN DE TRABAJO 009: CORRECCIÓN MASIVA DE PRECIOS
URGENCIA: CRÍTICA
DESCRIPCIÓN: Recalcular TODAS las FIs en estado RESERVADA con precios correctos
"""

import sys
sys.path.insert(0, '.')

from core.database import get_dataframe, engine
from sqlalchemy import text as sqlt
from modules.aprobacion_pedidos.logic import actualizar_fi_encabezado
import time

print("="*80)
print("CORRECCIÓN MASIVA DE PRECIOS - ORDEN DE TRABAJO 009")
print("="*80)

# Obtener todas las FIs en RESERVADA
query = """
SELECT
    id,
    nro_factura,
    lista_precio_id,
    descuento_1,
    descuento_2,
    descuento_3,
    descuento_4,
    plazo_id
FROM factura_interna
WHERE estado = 'RESERVADA'
ORDER BY id
"""

print("\n[1/2] Obteniendo facturas en estado RESERVADA...")
df = get_dataframe(query)

if df.empty:
    print("No hay facturas RESERVADAS para corregir.")
    exit(0)

print(f"   - {len(df)} facturas encontradas")

# Recalcular cada FI
print("\n[2/2] Recalculando precios...")
print("-"*80)

exitosos = 0
fallidos = 0
errores = []

for idx, row in df.iterrows():
    fi_id = int(row['id'])
    nro_factura = row['nro_factura']
    lista_precio_id = int(row['lista_precio_id'])
    plazo_id = int(row['plazo_id']) if row['plazo_id'] else 1

    # Convertir descuentos a float (pueden venir como None)
    desc1 = float(row['descuento_1'] or 0)
    desc2 = float(row['descuento_2'] or 0)
    desc3 = float(row['descuento_3'] or 0)
    desc4 = float(row['descuento_4'] or 0)

    print(f"\n[{idx+1}/{len(df)}] Procesando {nro_factura} (ID:{fi_id})...")
    print(f"        Lista: {lista_precio_id}, Descuentos: {desc1}% / {desc2}% / {desc3}% / {desc4}%")

    try:
        # Llamar a la función de recalcular
        ok, msg = actualizar_fi_encabezado(
            fi_id=fi_id,
            lista_precio_id=lista_precio_id,
            descuento_1=desc1,
            descuento_2=desc2,
            descuento_3=desc3,
            descuento_4=desc4,
            plazo_id=plazo_id
        )

        if ok:
            print(f"        [OK] {msg}")
            exitosos += 1
        else:
            print(f"        [ERROR] ERROR: {msg}")
            fallidos += 1
            errores.append({'fi_id': fi_id, 'nro_factura': nro_factura, 'error': msg})

    except Exception as e:
        print(f"        [ERROR] EXCEPCIÓN: {str(e)}")
        fallidos += 1
        errores.append({'fi_id': fi_id, 'nro_factura': nro_factura, 'error': str(e)})

    # Pequeña pausa para no saturar la BD
    time.sleep(0.1)

# Reporte final
print("\n" + "="*80)
print("RESUMEN DE CORRECCIÓN")
print("="*80)
print(f"Total procesadas: {len(df)}")
print(f"Exitosas: {exitosos}")
print(f"Fallidas: {fallidos}")

if errores:
    print("\n" + "-"*80)
    print("ERRORES DETECTADOS")
    print("-"*80)
    for err in errores:
        print(f"  - {err['nro_factura']} (ID:{err['fi_id']}): {err['error']}")

print("\n" + "="*80)
if fallidos == 0:
    print("[OK] CORRECCIÓN COMPLETADA EXITOSAMENTE")
else:
    print(f"⚠ CORRECCIÓN COMPLETADA CON {fallidos} ERRORES")
print("="*80)
