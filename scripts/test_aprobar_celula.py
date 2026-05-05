"""Test directo: aprobar celula PP MOLEKINHA 2126 del primer pedido PENDIENTE."""
import sys, pathlib, json, traceback
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.database import get_dataframe
from modules.aprobacion_pedidos.logic import crear_preventa_desde_celula

# Obtener primer pedido PENDIENTE
df = get_dataframe("SELECT id, nro_pedido, payload_json FROM pedido_venta_rimec WHERE estado='PENDIENTE' ORDER BY created_at DESC LIMIT 1")
if df is None or df.empty:
    print("No hay pedidos PENDIENTES.")
    sys.exit(1)

pedido = df.iloc[0]
pedido_id = int(pedido["id"])
print(f"Pedido: {pedido['nro_pedido']} (id={pedido_id})")

import ast
raw = pedido["payload_json"]
if isinstance(raw, dict):
    payload = raw
else:
    try:
        payload = json.loads(raw)
    except Exception:
        payload = ast.literal_eval(raw)
lotes = payload.get("lotes", [])

# Construir celula de MOLEKINHA 2126
celula = None
for lote in lotes:
    pp_id  = lote.get("pp_id")
    pp_nro = lote.get("pp_nro", str(pp_id))
    for mb in lote.get("marcas", []):
        if mb.get("marca") != "MOLEKINHA":
            continue
        for item in mb.get("items", []):
            if str(item.get("linea_codigo")) == "2126":
                if celula is None:
                    celula = {"pp_id": pp_id, "pp_nro": pp_nro,
                              "marca": "MOLEKINHA", "caso": "2126", "items": []}
                celula["items"].append(item)

if celula is None:
    print("No se encontro celula MOLEKINHA/2126. Mostrando marcas disponibles:")
    for lote in lotes:
        for mb in lote.get("marcas", []):
            print(f"  Marca: {mb.get('marca')} — items: {[i.get('linea_codigo') for i in mb.get('items',[])]}")
    sys.exit(1)

print(f"Celula: {len(celula['items'])} items — intentando aprobar...")
try:
    ok, resultado = crear_preventa_desde_celula(pedido_id, celula)
    if ok:
        print(f"EXITO: Preventa generada: {resultado}")
    else:
        print(f"FALLO (lógico): {resultado}")
except Exception as e:
    print(f"EXCEPCION: {e}")
    traceback.print_exc()
