# Ubicación: C:\Users\hecto\Documents\Prg_locales\I_R_G\check_aggrid_types.py
import pandas as pd
import streamlit as st

def audit_dataframe_for_grid(df, table_name):
    print(f"\n--- AUDITORÍA DE DATOS: {table_name} ---")
    print(f"Columnas detectadas: {list(df.columns)}")

    for col in df.columns:
        dtype = df[col].dtype
        sample_value = df[col].iloc[0] if not df.empty else "N/A"

        # Verificamos si es numérico real o un objeto que parece número
        is_numeric = pd.api.types.is_numeric_dtype(df[col])

        status = "✅ NUMÉRICO" if is_numeric else "❌ OBJETO/TEXTO"
        print(f"Columna: {col:20} | Tipo: {str(dtype):12} | {status} | Ejemplo: {sample_value}")

    print("-" * 40 + "\n")

# Agregá este llamado en tu ui.py justo antes del AgGrid:
# audit_dataframe_for_grid(df, table_name)