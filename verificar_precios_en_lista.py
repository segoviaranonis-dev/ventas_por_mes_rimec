# Verificar si existen precios en precio_lista para los SKUs problemáticos

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*80)
print("VERIFICACION: Precios en precio_lista para SKUs del PP-0010")
print("="*80 + "\n")

# IDs que encontramos antes:
# Linea 2305 ID: 221
# Referencia 1579 ID: 10687
# Linea 2400 ID: 259
# Referencia 139 ID: 2087

skus = [
    {"linea_id": 221, "ref_id": 10687, "linea": "2305", "ref": "1579", "material": "9569"},
    {"linea_id": 259, "ref_id": 2087, "linea": "2400", "ref": "139", "material": "13958"}
]

for sku in skus:
    print(f"\n{'='*80}")
    print(f"SKU: Linea {sku['linea']}:{sku['ref']} - Material {sku['material']}")
    print('='*80)

    # 1. Buscar material_id
    query_mat = """
        SELECT id, codigo_proveedor, proveedor_id
        FROM public.material
        WHERE codigo_proveedor = :mat_code
        LIMIT 1
    """
    df_mat = get_dataframe(query_mat, {"mat_code": int(sku['material'])})

    if df_mat is None or df_mat.empty:
        print(f"[ERROR] Material {sku['material']} NO encontrado")
        continue

    mat_id = int(df_mat.iloc[0]['id'])
    mat_prov = int(df_mat.iloc[0]['proveedor_id'])
    print(f"[OK] Material encontrado - ID: {mat_id}, Proveedor: {mat_prov}")

    # 2. Buscar precios en precio_lista
    query_precios = """
        SELECT
            pl.id,
            pl.evento_id,
            pl.linea_id,
            pl.referencia_id,
            pl.material_id,
            pl.lpn,
            pl.lpc02,
            pl.lpc03,
            pl.lpc04,
            pl.nombre_caso_aplicado,
            pe.nombre_evento,
            pe.estado as evento_estado
        FROM public.precio_lista pl
        JOIN public.precio_evento pe ON pe.id = pl.evento_id
        WHERE pl.linea_id = :linea_id
            AND pl.referencia_id = :ref_id
            AND pl.material_id = :mat_id
        ORDER BY pe.created_at DESC
        LIMIT 5
    """

    df_precios = get_dataframe(query_precios, {
        "linea_id": sku['linea_id'],
        "ref_id": sku['ref_id'],
        "mat_id": mat_id
    })

    if df_precios is not None and not df_precios.empty:
        print(f"\n[OK] Se encontraron {len(df_precios)} precio(s) para este SKU:\n")
        print(df_precios[['evento_id', 'nombre_evento', 'evento_estado', 'lpn', 'lpc02', 'lpc03']].to_string(index=False))

        # Ver cuál es el más reciente cerrado
        cerrados = df_precios[df_precios['evento_estado'] == 'cerrado']
        if not cerrados.empty:
            print(f"\n[INFO] Evento más reciente CERRADO:")
            ultimo = cerrados.iloc[0]
            print(f"  Evento ID: {ultimo['evento_id']}")
            print(f"  Nombre: {ultimo['nombre_evento']}")
            print(f"  LPN: {ultimo['lpn']}")
            print(f"  LPC02: {ultimo['lpc02']}")
        else:
            print(f"\n[ADVERTENCIA] No hay eventos CERRADOS con precio para este SKU")

    else:
        print(f"\n[ERROR] NO HAY PRECIOS en precio_lista para este SKU")
        print(f"  Linea ID: {sku['linea_id']}")
        print(f"  Ref ID: {sku['ref_id']}")
        print(f"  Material ID: {mat_id}")

print("\n" + "="*80)
print("Fin de la verificación")
print("="*80 + "\n")
