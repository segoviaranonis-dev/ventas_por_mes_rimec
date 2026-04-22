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
        # Botón Streamlit oculto — el FAB lo activa vía JS
        if st.button("↩", key="btn_hub_content"):
            st.session_state.piso_actual = "home"
            st.rerun()

        st.markdown("""
        <style>
        /* Ocultar el botón Streamlit trigger */
        div[data-testid="stMainBlockContainer"]
            div[data-testid="stVerticalBlock"]
            > div:first-child
            button[data-testid="baseButton-secondary"] {
            position: absolute !important;
            opacity: 0 !important;
            pointer-events: none !important;
            width: 1px !important;
            height: 1px !important;
            overflow: hidden !important;
        }

        /* FAB — Floating Action Button */
        .nexus-fab {
            position: fixed;
            bottom: 2.2rem;
            right: 2.2rem;
            z-index: 99999;
            background: linear-gradient(135deg, #D4AF37 0%, #9A7D10 100%);
            color: #0F172A;
            border: none;
            border-radius: 3rem;
            padding: 0.85rem 1.75rem;
            font-size: 0.88rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.55rem;
            box-shadow:
                0 4px 20px rgba(212, 175, 55, 0.5),
                0 2px 8px  rgba(0, 0, 0, 0.4),
                inset 0 1px 0 rgba(255,255,255,0.2);
            transition: transform 0.18s cubic-bezier(.4,0,.2,1),
                        box-shadow 0.18s cubic-bezier(.4,0,.2,1);
            user-select: none;
        }
        .nexus-fab:hover {
            transform: translateY(-4px) scale(1.04);
            box-shadow:
                0 10px 36px rgba(212, 175, 55, 0.65),
                0 4px 16px  rgba(0, 0, 0, 0.45),
                inset 0 1px 0 rgba(255,255,255,0.25);
        }
        .nexus-fab:active {
            transform: translateY(0) scale(0.97);
            box-shadow: 0 2px 10px rgba(212,175,55,0.4);
        }
        .nexus-fab .fab-icon {
            font-size: 1.1rem;
            line-height: 1;
        }
        </style>

        <button class="nexus-fab" onclick="
            (function(){
                var btn = Array.from(window.parent.document.querySelectorAll('button'))
                    .find(function(b){ return b.innerText.trim() === '↩'; });
                if (btn) btn.click();
            })();
        ">
            <span class="fab-icon">🏠</span> Hub Central
        </button>
        """, unsafe_allow_html=True)

    registry.render(modulo_key)
