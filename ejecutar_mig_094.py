# Ejecutar migración 094 directamente (sin confirmación)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import engine
from sqlalchemy import text

print("\n" + "="*80)
print("EJECUTANDO MIG-094: Fix validacion de precios desde v_stock_rimec")
print("="*80 + "\n")

try:
    with open('migrations/094_fix_validar_precio_desde_vista.sql', 'r', encoding='utf-8') as f:
        sql = f.read()

    with engine.begin() as conn:
        conn.execute(text(sql))

    print("[EXITO] Migracion 094 aplicada correctamente!")
    print("\nAhora el sistema:")
    print("  OK Valida precios desde v_stock_rimec")
    print("  OK Funciona aunque NO haya intencion de compra vinculada al PP")
    print("  OK Usa el fallback automatico a eventos cerrados")
    print("\n" + "="*80)

except Exception as e:
    print(f"\n[ERROR] Fallo al aplicar la migracion:")
    print(f"  {str(e)}")

print("\n" + "="*80)
