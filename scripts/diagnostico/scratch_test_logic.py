import sys
sys.path.append('c:\\Users\\hecto\\Documents\\Prg_locales\\ventas_por_mes_rimec-main')
from modules.compra_legal.logic import get_traspaso_detalle_lines

print("\nTesting get_traspaso_detalle_lines for TRP 12")
df2 = get_traspaso_detalle_lines(12)
print(df2)
print("Empty?", df2.empty)
