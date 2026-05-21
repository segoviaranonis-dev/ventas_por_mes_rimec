import pandas as pd

file_path = r'C:\Users\hecto\Downloads\VTA SM 02 AL 16.xlsx'

print(f"=== Inspeccionando: {file_path} ===\n")

# Leer Excel
xl = pd.ExcelFile(file_path, engine='openpyxl')
print(f"Hojas: {xl.sheet_names}\n")

# Leer hoja st+vt+RC
df = pd.read_excel(xl, sheet_name='st+vt+RC', dtype=object, keep_default_na=False)
print(f"Dimensiones: {len(df)} filas x {len(df.columns)} columnas\n")

print("=== COLUMNAS (primeras 15) ===")
for i, col in enumerate(list(df.columns)[:15]):
    print(f"[{i}] {col}")

# Verificar fila 903
if len(df) >= 903:
    print(f"\n\n=== FILA 903 (índice 902) - TODAS LAS COLUMNAS ===")
    fila_903 = df.iloc[902]
    for i, col in enumerate(df.columns):
        val = str(fila_903[col]).strip() if pd.notna(fila_903[col]) else "(vacío)"
        if val and val != "(vacío)":
            print(f"[{i}] {col}: {val}")

    # Columna J específicamente
    if len(df.columns) > 9:
        print(f"\n*** COLUMNA J (índice 9) ***")
        print(f"Nombre: {df.columns[9]}")
        print(f"Valor fila 903: '{fila_903.iloc[9]}'")
else:
    print(f"\nEl archivo solo tiene {len(df)} filas")

# Buscar columna grada
print("\n\n=== COLUMNA 'GRADA' ===")
grada_idx = None
for i, col in enumerate(df.columns):
    if 'grada' in str(col).lower():
        grada_idx = i
        print(f"Encontrada en índice [{i}]: {col}")
        break

if grada_idx is not None:
    col_name = df.columns[grada_idx]
    print(f"\nPrimeros 20 valores de '{col_name}':")
    for i in range(min(20, len(df))):
        val = df.iloc[i][col_name]
        if pd.notna(val) and str(val).strip():
            print(f"  fila {i+1}: {val}")

    if len(df) >= 903:
        print(f"\nFila 903 - {col_name}: '{df.iloc[902][col_name]}'")

    # Buscar valores con formato caja cerrada
    print(f"\n=== Valores con paréntesis en '{col_name}' (cajas cerradas) ===")
    count = 0
    for i, val in enumerate(df[col_name]):
        if pd.notna(val) and '(' in str(val) and ')' in str(val):
            print(f"  fila {i+1}: {val}")
            count += 1
            if count >= 10:
                print(f"  ... (mostrando primeras 10)")
                break
else:
    print("No se encontró columna 'grada'")

# Ver columna de origen/tienda
print("\n\n=== COLUMNA ORIGEN/TIENDA ===")
for i, col in enumerate(df.columns):
    if 'tienda' in str(col).lower() or 'origen' in str(col).lower():
        print(f"[{i}] {col}")
        valores_unicos = df[col].value_counts().head(10)
        print(f"  Valores únicos (top 10):")
        for val, cnt in valores_unicos.items():
            print(f"    {val}: {cnt} filas")
