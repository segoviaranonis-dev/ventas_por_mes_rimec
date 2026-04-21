# =============================================================================
# MÓDULO: Pedido Proveedor
# ARCHIVO: modules/pedido_proveedor/sidebar.py
# DESCRIPCIÓN: Sidebar contextual — se adapta a la vista activa.
#
#  LISTA     → "➕ Nuevo Pedido" + "🛍️ Showroom" + filtros de estado
#  DETALLE   → "← Volver a lista"
#  FORM      → "← Volver a lista"
#  SHOWROOM  → "← Volver a lista"
# =============================================================================

import streamlit as st

from core.database import get_dataframe


@st.cache_data(ttl=300)
def _get_marcas_pp() -> list[str]:
    """Marcas presentes en pedido_proveedor_detalle (NEXUS PPs)."""
    df = get_dataframe("""
        SELECT DISTINCT mv.descp_marca
        FROM pedido_proveedor_detalle ppd
        JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
        WHERE pp.estado IN ('ABIERTO', 'CERRADO', 'ANULADO')
          AND ppd.linea IS NOT NULL
        ORDER BY mv.descp_marca
    """)
    return df["descp_marca"].tolist() if not df.empty else []


def _limpiar_estado_pp():
    """Limpia todo el estado de navegación del módulo."""
    for k in (
        "pp_selected_id", "pp_mostrar_form", "pp_vista_showroom",
        "pp_parsed_df", "pp_parsed_total", "pp_parsed_error", "_pp_last_ic",
    ):
        st.session_state.pop(k, None)


def render_sidebar():
    st.markdown("### 📦 Pedido Proveedor")
    st.divider()

    id_sel        = st.session_state.get("pp_selected_id")
    show_form     = st.session_state.get("pp_mostrar_form", False)
    show_showroom = st.session_state.get("pp_vista_showroom", False)

    # ── Vistas secundarias: solo mostrar "Volver" ─────────────────────────────
    if id_sel or show_form or show_showroom:
        if st.button("← Volver a lista", use_container_width=True, key="pp_btn_volver"):
            _limpiar_estado_pp()
            st.rerun()

        if id_sel:
            st.divider()
            st.caption(f"PP ID: **{id_sel}**")

        return

    # ── Vista LISTA: acciones y filtros ───────────────────────────────────────
    if st.button(
        "📊 Auditoría de Saldo",
        use_container_width=True,
        type="primary",
        key="pp_btn_showroom",
    ):
        _limpiar_estado_pp()
        st.session_state["pp_vista_showroom"] = True
        st.rerun()

    st.divider()

    if st.button("➕ Nuevo Pedido", use_container_width=True, key="pp_btn_nuevo"):
        _limpiar_estado_pp()
        st.session_state["pp_mostrar_form"] = True
        st.rerun()

    st.markdown("#### Filtros")

    estado = st.selectbox(
        "Estado",
        ["TODOS", "ABIERTO", "CERRADO", "ANULADO"],
        key="pp_filtro_estado",
    )

    marca = st.selectbox(
        "Marca",
        ["TODAS"] + _get_marcas_pp(),
        key="pp_filtro_marca",
    )

    filtros = {}
    if estado != "TODOS":
        filtros["estado"] = estado
    if marca != "TODAS":
        filtros["marca"] = marca

    st.session_state["pp_filtros"] = filtros
