# Ubicación: C:\Users\hecto\Documents\Prg_locales\I_R_G\modules\system_status\ui.py
import streamlit as st
from core.database import get_engine, DBInspector
from core.styles import header_section, apply_styles
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import pandas as pd
import time

def render_system_status_interface():
    """
    Renderiza el módulo de diagnóstico del sistema.
    AUDITORÍA: Monitoreo de salud de tablas y conexión.
    """
    # ANDAMIO 1: Terminal parlante
    print("\n" + "🩺" + "═"*60)
    print(f"🩺 [DIAGNÓSTICO] {time.strftime('%H:%M:%S')} - Iniciando chequeo de sistemas...")

    apply_styles()
    header_section("Diagnóstico", "Salud de la Infraestructura")

    # --- MONITOR DE MÉTRICAS ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Estado DB", "🟢 Conectado")
    with col2:
        st.metric("Pooler", "Activo")
    with col3:
        st.metric("Región", "sa-east-1")

    st.divider()

    # --- VERIFICACIÓN DE TABLAS (La Jaula del León) ---
    st.subheader("🗄️ Verificación de Tablas en Tiempo Real")

    try:
        engine = get_engine()
        if engine:
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tablas = inspector.get_table_names()

            print(f"📊 [DIAGNÓSTICO] Tablas encontradas en DB: {len(tablas)}")
            st.success(f"✅ {len(tablas)} tablas detectadas en el cerebro del sistema")

            df_tablas = pd.DataFrame({
                'Número': range(1, len(tablas) + 1),
                'Nombre de Tabla': sorted(tablas)
            })

            # Configuración de AG Grid para el diagnóstico
            gb = GridOptionsBuilder.from_dataframe(df_tablas)
            gb.configure_pagination(paginationPageSize=10)
            gb.configure_default_column(resizable=True, filterable=True, sortable=True)
            grid_options = gb.build()

            print(f"🦁 [DIAGNÓSTICO] Renderizando listado de tablas con AgGrid...")
            AgGrid(
                df_tablas,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.NO_UPDATE,
                theme='streamlit',
                height=400,
                key="grid_diagnostic_tables"
            )
            print(f"✅ [DIAGNÓSTICO] AgGrid renderizado sin errores.")

        else:
            print("🚨 [DIAGNÓSTICO] ERROR: Engine no disponible.")
            st.error("❌ No se pudo conectar a la base de datos")

    except Exception as e:
        print(f"🔥 [DIAGNÓSTICO] FALLO CRÍTICO: {str(e)}")
        st.error(f"❌ Error al verificar tablas: {e}")

    print(f"🩺 [DIAGNÓSTICO] Chequeo finalizado.\n" + "═"*60)

    # Botones de acción
    if st.button("📊 Forzar Actualización de Estadísticas", use_container_width=True):
        print("⚡ [DIAGNÓSTICO] Solicitando RERUN del sistema...")
        st.rerun()