# =============================================================================
# MÓDULO: Intención de Compra
# ARCHIVO: modules/intencion_compra/sidebar.py
# DESCRIPCIÓN: Controles de filtro del sidebar.
#              Registrado como sidebar_fn en MODULE_INFO.
#              Almacena filtros en st.session_state["ic_filtros"].
# =============================================================================

import streamlit as st
from modules.intencion_compra.logic import get_marcas


_ESTADOS = ["TODOS", "PENDIENTE_OPERATIVO", "APROBADO", "VINCULADO_PP"]


def render_sidebar():
    """
    Sidebar del módulo Intención de Compra.
    El Dispatcher (core/sidebar.py) llama esta función dinámicamente.
    """
    if "ic_filtros" not in st.session_state:
        st.session_state["ic_filtros"] = {"estado": "TODOS", "id_marca": None}

    with st.sidebar:
        st.markdown("### Filtros de Vista")

        # ── ESTADO ───────────────────────────────────────────────────────────
        with st.expander("📌 Estado", expanded=True):
            estado_actual = st.session_state["ic_filtros"].get("estado", "TODOS")
            idx = _ESTADOS.index(estado_actual) if estado_actual in _ESTADOS else 0
            estado = st.selectbox(
                "Estado:",
                options=_ESTADOS,
                index=idx,
                key="ic_sb_estado",
            )
            st.session_state["ic_filtros"]["estado"] = estado

        # ── MARCA ─────────────────────────────────────────────────────────────
        with st.expander("🏷️ Marca", expanded=True):
            df_marcas = get_marcas()
            if not df_marcas.empty:
                opciones = {"TODAS": None}
                opciones.update(
                    {row["descp_marca"]: row["id_marca"]
                     for _, row in df_marcas.iterrows()}
                )
                marca_actual_id = st.session_state["ic_filtros"].get("id_marca")
                marca_actual_nombre = next(
                    (k for k, v in opciones.items() if v == marca_actual_id), "TODAS"
                )
                sel = st.selectbox(
                    "Marca:",
                    options=list(opciones.keys()),
                    index=list(opciones.keys()).index(marca_actual_nombre),
                    key="ic_sb_marca",
                )
                st.session_state["ic_filtros"]["id_marca"] = opciones[sel]

        # ── NUEVA INTENCIÓN (acceso rápido) ───────────────────────────────────
        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        if st.button(
            "➕ Nueva Intención",
            use_container_width=True,
            key="ic_sb_nueva",
            help="Desplaza la vista al formulario de alta",
        ):
            st.session_state["ic_mostrar_form"] = True
            st.rerun()
