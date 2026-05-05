"""Diagnóstico: estructura real de PPD y keys del payload."""
import sys, pathlib, json, ast
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.database import get_dataframe, engine
from sqlalchemy import text

# --- Payload del primer pedido PENDIENTE ---
df = get_dataframe("SELECT id, payload_json FROM pedido_venta_rimec WHERE estado='PENDIENTE' ORDER BY created_at DESC LIMIT 1")
pedido = df.iloc[0]
pedido_id = int(pedido["id"])
raw = pedido["payload_json"]
if isinstance(raw, dict):
    payload = raw
else:
    try:
        payload = json.loads(raw)
    except Exception:
        payload = ast.literal_eval(raw)

lotes = payload.get("lotes", [])
print(f"\n[DIAG] Pedido id={pedido_id}  lotes={len(lotes)}")

for lote in lotes[:2]:
    pp_id = lote.get("pp_id")
    print(f"\n[DIAG] ===== LOTE pp_id={pp_id} =====")
    for mb in lote.get("marcas", [])[:1]:
        marca = mb.get("marca")
        print(f"[DIAG] Marca: {marca}")
        for item in mb.get("items", [])[:3]:
            print(f"[DIAG]   keys    : {list(item.keys())}")
            print(f"[DIAG]   linea_codigo={item.get('linea_codigo')}  ref_codigo={item.get('ref_codigo')}")
            print(f"[DIAG]   linea_cod  ={item.get('linea_cod')}      ref_cod   ={item.get('ref_cod')}")
            print(f"[DIAG]   det_id     ={item.get('det_id')}")
            break

# --- Estructura real de PPD ---
with engine.connect() as conn:
    # Columnas de la tabla
    cols = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'pedido_proveedor_detalle'
        ORDER BY ordinal_position
    """)).fetchall()
    print(f"\n[DIAG] pedido_proveedor_detalle COLUMNAS:")
    for c in cols:
        print(f"  {c[0]:30s} {c[1]}")

    # Rows del pp_id del primer lote
    pp_id = lotes[0].get("pp_id") if lotes else None
    if pp_id:
        rows = conn.execute(text("""
            SELECT * FROM pedido_proveedor_detalle
            WHERE pedido_proveedor_id = :ppid LIMIT 5
        """), {"ppid": pp_id}).fetchall()
        keys = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='pedido_proveedor_detalle' ORDER BY ordinal_position
        """)).fetchall()
        col_names = [k[0] for k in keys]
        print(f"\n[DIAG] PPD rows para pp_id={pp_id}: {len(rows)}")
        for r in rows[:3]:
            print(f"  {dict(zip(col_names, r))}")
