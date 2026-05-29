# Verificar relación IC -> PP (al revés)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("VERIFICACION: Intenciones de Compra que apuntan al PP-2026-0010")
print("="*80 + "\n")

# Ver estructura de intencion_compra
query_estructura = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'intencion_compra'
        AND table_schema = 'public'
    ORDER BY ordinal_position
"""

print("[1] Estructura de tabla intencion_compra:\n")
df_est = get_dataframe(query_estructura)
if df_est is not None:
    print(df_est.to_string(index=False))

# Buscar ICs relacionadas con el PP ID 10
print("\n" + "="*80)
print("[2] Intenciones de compra relacionadas:\n")

query_ics = """
    SELECT
        ic.id,
        ic.nro_registro,
        ic.id_proveedor,
        ic.precio_evento_id,
        pe.nombre_evento,
        pe.estado as evento_estado
    FROM public.intencion_compra ic
    LEFT JOIN public.precio_evento pe ON pe.id = ic.precio_evento_id
    WHERE ic.nro_registro IN ('IC-2026-0039', 'IC-2026-0040')
       OR ic.id IN (
           SELECT id_intencion_compra
           FROM public.pedido_proveedor
           WHERE id = 10
       )
    ORDER BY ic.id
"""

df_ics = get_dataframe(query_ics)
if df_ics is not None and not df_ics.empty:
    print(df_ics.to_string(index=False))

    # Ver si tienen evento de precio
    for idx, ic in df_ics.iterrows():
        if ic['precio_evento_id']:
            print(f"\n[OK] IC {ic['nro_registro']} tiene evento {ic['nombre_evento']} ({ic['evento_estado']})")
        else:
            print(f"\n[WARN] IC {ic['nro_registro']} NO tiene evento de precio")
else:
    print("[INFO] No se encontraron ICs con esos registros")

print("\n" + "="*80)
