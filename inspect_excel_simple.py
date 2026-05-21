#!/usr/bin/env python3
import sys
sys.path.insert(0, r'C:\Users\hecto\Nexus_Core\control_central')

from modules.balance_tiendas_retail import st_vt_rc_import as retail

file_path = r'C:\Users\hecto\Downloads\VTA SM 02 AL 16.xlsx'

print(f"Leyendo: {file_path}\n")
raw, sheet_name, meta = retail.read_excel_retail_sheet(file_path, engine='openpyxl')

print(f"Hoja encontrada: {sheet_name}")
print(f"Total filas raw: {len(raw)}")
print(f"Total columnas raw: {len(raw.columns)}\n")

print("=== COLUMNAS RAW ===")
for i, col in enumerate(raw.columns):
    print(f"[{i}] {col}")

if len(raw) >= 903:
    print(f"\n\n=== FILA 903 (índice 902) ===")
    fila_903 = raw.iloc[902]
    for i, col in enumerate(raw.columns[:15]):
        val = fila_903[col]
        print(f"[{i}] {col}: {val}")

    if len(raw.columns) > 9:
        print(f"\n*** COLUMNA J (índice 9): {raw.columns[9]} ***")
        print(f"Valor fila 903: {fila_903.iloc[9]}")
else:
    print(f"\nEl Excel tiene {len(raw)} filas, no llega a 903")

print("\n\n=== NORMALIZACIÓN ===")
norm, errs = retail.normalize_retail_dataframe(raw)
print(f"Filas normalizadas: {len(norm)}")
print(f"Errores: {errs}")

if 'grada' in norm.columns:
    print("\n=== COLUMNA 'GRADA' (post-normalización) ===")
    print("Primeros 10 valores:")
    for i in range(min(10, len(norm))):
        print(f"  fila {i}: {norm.iloc[i]['grada']}")

    if len(norm) >= 903:
        print(f"\nFila 903 grada: {norm.iloc[902]['grada']}")
