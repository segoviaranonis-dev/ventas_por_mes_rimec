"""
SISTEMA: NEXUS CORE — modules/sales_report/sidebar.py
DESCRIPCIÓN: Controles de sidebar exclusivos del módulo de Ventas.
             Registrado como sidebar_fn en MODULE_INFO.
             Agnóstico del core — el core no sabe qué hay aquí dentro.
"""

import streamlit as st
from core.filters import FilterManager
from core.database import DBInspector
from core.constants import MESES_LISTA


def render_sales_sidebar():
    """
    Punto de entrada del sidebar de Ventas.
    El Dispatcher (core/sidebar.py) llama esta función dinámicamente.
    Accede a session_state directamente — no necesita parámetros.
    """
    df_raw   = st.session_state.get("raw_universe")
    u_sales  = FilterManager.get_sales_ui_universe(df_raw)
    cat_map  = FilterManager.get_categoria_map()   # {nombre: id} desde BD
    rev_map  = {v: k for k, v in cat_map.items()}  # {id: nombre}

    with st.sidebar:

        # ── ESTRATEGIA DE CRECIMIENTO ─────────────────────────────────────────
        with st.expander("📈 Estrategia de Crecimiento", expanded=False):
            val_obj = FilterManager.get_draft("objetivo_pct", 20)
            obj = st.select_slider(
                "Incremento Objetivo (%):",
                options=list(range(0, 105, 5)),
                value=int(val_obj),
                key="slider_estrategia_nexus"
            )
            if obj != val_obj:
                FilterManager.update_draft("objetivo_pct", obj)

        # ── HORIZONTE TEMPORAL ────────────────────────────────────────────────
        with st.expander("📅 Horizonte Temporal", expanded=False):
            st.markdown(
                "<p style='font-size:0.8rem; font-weight:bold;'>Accesos Rápidos:</p>",
                unsafe_allow_html=True
            )
            c1, c2, c3 = st.columns(3)
            draft_meses = FilterManager.get_draft("meses", [])
            is_1er = set(draft_meses) == set(MESES_LISTA[:6])
            is_2do = set(draft_meses) == set(MESES_LISTA[6:])
            is_ano = set(draft_meses) == set(MESES_LISTA)

            if c1.button("1er S", type="primary" if is_1er else "secondary",
                         use_container_width=True, help="Enero-Junio"):
                FilterManager.update_draft("meses", MESES_LISTA[:6])
                st.session_state.meses_key_tracker = st.session_state.get("meses_key_tracker", 0) + 1
                st.rerun()
            if c2.button("2do S", type="primary" if is_2do else "secondary",
                         use_container_width=True, help="Julio-Diciembre"):
                FilterManager.update_draft("meses", MESES_LISTA[6:])
                st.session_state.meses_key_tracker = st.session_state.get("meses_key_tracker", 0) + 1
                st.rerun()
            if c3.button("AÑO", type="primary" if is_ano else "secondary",
                         use_container_width=True, help="Año Completo"):
                FilterManager.update_draft("meses", MESES_LISTA)
                st.session_state.meses_key_tracker = st.session_state.get("meses_key_tracker", 0) + 1
                st.rerun()

            sel_meses = st.multiselect(
                "Selección Manual:",
                options=MESES_LISTA,
                default=draft_meses,
                key=f"ms_meses_{st.session_state.get('meses_key_tracker', 0)}"
            )
            if set(sel_meses) != set(draft_meses):
                FilterManager.update_draft("meses", sel_meses)

        # ── PARÁMETROS MAESTROS ───────────────────────────────────────────────
        with st.expander("🏗️ Parámetros Maestros", expanded=True):
            # Departamento — búsqueda case-insensitive para evitar mismatch
            deptos    = u_sales.get("departamentos", ["TODOS", "CALZADOS"])
            cur_depto = FilterManager.get_draft("departamento", "TODOS")
            deptos_upper = [d.upper() for d in deptos]
            idx_depto = deptos_upper.index(cur_depto.upper()) if cur_depto.upper() in deptos_upper else 0
            depto = st.selectbox("Departamento:", options=deptos, index=idx_depto)
            if depto != cur_depto:
                FilterManager.update_draft("departamento", depto)

            # Categorías — siempre desde cat_map (fuente de verdad, no u_sales)
            cat_options       = [k for k in cat_map.keys() if k != "TODOS"]  # sin "TODOS" en multiselect
            current_cat_ids   = FilterManager.get_draft("categoria_ids", [])
            current_cat_names = [rev_map.get(c, str(c)) for c in current_cat_ids]
            valid_defaults    = [n for n in current_cat_names if n in cat_options]

            sel_cats = st.multiselect("Categorías:", options=cat_options, default=valid_defaults,
                                      placeholder="Sin filtro = TODAS")
            if sel_cats != current_cat_names:
                FilterManager.update_draft("categoria_ids", sel_cats)

        # ── FILTROS DE ENTIDAD ────────────────────────────────────────────────
        with st.expander("🔍 Filtros de Entidad", expanded=False):
            def _ms(label, key_data, key_draft):
                options = u_sales.get(key_data, [])
                current = FilterManager.get_draft(key_draft, [])
                valid   = [v for v in current if v in options]
                sel = st.multiselect(label, options=options, default=valid)
                if set(sel) != set(current):
                    FilterManager.update_draft(key_draft, sel)
                    st.rerun()

            _ms("Marcas:",     "marcas",     "marcas")
            _ms("Cadenas:",    "cadenas",    "cadenas")
            _ms("Vendedores:", "vendedores", "vendedores")
            _ms("Clientes:",   "clientes",   "clientes")

            id_actual = FilterManager.get_draft("id_cliente_exacto") or ""
            id_input  = st.text_input("Búsqueda por Código Cliente:", value=str(id_actual))
            if id_input != str(id_actual):
                FilterManager.update_draft("id_cliente_exacto", id_input)

        # ── PANEL DE DISPARO ──────────────────────────────────────────────────
        st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
        col_reset, col_exe = st.columns([1, 1.3])

        if col_reset.button("🔄 REINICIAR", use_container_width=True,
                            help="Vuelve a Calzados/Programado"):
            FilterManager.reset_all_filters()
            st.rerun()

        if col_exe.button("🚀 EJECUTAR ORDEN", type="primary",
                          use_container_width=True):
            DBInspector.log("[SALES-SIDEBAR] Consulta disparada.", "SUCCESS")
            FilterManager.commit_filters()
            st.rerun()
