"""
Test finalizar_compra(1) después de OT-TRASPASO-504-001 fixes
"""
import sys
sys.path.insert(0, 'C:/Users/hecto/Documents/Prg_locales/ventas_por_mes_rimec-main')

from modules.compra_legal.logic import finalizar_compra

print("=" * 80)
print("TEST: finalizar_compra(1)")
print("=" * 80)
print()

try:
    ok, msg = finalizar_compra(1)
    print(f"ok: {ok}")
    print(f"msg: {msg}")
    print()

    if ok:
        print("[OK] finalizar_compra completado sin error")
    else:
        print(f"[ERROR] {msg}")
        sys.exit(1)

except Exception as e:
    print(f"[EXCEPTION] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
