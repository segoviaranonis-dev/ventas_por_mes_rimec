"""
SISTEMA: NEXUS CORE — core/sidebar.py
VERSION: 73.0.0 (GENERIC DISPATCHER)
DESCRIPCIÓN: Dispatcher genérico de controles de sidebar.
             No sabe nada de ningún módulo en particular.
             Cada módulo declara sidebar_fn en MODULE_INFO y este archivo
             lo invoca dinámicamente. Agregar módulo #5000 = 0 cambios aquí.
"""

import importlib
import streamlit as st
from core.database import DBInspector, get_engine
import core.registry as registry


def render_sidebar_controls(modulo_key: str) -> None:
    """
    Dispatcher universal de controles de módulo en el sidebar.
    Busca sidebar_fn en el Registry y la invoca dinámicamente.
    Si el módulo no tiene sidebar_fn, no renderiza nada (correcto por diseño).
    """
    with st.sidebar:
        render_connection_status()

    sidebar_fn_path = registry.get_sidebar_fn(modulo_key)
    if not sidebar_fn_path:
        return

    try:
        module_path, fn_name = sidebar_fn_path.rsplit(".", 1)
        fn = getattr(importlib.import_module(module_path), fn_name)
        fn()
    except Exception as e:
        DBInspector.log(f"[SIDEBAR] Error en sidebar de '{modulo_key}': {e}", "ERROR")
        st.sidebar.error(f"Error en controles del módulo.")


def render_connection_status() -> None:
    """Indicador de salud de conexión BD — minimalista."""
    try:
        get_engine()
        st.markdown(
            "<p style='color:#10B981; font-size:0.7rem; margin-bottom:12px;'>● Conexión Estable</p>",
            unsafe_allow_html=True
        )
    except Exception:
        st.markdown(
            "<p style='color:#EF4444; font-size:0.7rem; margin-bottom:12px;'>● Error de Enlace</p>",
            unsafe_allow_html=True
        )
