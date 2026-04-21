import streamlit as st


def render_sidebar():
    st.markdown("### 🛒 Pedidos Web")
    st.markdown("---")

    estado = st.radio(
        "Filtrar por estado",
        options=["PENDIENTE", "CONFIRMADO", "RECHAZADO"],
        index=0,
        key="pw_estado_filtro",
    )

    st.markdown("---")
    st.caption("💡 **Confirmar** descuenta stock del depósito web automáticamente.")

    return estado
