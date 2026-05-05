import streamlit as st


def render_sidebar():
    st.markdown(
        "<div style='color:#D4AF37;font-size:.78rem;font-weight:700;"
        "letter-spacing:.07em;text-transform:uppercase;margin-bottom:12px;'>"
        "COMPRA WEB</div>",
        unsafe_allow_html=True,
    )

    estado = st.selectbox(
        "Estado",
        ["TODOS", "ENVIADO", "CONFIRMADO", "BORRADOR"],
        key="cw_select_estado",
        label_visibility="collapsed",
    )
    st.session_state["cw_estado_filtro"] = None if estado == "TODOS" else estado

    st.divider()

    if st.session_state.get("cw_trp_selected_id"):
        if st.button("← Volver", key="cw_volver", use_container_width=True):
            st.session_state.pop("cw_trp_selected_id", None)
            st.rerun()
