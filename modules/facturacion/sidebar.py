import streamlit as st


def render_sidebar():
    st.markdown(
        "<div style='color:#D4AF37;font-size:.78rem;font-weight:700;"
        "letter-spacing:.07em;text-transform:uppercase;margin-bottom:12px;'>"
        "FACTURACIÓN</div>",
        unsafe_allow_html=True,
    )

    vista = st.radio(
        "Vista",
        ["🧾 Facturas Internas", "📦 Carga Manual"],
        key="fac_vista",
        label_visibility="collapsed",
    )
    st.session_state["fac_vista_carga"] = (vista == "📦 Carga Manual")

    st.divider()

    if st.session_state.get("fac_carga_pp_id"):
        if st.button("← Cancelar carga", key="fac_cancel_carga", use_container_width=True):
            st.session_state.pop("fac_carga_pp_id", None)
            st.rerun()
