"""
OT-WEB-PRECIO-509-001 N2-N5: UI Streamlit para diccionario markup web por caso.
"""
import streamlit as st
import pandas as pd
from modules.web_precio_caso.logic import (
    listar_reglas,
    crear_regla,
    editar_regla,
    desactivar_regla,
    activar_regla,
)


def render_web_precio_caso() -> None:
    """
    N2-N5: Interfaz editable para caso_precio_web_regla.
    Sin hardcodear casos (N6) — todo desde BD.
    """
    st.title("🌐 Diccionario Precios Web")
    st.markdown("""
    Gestión de markup por caso comercial para precios de venta en **rimec-web**.

    **Fórmula**: `Precio Web = LPN × (1 + markup%) redondeado a centena`

    **Casos configurables sin deploy** — los cambios se aplican inmediatamente en catálogo web.
    """)

    # N3: Listar reglas existentes
    df = listar_reglas()

    if df is None or df.empty:
        st.warning("No hay reglas configuradas. Crea la primera regla abajo.")
        df = pd.DataFrame(columns=["id", "caso_codigo", "markup_pct", "descripcion", "activo", "updated_at"])

    st.markdown("### 📋 Reglas actuales")

    # Tabla con edición inline
    with st.container():
        for idx, row in df.iterrows():
            regla_id = row["id"]
            caso = row["caso_codigo"]
            markup = row["markup_pct"]
            desc = row["descripcion"] or ""
            activo = row["activo"]

            col1, col2, col3, col4, col5 = st.columns([2, 1.5, 3, 1, 1])

            with col1:
                st.text_input(
                    "Caso",
                    value=caso,
                    disabled=True,
                    key=f"caso_{regla_id}",
                    label_visibility="collapsed",
                )

            with col2:
                nuevo_markup = st.number_input(
                    "Markup %",
                    value=float(markup),
                    min_value=0.0,
                    max_value=200.0,
                    step=5.0,
                    format="%.2f",
                    key=f"markup_{regla_id}",
                    label_visibility="collapsed",
                )

            with col3:
                nueva_desc = st.text_input(
                    "Descripción",
                    value=desc,
                    key=f"desc_{regla_id}",
                    label_visibility="collapsed",
                )

            with col4:
                estado = "✓ Activo" if activo else "✗ Inactivo"
                st.markdown(f"<div style='margin-top:8px;font-size:0.85rem;'>{estado}</div>", unsafe_allow_html=True)

            with col5:
                # N4: Botón guardar cambios
                if nuevo_markup != markup or nueva_desc != desc:
                    if st.button("💾", key=f"save_{regla_id}", help="Guardar cambios"):
                        result = editar_regla(regla_id, nuevo_markup, nueva_desc)
                        if result["ok"]:
                            st.success(f"✓ {caso} actualizado")
                            st.rerun()
                        else:
                            st.error(f"Error: {result['error']}")

                # N3: Botón activar/desactivar
                if activo:
                    if st.button("🔴", key=f"deact_{regla_id}", help="Desactivar"):
                        result = desactivar_regla(regla_id)
                        if result["ok"]:
                            st.success(f"✓ {caso} desactivado")
                            st.rerun()
                        else:
                            st.error(f"Error: {result['error']}")
                else:
                    if st.button("🟢", key=f"act_{regla_id}", help="Reactivar"):
                        result = activar_regla(regla_id)
                        if result["ok"]:
                            st.success(f"✓ {caso} reactivado")
                            st.rerun()
                        else:
                            st.error(f"Error: {result['error']}")

            st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)

    # N3: Agregar nueva regla
    st.markdown("### ➕ Agregar nuevo caso")

    col_a, col_b, col_c = st.columns([2, 1.5, 1])

    with col_a:
        nuevo_caso = st.text_input("Código de caso", placeholder="Ej: NUEVO-CASO", key="new_caso")

    with col_b:
        nuevo_markup_val = st.number_input(
            "Markup %",
            value=50.0,
            min_value=0.0,
            max_value=200.0,
            step=5.0,
            format="%.2f",
            key="new_markup",
        )

    with col_c:
        nueva_desc_val = st.text_input("Descripción", placeholder="Opcional", key="new_desc")

    if st.button("➕ Crear regla", type="primary"):
        if not nuevo_caso.strip():
            st.error("Código de caso no puede estar vacío")
        else:
            result = crear_regla(nuevo_caso, nuevo_markup_val, nueva_desc_val)
            if result["ok"]:
                st.success(f"✓ Caso '{nuevo_caso}' creado con markup +{nuevo_markup_val}%")
                st.rerun()
            else:
                st.error(f"Error: {result['error']}")

    # N2: Criterio verificación — usuario puede cambiar CHINELO de 40% a 45%
    st.markdown("---")
    st.markdown("### 🧪 Prueba de configuración")
    st.markdown("""
    **Criterio N2 (OT-509):** Usuario puede cambiar markup de cualquier caso y guardar sin deploy.

    Ejemplo: Edita CHINELO de +40% a +45%, presiona 💾, verifica que se guarda.
    """)
