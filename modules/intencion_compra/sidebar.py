# =============================================================================
# MÓDULO: Intención de Compra
# ARCHIVO: modules/intencion_compra/sidebar.py
# DESCRIPCIÓN: Accesos rápidos del sidebar.
#              La separación PENDIENTES / HISTORIAL se maneja con tabs en la UI.
# =============================================================================

import streamlit as st


def render_sidebar():
    """
    Sidebar del módulo Intención de Compra.
    El Dispatcher (core/sidebar.py) llama esta función dinámicamente.
    """
    with st.sidebar:
        st.markdown("### Intención de Compra")

        # ── NUEVA INTENCIÓN (acceso rápido) ───────────────────────────────────
        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
        if st.button(
            "➕ Nueva Intención",
            use_container_width=True,
            key="ic_sb_nueva",
            help="Iniciar nueva IC desde el Paso A",
        ):
            st.session_state.pop("ic_tipo_id", None)
            st.session_state.pop("ic_cat_id", None)
            st.session_state["ic_vista"] = "paso_a"
            st.rerun()

        if st.button(
            "📋 Ver Bandeja",
            use_container_width=True,
            key="ic_sb_dashboard",
            help="Volver al dashboard de ICs",
        ):
            st.session_state["ic_vista"] = "dashboard"
            st.rerun()
