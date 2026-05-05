"""
Popula pedido_proveedor_detalle del PP-2026-0001 usando los items
del pedido_venta_rimec (único lugar donde viven los datos de la proforma).
Solo inserta si PPD está vacío para ese pp_id.
"""
import sys, pathlib, json, ast
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.database import get_dataframe, engine
from sqlalchemy import text

PP_ID = 1  # PP-2026-0001

# ── Verificar que PPD realmente está vacío ──────────────────────────────────
with engine.connect() as conn:
    cnt = conn.execute(text(
        "SELECT COUNT(*) FROM pedido_proveedor_detalle WHERE pedido_proveedor_id=:p"
    ), {"p": PP_ID}).scalar()
    print(f"PPD actual para PP_ID={PP_ID}: {cnt} filas")
    if cnt > 0:
        print("PPD ya tiene datos. Abortando para no duplicar.")
        sys.exit(0)

# ── Cargar todos los pedidos PENDIENTE/AUTORIZADO de ese PP ────────────────
df = get_dataframe("""
    SELECT payload_json FROM pedido_venta_rimec
    WHERE estado IN ('PENDIENTE','AUTORIZADO')
    ORDER BY created_at DESC LIMIT 20
""")

if df is None or df.empty:
    print("No hay pedidos. Abortando.")
    sys.exit(1)

# ── Extraer todos los ítems del PP_ID=1 ────────────────────────────────────
# Acumular por linea|ref → cantidad total ordenada
acum: dict[str, dict] = {}

for _, row in df.iterrows():
    raw = row["payload_json"]
    if isinstance(raw, dict):
        payload = raw
    else:
        try:
            payload = json.loads(raw)
        except Exception:
            payload = ast.literal_eval(raw)

    for lote in payload.get("lotes", []):
        if str(lote.get("pp_id")) != str(PP_ID):
            continue
        for mb in lote.get("marcas", []):
            for item in mb.get("items", []):
                linea = str(item.get("linea_codigo", "")).strip()
                ref   = str(item.get("ref_codigo",   "")).strip()
                pares = int(item.get("pares", 0))
                if not linea or not ref or pares <= 0:
                    continue
                clave = f"{linea}|{ref}"
                if clave not in acum:
                    acum[clave] = {
                        "linea":     linea,
                        "referencia": ref,
                        "cantidad_pares": 0,
                    }
                acum[clave]["cantidad_pares"] += pares

print(f"\nÍtems únicos encontrados en payload: {len(acum)}")
for k, v in acum.items():
    print(f"  L{v['linea']}/R{v['referencia']} = {v['cantidad_pares']} pares")

if not acum:
    print("Sin ítems para PP_ID=1. Verificar payload.")
    sys.exit(1)

# ── Insertar en PPD ─────────────────────────────────────────────────────────
with engine.begin() as conn:
    for v in acum.values():
        conn.execute(text("""
            INSERT INTO pedido_proveedor_detalle
                (pedido_proveedor_id, linea, referencia,
                 cantidad, cantidad_pares, pares_vendidos,
                 cantidad_cajas, precio_usd)
            VALUES
                (:pp_id, :linea, :ref,
                 :pares, :pares, 0,
                 0, 0)
        """), {
            "pp_id": PP_ID,
            "linea": v["linea"],
            "ref":   v["referencia"],
            "pares": v["cantidad_pares"],
        })
    print(f"\nInsertados {len(acum)} registros en PPD.")

# ── Verificar ───────────────────────────────────────────────────────────────
df_check = get_dataframe("""
    SELECT linea, referencia, cantidad_pares, pares_vendidos
    FROM pedido_proveedor_detalle WHERE pedido_proveedor_id=1
    ORDER BY linea, referencia
""")
print("\nPPD final:")
print(df_check.to_string())
