"""
SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
UBICACIÓN: core/sidebar.py
VERSION: 72.0.0 (NEXUS CONSOLE - ACCORDION EDITION)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Consola de mando minimalista basada en acordeones inteligentes.
              Implementa Protocolo Reset y Neutralización SQL 'TODOS'.
"""

import streamlit as st
import time
from core.filters import FilterManager
from core.database import DBInspector, get_engine
from core.settings import settings

def render_sidebar_controls(modulo_key, df_raw=None):
    """
    Orquestador de Mandos v72.0.0.
    Transforma el sidebar en una consola de alta eficiencia con acordeones.
    """
    user_name = st.session_state.get('user', {}).get('name', 'Operador')
    
    with st.sidebar:
        # --- 1. CABECERA DE IDENTIDAD ---
        st.markdown(f"""
            <div style='padding: 5px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 10px;'>
                <h2 style='margin:0; font-size: 1.3rem; color: #FBBF24;'>RIMEC NEXUS</h2>
                <p style='margin:0; font-size: 0.8rem; opacity: 0.7;'>👤 {user_name}</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Status de Conexión Minimalista
        render_connection_status()

        if modulo_key == "sales":
            # --- 2. ACORDEÓN 1: ESTRATEGIA DE CRECIMIENTO ---
            with st.expander("📈 Estrategia de Crecimiento", expanded=False):
                val_obj = FilterManager.get_draft("objetivo_pct", 20)
                obj = st.select_slider(
                    "Incremento Objetivo (%):",
                    options=list(range(0, 105, 5)),
                    value=val_obj,
                    key="slider_estrategia_nexus"
                )
                if obj != val_obj:
                    FilterManager.update_draft("objetivo_pct", obj)

            # --- 3. ACORDEÓN 2: HORIZONTE TEMPORAL ---
            with st.expander("📅 Horizonte Temporal", expanded=False):
                st.markdown("<p style='font-size:0.8rem; font-weight:bold;'>Accesos Rápidos:</p>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                meses_full = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

                draft_meses = FilterManager.get_draft("meses", [])
                
                # Determinación de botones activos
                is_1er_sem = set(draft_meses) == set(meses_full[:6])
                is_2do_sem = set(draft_meses) == set(meses_full[6:])
                is_ano = set(draft_meses) == set(meses_full)

                if c1.button("1er S", type="primary" if is_1er_sem else "secondary", use_container_width=True, help="Enero-Junio"):
                    FilterManager.update_meses_shortcut(meses_full[:6])
                    st.rerun()
                if c2.button("2do S", type="primary" if is_2do_sem else "secondary", use_container_width=True, help="Julio-Diciembre"):
                    FilterManager.update_meses_shortcut(meses_full[6:])
                    st.rerun()
                if c3.button("AÑO", type="primary" if is_ano else "secondary", use_container_width=True, help="Año Completo"):
                    FilterManager.update_meses_shortcut(meses_full)
                    st.rerun()

                # Multi-selector de meses
                sel_meses = st.multiselect(
                    "Selección Manual:",
                    options=meses_full,
                    default=draft_meses,
                    key=f"ms_meses_{st.session_state.get('meses_key_tracker', 0)}"
                )
                if set(sel_meses) != set(draft_meses):
                    FilterManager.update_draft("meses", sel_meses)

            # --- 4. ACORDEÓN 3: PARÁMETROS MAESTROS (EL CEREBRO) ---
            u_sales = FilterManager.get_sales_ui_universe(df_raw)
            
            with st.expander("🏗️ Parámetros Maestros", expanded=False):
                # Departamento con neutralización TODOS
                deptos = u_sales.get("departamentos", ["TODOS", "CALZADOS"])
                cur_depto = FilterManager.get_draft("departamento", "TODOS")
                idx_depto = deptos.index(cur_depto) if cur_depto in deptos else 0
                
                depto = st.selectbox("Departamento:", options=deptos, index=idx_depto)
                if depto != cur_depto:
                    FilterManager.update_draft("departamento", depto)

                # Categoría con neutralización TODOS
                cats = u_sales.get("categorias", ["TODOS"])
                # Mapeo inverso para UI (Nombre a ID)
                rev_map = {v: k for k, v in FilterManager.CATEGORIA_MAP.items()}
                current_cat_names = [rev_map.get(c, c) for c in FilterManager.get_draft("categoria_ids", [])]
                
                sel_cats = st.multiselect("Categorías:", options=cats, default=current_cat_names)
                if sel_cats != current_cat_names:
                    FilterManager.update_draft("categoria_ids", sel_cats)

            # --- 5. ACORDEÓN 4: FILTROS DE ENTIDAD (AJUSTE FINO) ---
            with st.expander("🔍 Filtros de Entidad", expanded=False):
                def render_ms_filtros(label, key_data, key_draft):
                    options = u_sales.get(key_data, [])
                    current = FilterManager.get_draft(key_draft, [])
                    valid_defaults = [v for v in current if v in options]
                    sel = st.multiselect(label, options=options, default=valid_defaults)
                    if set(sel) != set(current):
                        FilterManager.update_draft(key_draft, sel)
                        st.rerun() # Cascada inmediata en memoria

                render_ms_filtros("Marcas:", "marcas", "marcas")
                render_ms_filtros("Cadenas:", "cadenas", "cadenas")
                render_ms_filtros("Vendedores:", "vendedores", "vendedores")
                render_ms_filtros("Clientes:", "clientes", "clientes")
                
                # Búsqueda por ID
                id_actual = FilterManager.get_draft("id_cliente_exacto") or ""
                id_input = st.text_input("Búsqueda por ID Cliente:", value=str(id_actual))
                if id_input != str(id_actual):
                    FilterManager.update_draft("id_cliente_exacto", id_input)

            # --- 6. PANEL DE DISPARO (FIJO AL FINAL) ---
            st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
            
            col_reset, col_exe = st.columns([1, 1.3])
            
            with col_reset:
                # Estilo Rojo Tenue / Outline
                if st.button("🔄 REINICIAR", use_container_width=True, help="Vuelve a Calzados/Programado"):
                    DBInspector.log("[UI-RESET] Ejecutando Protocolo Volver a Casa.", "AVISO")
                    FilterManager.reset_all_filters()
                    st.rerun()

            with col_exe:
                # Estilo Sólido Azul/Oro (Primary)
                if st.button("🚀 EJECUTAR ORDEN", type="primary", use_container_width=True):
                    DBInspector.log("[UI-COMMIT] Disparando Consulta SQL Íntegra.", "SUCCESS")
                    FilterManager.commit_filters()
                    st.rerun()

        elif modulo_key == "home":
            st.info("Consola Nexus lista para navegación.")

def render_connection_status():
    """Indicador de salud de red minimalista."""
    try:
        get_engine()
        st.markdown("<p style='color: #10B981; font-size: 0.7rem; margin-bottom: 15px;'>● Conexión Estable</p>", unsafe_allow_html=True)
    except:
        st.markdown("<p style='color: #EF4444; font-size: 0.7rem; margin-bottom: 15px;'>● Error de Enlace</p>", unsafe_allow_html=True)