"""
Reimporta faturaProforma 6421_2026_Molekinha.xls en PPD del PP-2026-0001
resolviendo los 5 pilares: linea, referencia, material, color, marca.
"""
import sys, pathlib, io
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.database import engine, get_dataframe
from modules.pedido_proveedor.logic import parse_proforma, populate_pp_from_proforma
from sqlalchemy import text

ARCHIVO = r"C:\Users\hecto\Documents\Prg_locales\PROFORMAS\faturaProforma 6421_2026_Molekinha.xls"
PP_ID        = 1
PROVEEDOR_ID = 654
PROFORMA     = "CP-6421-4015"
NRO_EXTERNO  = "4016"
DESCUENTO_1  = 0.20
DESCUENTO_2  = 0.05
DESCUENTO_3  = 0.0
DESCUENTO_4  = 0.0
FECHA_ETA    = "2026-05-15"
CATEGORIA_ID = 2

# ── 1. Leer archivo ──────────────────────────────────────────────────────────
print(f"Leyendo: {ARCHIVO}")
with open(ARCHIVO, "rb") as f:
    file_bytes = f.read()
print(f"  Tamanio: {len(file_bytes):,} bytes")

# ── 2. Parsear proforma ──────────────────────────────────────────────────────
print("\nParsendo proforma...")
df_detalle, total_pares, err = parse_proforma(file_bytes)

if err:
    print(f"ERROR en parser: {err}")
    sys.exit(1)

print(f"  Total pares: {total_pares}")
print(f"  SKUs parseados: {len(df_detalle)}")
if not df_detalle.empty:
    print(f"  Columnas: {list(df_detalle.columns)}")
    print(f"  Muestra (primeras 3 filas):")
    for _, r in df_detalle.head(3).iterrows():
        print(f"    L{r.get('linea_cod')} R{r.get('ref_cod')} "
              f"mat={r.get('material_code')} mat_desc={r.get('material')} "
              f"col={r.get('color_code')} col_desc={r.get('color')} "
              f"pares={r.get('pairs')}")

# ── 3. Verificar lookups de material y color ─────────────────────────────────
print("\nVerificando lookups maestros...")
with engine.connect() as conn:
    mat_cnt = conn.execute(text(
        "SELECT COUNT(*) FROM material WHERE proveedor_id=654"
    )).scalar()
    col_cnt = conn.execute(text(
        "SELECT COUNT(*) FROM color WHERE proveedor_id=654"
    )).scalar()
    print(f"  material: {mat_cnt} registros")
    print(f"  color:    {col_cnt} registros")

    # Verificar si los material_code del archivo existen en la tabla
    if not df_detalle.empty:
        sample_mat = str(df_detalle.iloc[0].get('material_code', ''))
        sample_col = str(df_detalle.iloc[0].get('color_code', ''))
        hit_mat = conn.execute(text(
            "SELECT id, descripcion FROM material WHERE codigo_proveedor::text=:c AND proveedor_id=654"
        ), {"c": sample_mat}).fetchone()
        hit_col = conn.execute(text(
            "SELECT id, nombre FROM color WHERE codigo_proveedor::text=:c AND proveedor_id=654"
        ), {"c": sample_col}).fetchone()
        print(f"  Muestra material_code={sample_mat} -> {hit_mat}")
        print(f"  Muestra color_code={sample_col}    -> {hit_col}")

# ── 4. Ejecutar importación ──────────────────────────────────────────────────
detalle_rows = df_detalle.to_dict("records")
print(f"\nEjecutando populate_pp_from_proforma para PP_ID={PP_ID}...")

ok, msg = populate_pp_from_proforma(
    pp_id        = PP_ID,
    proforma     = PROFORMA,
    nro_externo  = NRO_EXTERNO,
    descuento_1  = DESCUENTO_1,
    descuento_2  = DESCUENTO_2,
    descuento_3  = DESCUENTO_3,
    descuento_4  = DESCUENTO_4,
    fecha_eta    = FECHA_ETA,
    categoria_id = CATEGORIA_ID,
    detalle_rows = detalle_rows,
)

print(f"  Resultado: {'OK' if ok else 'ERROR'} — {msg}")

# ── 5. Verificación post-import ──────────────────────────────────────────────
print("\nVerificacion PPD post-import:")
df_check = get_dataframe("""
    SELECT linea, referencia, descp_material, descp_color,
           material_code, color_code,
           id_material, id_color,
           cantidad_pares, pares_vendidos
    FROM pedido_proveedor_detalle
    WHERE pedido_proveedor_id = 1
    ORDER BY linea, referencia
""")
if df_check is not None and not df_check.empty:
    print(df_check.to_string())
    none_mat = df_check['id_material'].isna().sum()
    none_col = df_check['id_color'].isna().sum()
    print(f"\n  id_material None: {none_mat}/{len(df_check)}")
    print(f"  id_color    None: {none_col}/{len(df_check)}")
else:
    print("  PPD vacio despues de import - algo fallo")
