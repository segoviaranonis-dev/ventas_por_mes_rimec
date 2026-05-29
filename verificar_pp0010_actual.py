# Verificar estado ACTUAL del PP-2026-0010

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("VERIFICACION ACTUAL: PP-2026-0010")
print("="*80 + "\n")

# Consultar pedido con ICs
query = """
    SELECT
        pp.id,
        pp.numero_registro,
        pp.estado,
        pp.id_intencion_compra,
        ic.precio_evento_id,
        pe.nombre_evento,
        pe.estado as evento_estado
    FROM public.pedido_proveedor pp
    LEFT JOIN public.intencion_compra ic ON ic.id = pp.id_intencion_compra
    LEFT JOIN public.precio_evento pe ON pe.id = ic.precio_evento_id
    WHERE pp.numero_registro = 'PP-2026-0010'
"""

df = get_dataframe(query)

if df is not None and not df.empty:
    row = df.iloc[0]
    print(f"PP ID: {row['id']}")
    print(f"Numero: {row['numero_registro']}")
    print(f"Estado: {row['estado']}")
    print(f"ID Intencion Compra: {row['id_intencion_compra']}")
    print(f"Precio Evento ID: {row['precio_evento_id']}")

    if row['id_intencion_compra'] is not None:
        print(f"\n[OK] El PP SI tiene intencion de compra vinculada")
        print(f"     Evento: {row['nombre_evento']}")
        print(f"     Estado evento: {row['evento_estado']}")
    else:
        print(f"\n[INFO] El PP NO tiene intencion de compra directa")
        print(f"       (Pero la MIG-094 permite que funcione igual)")

print("\n" + "="*80)
