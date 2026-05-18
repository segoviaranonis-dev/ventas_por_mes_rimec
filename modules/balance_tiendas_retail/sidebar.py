# =============================================================================
# Sidebar: imágenes locales (sesión) — Retail multi-tienda
# =============================================================================

from __future__ import annotations

import streamlit as st

from modules.balance_tiendas_retail import logic as bt


def render_balance_sidebar():
    st.markdown("### 🖼️ Imágenes (local, sesión)")
    st.caption(
        "Índice en memoria para miniaturas: **no** se suben archivos a Supabase. "
        "Al cerrar sesión o el navegador se pierde. **Limpiar** borra antes. "
        "Las pestañas **Estadística ventas/stock** también muestran miniaturas si hay carpeta."
    )
    st.caption(
        "Formato estándar de este proveedor: **`linea-referencia-material-color.jpg`** "
        "(ej. `1143-309-5881-47164.jpg`). También se aceptan variantes con `_` o `|`. "
        "La ruta debe existir en el **mismo equipo** donde ejecutás Streamlit."
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📂 Elegir carpeta…", use_container_width=True, key="retail_pick_dir"):
            picked = bt.pick_folder_dialog()
            if picked:
                st.session_state["retail_img_dir"] = picked.strip()
                st.session_state["retail_img_idx"] = bt.build_image_index(picked.strip())
                st.rerun()
    with col_b:
        if st.button("✕ Limpiar", use_container_width=True, key="retail_clear_dir"):
            st.session_state.pop("retail_img_dir", None)
            st.session_state.pop("retail_img_idx", None)
            st.rerun()

    path_in = st.text_input(
        "Ruta carpeta imágenes",
        value=st.session_state.get("retail_img_dir", ""),
        placeholder=r"C:\Fotos\Calzados",
        key="retail_path_input",
    )
    p = (path_in or "").strip()
    if p != (st.session_state.get("retail_img_dir") or ""):
        st.session_state["retail_img_dir"] = p
        st.session_state["retail_img_idx"] = bt.build_image_index(p) if p else {}

    if p:
        nimg = len(st.session_state.get("retail_img_idx") or {})
        st.info(f"{nimg} archivo(s) en carpeta (vista local).")
