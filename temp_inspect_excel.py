import pandas as pd

xl = pd.ExcelFile(r'C:\Users\hecto\Downloads\VTA SM 02 AL 16.xlsx')
print('Hojas:', xl.sheet_names)

df = pd.read_excel(xl, sheet_name='st+vt+RC', dtype=object, keep_default_na=False, nrows=905)
print('\nColumnas totales:', len(df.columns))
print('\nPrimeras 15 columnas:')
for i, col in enumerate(list(df.columns)[:15]):
    print(f'  [{i}] {col}')

print('\n\n=== FILA 903 (índice 902) - COLUMNA J ===')
if len(df) > 902:
    print(f'Total filas: {len(df)}')
    fila_903 = df.iloc[902]
    print(f'\nColumna J (índice 9): {list(df.columns)[9] if len(df.columns) > 9 else "NO EXISTE"}')
    if len(df.columns) > 9:
        print(f'Valor: {fila_903.iloc[9]}')

    print('\n--- Todas las columnas fila 903 ---')
    for i, col in enumerate(df.columns):
        print(f'[{i}] {col}: {fila_903[col]}')
else:
    print(f'El Excel solo tiene {len(df)} filas, no llega a 903')

print('\n\n=== BÚSQUEDA COLUMNA "GRADA" ===')
grada_cols = [i for i, col in enumerate(df.columns) if 'grada' in str(col).lower()]
if grada_cols:
    for idx in grada_cols:
        col_name = df.columns[idx]
        print(f'\nColumna [{idx}]: {col_name}')
        print('Primeros 10 valores:')
        for i in range(min(10, len(df))):
            print(f'  fila {i}: {df.iloc[i][col_name]}')
else:
    print('No se encontró columna "grada"')
