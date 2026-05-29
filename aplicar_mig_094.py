# Aplicar migración 094 - Fix validación de precios

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import engine
from sqlalchemy import text

print("\n" + "="*80)
print("APLICANDO MIG-094: Fix validación de precios desde v_stock_rimec")
print("="*80 + "\n")

print("[INFO] Esta migración corrige la validación de precios para que:")
print("  1. Consulte precios desde v_stock_rimec (no desde ppd.precio_lpn)")
print("  2. Aproveche el fallback automático de la vista")
print("  3. Permita que RIMEC WEB sea un exhibidor puro\n")

respuesta = input("¿Deseas aplicar la migración? (SI/NO): ")

if respuesta.upper() != "SI":
    print("\n[CANCELADO] No se aplicó la migración")
    sys.exit(0)

try:
    with open('migrations/094_fix_validar_precio_desde_vista.sql', 'r', encoding='utf-8') as f:
        sql = f.read()

    with engine.begin() as conn:
        conn.execute(text(sql))

    print("\n[EXITO] Migración 094 aplicada correctamente!")
    print("\nAhora el sistema:")
    print("  ✓ Valida precios desde v_stock_rimec")
    print("  ✓ Funciona aunque NO haya intención de compra")
    print("  ✓ Usa el fallback automático a eventos cerrados")
    print("\n" + "="*80)

except Exception as e:
    print(f"\n[ERROR] Fallo al aplicar la migración:")
    print(f"  {str(e)}")
    print("\n[ROLLBACK] No se aplicaron cambios")

print("\n" + "="*80)
