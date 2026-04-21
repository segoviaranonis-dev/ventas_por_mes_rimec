import streamlit as st


def render_sidebar():
    st.markdown(
        "<div style='color:#D4AF37;font-size:.78rem;font-weight:700;"
        "letter-spacing:.07em;text-transform:uppercase;margin-bottom:12px;'>"
        "COMPRA</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.get("cl_selected_id"):
        if st.button("← Volver al listado", key="cl_volver", use_container_width=True):
            st.session_state.pop("cl_selected_id", None)
            st.rerun()
