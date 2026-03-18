"""
SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
UBICACIÓN: core/navigation.py
VERSION: 94.4.0 (PREMIUM - ENGINE INJECTION READY)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Orquestador de navegación con Inyección de Motor v4.3.
             Control de Bucle `piso_actual` con Telemetría Activa.
"""

import streamlit as st
import time
from core.settings import settings
from core.styles import apply_ui_theme
from core.sidebar import render_sidebar_controls
from core.auth import AuthManager
from core.database import DBInspector, engine  # <--- IMPORTACIÓN DEL MOTOR CENTRAL

# Importación diferida para evitar colapsos de memoria
import modules.import_data.ui as import_ui

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES LOCALES (ICONOGRAFÍA INTEGRADA)
# ─────────────────────────────────────────────────────────────────────────────
ICONS = {
    "HOME": "🏠",
    "IMPORT": "📥",
    "SALES": "📊",
    "DIAG": "⚙️",
    "LOGOUT": "🚪"
}

def render_sidebar():
    """
    Orquestador de Navegación v94.4.
    Gestiona el flujo vital de datos y suministra el motor a los módulos.
    """
    t_start = time.time()
    user_data = st.session_state.get('user', {})
    user_name = user_data.get('name', 'Usuario')
    user_role = AuthManager.get_role()

    # 1. Asegurar Cimientos
    if "piso_actual" not in st.session_state:
        st.session_state.piso_actual = "home"

    # APLICAR ADN VISUAL (OBSIDIAN ARMOR)
    apply_ui_theme()

    with st.sidebar:
        # --- 1. BLOQUE DE IDENTIDAD ---
        color_ok = getattr(settings, 'COLOR_SUCCESS', '#10B981')
        c_name = getattr(settings, 'COMPANY_NAME', 'RIMEC')
        s_name = getattr(settings, 'SYSTEM_NAME', 'NEXUS CORE')

        st.markdown(f"""
            <div style='padding:1rem 0; margin-bottom:1rem; border-bottom:1px solid rgba(255,255,255,0.1);'>
                <h3 style='margin:0; font-size:1.1rem; color: #F8FAFC; letter-spacing:0.5px;'>
                    <span style='color:{color_ok}; font-size:0.8rem;'>●</span> {c_name}
                </h3>
                <div style='color:#94A3B8; font-size:0.75rem; margin-top:2px;'>
                    {s_name} {getattr(settings, 'VERSION', 'v94.4.0')}
                </div>
            </div>
        """, unsafe_allow_html=True)

        # --- 2. MENÚ PRINCIPAL ---
        st.markdown("<p style='color:#64748B; font-size:0.75rem; font-weight:600; margin-bottom:0.5rem;'>MÓDULOS ACTIVOS</p>", unsafe_allow_html=True)

        opciones = {
            f"{ICONS['HOME']} Hub Central": "home",
            f"{ICONS['SALES']} Inteligencia de Ventas": "sales",
            f"{ICONS['IMPORT']} Motor de Importación": "import",
            f"{ICONS['DIAG']} Diagnóstico de Red": "diagnostics"
        }

        # Vista Admin solo si es Director / Root
        if user_role in ['root', 'director']:
            opciones[f"⚙️ Panel Táctico (Admin)"] = "admin"

        # Sincronizar selección visual con el estado interno
        nav_list = list(opciones.keys())
        current_index = 0
        for i, val in enumerate(opciones.values()):
            if val == st.session_state.piso_actual:
                current_index = i

        seleccion = st.radio(
            "Navegación",
            options=nav_list,
            index=current_index,
            label_visibility='collapsed',
            key="main_nav_radio"
        )
        modulo_key = opciones[seleccion]

        # --- [SOLUCIÓN] GATILLO DE CARGA CONTROLADO ---
        if st.session_state.piso_actual != modulo_key:
            DBInspector.log(f"🧭 [NAV] Cambio de sector: {st.session_state.piso_actual} -> {modulo_key}", "V2-TRACE")
            st.session_state.piso_actual = modulo_key
            st.rerun()

    # --- 3. EXTRACCIÓN DEL UNIVERSO PARA LA CASCADA ---
    raw_universe = st.session_state.get('raw_universe') if modulo_key == "sales" else None

    # --- 4. RENDER DE CONTROLES ESPECÍFICOS ---
    try:
        render_sidebar_controls(modulo_key, df_raw=raw_universe)
    except Exception as e:
        DBInspector.log(f"[CRÍTICO] Fallo Render Sidebar: {e}", "ERROR")
        st.sidebar.error("Error en Controles Nexus.")

    # --- 5. LOGOUT ---
    with st.sidebar:
        st.markdown("<br>" * 2, unsafe_allow_html=True)
        st.divider()
        col1, col2 = st.columns([0.2, 0.8])
        if col1.button(ICONS['LOGOUT'], key="btn_logout", help="Cerrar Sesión"):
            AuthManager.logout()
            st.rerun()
        col2.caption(f"Operador: **{user_name}**")

    # REGISTRO DE TRÁFICO FINAL
    duracion = (time.time() - t_start) * 1000
    DBInspector.log(f"🧭 [NAV] Sector activo: {modulo_key.upper()}", "V2-TRACE")

    return modulo_key

def render_page_content(modulo_key):
    """
    Despliega el contenido del módulo inyectando las dependencias necesarias.
    """
    if modulo_key == "import":
        # PASO DEL MOTOR (ENGINE) AL MÓDULO DE IMPORTACIÓN
        import_ui.render_import_interface(engine)

    elif modulo_key == "home":
        from modules.home.ui import render_home
        render_home()

    elif modulo_key == "sales":
        from modules.sales_report.ui import render_sales_interface
        render_sales_interface()