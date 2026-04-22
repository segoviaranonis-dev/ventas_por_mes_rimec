# =============================================================================
# SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
# UBICACIÓN: core/navigation.py
# VERSION: 2.0.0 (REGISTRY-DRIVEN)
# DESCRIPCIÓN: Orquestador de navegación alimentado por el Registry central.
#              Agregar un módulo nuevo = 0 cambios en este archivo.
# =============================================================================

import streamlit as st
from core.settings import settings
from core.styles import apply_ui_theme
from core.sidebar import render_sidebar_controls
from core.auth import AuthManager
from core.database import DBInspector
import core.registry as registry


def render_sidebar() -> str:
    """
    Construye el sidebar y retorna la key del módulo activo.
    El menú se genera dinámicamente desde el Registry según el rol del usuario.
    """
    user_data  = st.session_state.get("user", {})
    user_name  = user_data.get("name", "Usuario")
    user_role  = AuthManager.get_role()

    if "piso_actual" not in st.session_state:
        st.session_state.piso_actual = "home"

    apply_ui_theme()

    with st.sidebar:
        # ── BLOQUE DE IDENTIDAD ──────────────────────────────────────────────
        color_ok = getattr(settings, "COLOR_SUCCESS", "#10B981")
        st.markdown(f"""
            <div style='padding:1rem 0; margin-bottom:1rem; border-bottom:1px solid rgba(255,255,255,0.1);'>
                <h3 style='margin:0; font-size:1.1rem; color:#F8FAFC; letter-spacing:0.5px;'>
                    <span style='color:{color_ok}; font-size:0.8rem;'>●</span>
                    {settings.COMPANY_NAME}
                </h3>
                <div style='color:#94A3B8; font-size:0.75rem; margin-top:2px;'>
                    {settings.SYSTEM_NAME} {settings.VERSION}
                </div>
            </div>
        """, unsafe_allow_html=True)

        # ── MENÚ DINÁMICO DESDE REGISTRY ────────────────────────────────────
        st.markdown(
            "<p style='color:#64748B; font-size:0.75rem; font-weight:600; margin-bottom:0.5rem;'>"
            "MÓDULOS ACTIVOS</p>",
            unsafe_allow_html=True
        )

        opciones = registry.get_nav_options(user_role)

        if not opciones:
            st.warning("Sin módulos disponibles para tu rol.")
            return "home"

        nav_list = list(opciones.keys())
        current_index = 0
        for i, val in enumerate(opciones.values()):
            if val == st.session_state.piso_actual:
                current_index = i

        seleccion = st.radio(
            "Navegación",
            options=nav_list,
            index=current_index,
            label_visibility="collapsed",
        )
        modulo_key = opciones[seleccion]

        # Si el usuario clickeó el radio (o un botón cambió piso_actual),
        # sincronizamos y recargamos.
        if st.session_state.piso_actual != modulo_key:
            DBInspector.log(
                f"🧭 [NAV] Cambio: {st.session_state.piso_actual} → {modulo_key}",
                "V2-TRACE"
            )
            st.session_state.piso_actual = modulo_key
            st.rerun()

    # ── CONTROLES DE SIDEBAR (dispatcher genérico — agnóstico de módulo) ─────
    try:
        render_sidebar_controls(modulo_key)
    except Exception as e:
        DBInspector.log(f"[CRÍTICO] Fallo Render Sidebar: {e}", "ERROR")
        st.sidebar.error("Error en controles del módulo.")

    # ── LOGOUT ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("<br>" * 2, unsafe_allow_html=True)
        st.divider()
        col1, col2 = st.columns([0.2, 0.8])
        if col1.button("🚪", key="btn_logout", help="Cerrar Sesión"):
            AuthManager.logout()
            st.rerun()
        col2.caption(f"Operador: **{user_name}**")

    DBInspector.log(f"🧭 [NAV] Sector activo: {modulo_key.upper()}", "V2-TRACE")
    return modulo_key


def render_page_content(modulo_key: str) -> None:
    """
    Delega el renderizado al módulo correspondiente a través del Registry.
    Importación dinámica garantiza aislamiento de errores entre módulos.
    """
    if modulo_key != "home":
        col_hub, _ = st.columns([1, 8])
        if col_hub.button("🏠 Hub", key="btn_hub_content", help="Volver al Hub Central"):
            st.session_state.piso_actual = "home"
            st.rerun()

    registry.render(modulo_key)
