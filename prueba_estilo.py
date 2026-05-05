# prueba_estilo.py
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder
from core.styles import apply_styles, apply_grid_sandbox_styles, get_group_row_style

st.set_page_config(layout="wide")

# 1. Aplicamos estilos (Base + Aislamiento para Grilla)
apply_styles()
apply_grid_sandbox_styles()

st.title("🧪 Laboratorio Blindado - Chongo Boy")

# Datos de prueba (Nivel 1: Vendedor, Nivel 2: Marca, Nivel 3: Tienda)
df = pd.DataFrame([
    ['PEDRO', 'NIKE', 'TIENDA 1', 5000],
    ['PEDRO', 'NIKE', 'TIENDA 2', 3000],
    ['PEDRO', 'ADIDAS', 'TIENDA 1', 2000]
], columns=['Vendedor', 'Marca', 'Tienda', 'Monto'])

gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_column("Vendedor", rowGroup=True, hide=True)
gb.configure_column("Marca", rowGroup=True, hide=True)
gb.configure_column("Tienda", rowGroup=True, hide=True)
gb.configure_column("Monto", aggFunc='sum')

go = gb.build()

# 2. Inyectamos el estilo de 'Botones' desde el corazón
go['getRowStyle'] = get_group_row_style()

go.update({
    'groupDisplayType': 'groupRows',
    'groupDefaultExpanded': 0,
    'theme': 'alpine'
})

AgGrid(df, gridOptions=go, enable_enterprise_modules=True, allow_unsafe_jscode=True)