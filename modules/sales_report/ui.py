# =============================================================================
# SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
# UBICACIÓN: modules/sales_report/ui.py
# VERSION: 90.0.2 (NAV-SYNC & BRIDGE METADATA)
# AUTOR: Héctor & Gemini AI
# DESCRIPCIÓN: Eliminación definitiva de duplicados mediante supresión de nodos.
#              Sincronización de nombre de función con core/navigation.py.
# =============================================================================

import streamlit as st
import time
import zipfile
import pandas as pd
import numpy as np
from io import BytesIO
from core.settings import settings
from core.queries import QueryCenter
from core.styles import header_section, card_metric, StatusFactory
from core.filters import FilterManager
from core.database import DBInspector

# Rutas Locales
from .logic import SalesLogic
from .export import ExportManager
from .styles_sales_report import SalesGridStyles
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, JsCode

# --- [CONFIGURACIÓN IDIOMA] ---
SPANISH_LOCALE = {
    'searchOoo': 'Buscar...', 'noRowsToShow': 'No hay datos en el universo Nexus',
    'totalFooter': 'TOTAL GENERAL', 'footer': 'Subtotal',
    'sum': 'Suma', 'avg': 'Promedio', 'pinColumn': 'Fijar',
    'groupBy': 'Agrupar por', 'ungroupBy': 'Desagrupar'
}

BLACK_LIST = ['LEVEL', 'IS_SUBTOTAL', 'mes_idx', 'Auto Unique ID']

def _ui_mic(msg, level="INFO", t_start=None):
    elapsed = f" | ⏱️ {time.time()-t_start:.4f}s" if t_start else ""
    log_msg = f"🖥️ [UI-CORE] {msg}{elapsed}"
    DBInspector.log(log_msg, level)
    print(log_msg)

# ─────────────────────────────────────────────────────────────────────────────
# EXPORTACIÓN Y DIÁLOGOS
# ─────────────────────────────────────────────────────────────────────────────

def export_batch_zip(pkg_item, group_col, filename_prefix, group_cols_pdf, report_title):
    t_init = time.time()
    df = pkg_item['data'] if isinstance(pkg_item, dict) else pkg_item
    zip_buffer = BytesIO()
    items = df[group_col].unique()

    # Captura de metadata global para el lote
    metadata_nexus = FilterManager.get_report_metadata()

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for item in items:
            filtered_df = df[df[group_col] == item].copy()
            # Inyectamos la metadata capturada por los micrófonos
            pdf_io = ExportManager.generate_general_report(
                f"{report_title}: {item}",
                filtered_df,
                group_cols=group_cols_pdf,
                meta_info=metadata_nexus
            )
            zip_file.writestr(f"{str(item).replace('/', '_')}.pdf", pdf_io.getvalue())

    zip_buffer.seek(0)
    _ui_mic(f"Lote {filename_prefix} listo: {len(items)} archivos", t_start=t_init)
    return zip_buffer, len(items)

@st.dialog("Análisis Profundo Nexus", width="large")
def show_expanded_table(pkg_data, group_cols, title, key_suffix):
    st.subheader(f"🔍 {title}")
    render_fragmented_grid(pkg_data, height=700, key_suffix=f"{key_suffix}_max", group_cols=group_cols)
    if st.button("Cerrar Vista", use_container_width=True): st.rerun()

def render_table_header(title, pkg_data, group_cols, key_suffix):
    col_t, col_e, col_p = st.columns([0.6, 0.2, 0.2])
    col_t.markdown(f"### {title}")
    df_to_export = pkg_data['data'] if isinstance(pkg_data, dict) else pkg_data

    if col_e.button(f"🔍 AMPLIAR", key=f"btn_exp_{key_suffix}", use_container_width=True):
        show_expanded_table(pkg_data, group_cols, title, key_suffix)

    if col_p.button(f"📄 PDF", key=f"btn_pdf_{key_suffix}", use_container_width=True):
        # Sellado y captura de metadata con microfonía
        FilterManager.commit_filters()
        metadata_nexus = FilterManager.get_report_metadata()

        pdf = ExportManager.generate_general_report(
            title,
            df_to_export,
            group_cols=group_cols,
            meta_info=metadata_nexus
        )
        st.download_button("💾 BAJAR", pdf.getvalue(), f"{title}.pdf", "application/pdf", key=f"dl_{key_suffix}")

# ─────────────────────────────────────────────────────────────────────────────
# RENDERIZADOR MAESTRO (PROTOCOLO NODO FINAL ABSOLUTO)
# ─────────────────────────────────────────────────────────────────────────────
@st.fragment
def render_fragmented_grid(pkg_data, height=500, key_suffix="", group_cols=[]):
    t_grid = time.time()

    if isinstance(pkg_data, dict):
        df = pkg_data['data'].copy()
        totals = pkg_data.get('totals', {})
    else:
        df = pkg_data.copy()
        totals = {}

    if df.empty: return st.info(f"Sin datos: {key_suffix}")

    # 1. LIMPIEZA DE ADN
    to_drop = [c for c in df.columns if any(b.lower() in c.lower() for b in BLACK_LIST)]
    df = df.drop(columns=to_drop, errors='ignore')

    display_groups = group_cols.copy()

    # Formateo de tipos
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace(r'<[^>]*>', '', regex=True)
            df[col] = df[col].replace(['nan', 'None', ''], np.nan).fillna('S/D')
        elif np.issubdtype(df[col].dtype, np.number):
            df[col] = df[col].astype(float)

    st.markdown(SalesGridStyles.get_header_overrides(), unsafe_allow_html=True)
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, filterable=True, sortable=True)

    # 2. ESTRUCTURA DE JERARQUÍA (ROOT CAUSE FIX)
    if display_groups:
        for col in display_groups:
            if col in df.columns:
                gb.configure_column(col, rowGroup=True, hide=True)
    else:
        identidad = df.columns[0]
        gb.configure_column(identidad, pinned='left', minWidth=250)

    # 3. AGREGACIONES
    columnas_numericas = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in df.columns:
        if col in columnas_numericas:
            is_pct = any(x in col.upper() for x in ['%', 'VAR', 'VARIACIÓN'])

            if is_pct:
                if 'CANT' in col.upper():
                    col_real_cand = next((c for c in df.columns if '26' in c.upper() and 'CANT' in c.upper()), None)
                    col_obj_cand = next((c for c in df.columns if 'OBJ' in c.upper() and 'CANT' in c.upper()), None)
                else:
                    col_real_cand = next((c for c in df.columns if '26' in c.upper() and ('MONT' in c.upper() or 'CANT' not in c.upper())), None)
                    col_obj_cand = next((c for c in df.columns if 'OBJ' in c.upper() and ('MONT' in c.upper() or 'CANT' not in c.upper())), None)

                if col_real_cand and col_obj_cand:
                    agg_func = JsCode(f"""
                        function(params) {{
                            let sumReal = 0;
                            let sumObj = 0;
                            if (params.values && params.rowNode && params.rowNode.childrenAfterGroup) {{
                                params.values.forEach(function(value, index) {{
                                    let child = params.rowNode.childrenAfterGroup[index];
                                    if (child) {{
                                        let rowReal = (child.data ? child.data['{col_real_cand}'] : (child.aggData ? child.aggData['{col_real_cand}'] : 0)) || 0;
                                        let rowObj = (child.data ? child.data['{col_obj_cand}'] : (child.aggData ? child.aggData['{col_obj_cand}'] : 0)) || 0;
                                        sumReal += Number(rowReal);
                                        sumObj += Number(rowObj);
                                    }}
                                }});
                            }}
                            if (sumObj > 0) return (sumReal - sumObj) / sumObj * 100;
                            if (sumReal > 0) return 100;
                            return 0;
                        }}
                    """)
                else:
                    agg_func = 'avg'
            else:
                agg_func = 'sum'

            gb.configure_column(
                col,
                aggFunc=agg_func,
                valueFormatter=SalesGridStyles.get_value_formatter(is_pct),
                cellStyle=SalesGridStyles.get_conditional_formatting() if is_pct else None,
                type=["numericColumn"]
            )

    grid_options = gb.build()

    # 4. CONFIGURACIÓN DE TABLA INTERACTIVA
    grid_options.update({
        'localeText': SPANISH_LOCALE,
        'getRowStyle': SalesGridStyles.get_piano_geometry(),
        'groupDefaultExpanded': 1,
        'groupIncludeFooter': True,
        'groupIncludeTotalFooter': True,
        'animateRows': False,
        'suppressAggFuncInHeader': True,
        'autoGroupColumnDef': {
            'headerName': 'ESTRUCTURA DE ANÁLISIS',
            'minWidth': 300,
            'pinned': 'left',
            'cellRendererParams': {
                'footerValueGetter': 'params.isFullWidth ? "TOTAL" : params.value'
            }
        }
    })

    if totals:
        grid_options['pinnedBottomRowData'] = [totals]

    res = AgGrid(
        df,
        gridOptions=grid_options,
        theme='balham',
        height=height,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=True,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        key=f"nexus_v90_{key_suffix}"
    )

    return res

# ─────────────────────────────────────────────────────────────────────────────
# ORQUESTADOR FINAL (RE-NAME SYNC)
# ─────────────────────────────────────────────────────────────────────────────
def render_sales_interface():
    """
    Función sincronizada con core/navigation.py
    """
    t_total = time.time()
    header_section("Inteligencia Nexus", "Nexus Core v90.0.0")

    f = FilterManager.get_all_committed()

    if FilterManager.should_reload() or 'sales_package' not in st.session_state:
        with st.spinner("Sincronizando..."):
            raw_data = QueryCenter.get_main_sales_query(f)
            if raw_data is not None and not raw_data.empty:
                st.session_state.sales_package = SalesLogic.get_full_analysis_package(
                    raw_data, f.get("objetivo_pct", 0), f.get("meses", [])
                )
            else:
                st.session_state.sales_package = None
            FilterManager.set_reload_state(False)
            st.rerun()

    pkg = st.session_state.get('sales_package')
    if not pkg:
        return StatusFactory.alert("error", "Empty Set: La consulta no devolvió filas.")

    tabs = st.tabs(["📊 Dashboard", "👥 Clientes", "🏷️ Marcas", "💼 Vendedores"])

    with tabs[0]:
        k = pkg['kpis']
        m1, m2, m3 = st.columns(3)
        with m1: card_metric("Clientes Activos", f"{k['clientes_26']}")
        with m2: card_metric("Atendimiento", f"{k['atendimiento']:.1f}%")
        with m3: card_metric("Variación Global", f"{pkg['kpis']['variacion_total']:+.1f}%")
        st.divider()
        render_table_header("Evolución Mensual", pkg['evolucion'], ['Semestre'], "evol")
        render_fragmented_grid(pkg['evolucion'], height=350, key_suffix="evol", group_cols=['Semestre'])

    with tabs[1]:
        for key, label in [('crecimiento', '✅ Clientes en Crecimiento'),
                          ('decrecimiento', '⚠️ Clientes en Riesgo'),
                          ('sin_compra', '📉 Sin Compra Reciente')]:
            st.divider()
            render_table_header(label, pkg['cartera'][key], ['Cadena', 'Cliente'], f"cli_{key}")
            render_fragmented_grid(pkg['cartera'][key], height=400, key_suffix=f"cli_{key}", group_cols=['Cadena', 'Cliente'])

    with tabs[2]:
        pkg_mar_gen, pkg_mar_det = pkg['marcas']
        render_table_header("Ranking de Marcas", pkg_mar_gen, [], "mar_gen")
        render_fragmented_grid(pkg_mar_gen, height=300, key_suffix="mar_gen")
        st.divider()

        col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
        col1.markdown("### Matriz Detallada Marcas")
        if col2.button("📦 BATCH PDF", key="btn_batch_mar", use_container_width=True):
            with st.spinner("Generando PDFs por Marca..."):
                z_buf, ct = export_batch_zip(pkg_mar_det, 'Marca', "Marcas", ['Marca', 'Cadena', 'Cliente'], "Matriz de Marca")
                st.download_button(f"⬇️ DESCARGAR ZIP ({ct})", z_buf.getvalue(), "batch_marcas.zip", "application/zip", key="dl_batch_mar")
        if col3.button("🔍 AMPLIAR", key="btn_exp_mar_det", use_container_width=True):
            show_expanded_table(pkg_mar_det, ['Marca', 'Cadena', 'Cliente'], "Matriz Detallada Marcas", "mar_det")

        render_fragmented_grid(pkg_mar_det, height=500, key_suffix="mar_det", group_cols=['Marca', 'Cadena', 'Cliente'])

    with tabs[3]:
        pkg_ven_gen, pkg_ven_det = pkg['vendedores']
        render_table_header("Ranking de Vendedores", pkg_ven_gen, [], "ven_gen")
        render_fragmented_grid(pkg_ven_gen, height=300, key_suffix="ven_gen")
        st.divider()

        col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
        col1.markdown("### Gestión Detallada")
        if col2.button("📦 BATCH PDF", key="btn_batch_ven", use_container_width=True):
            with st.spinner("Generando PDFs por Vendedor..."):
                z_buf, ct = export_batch_zip(pkg_ven_det, 'Vendedor', "Vendedores", ['Vendedor', 'Cadena', 'Cliente', 'Marca'], "Gestión Detallada")
                st.download_button(f"⬇️ DESCARGAR ZIP ({ct})", z_buf.getvalue(), "batch_vendedores.zip", "application/zip", key="dl_batch_ven")
        if col3.button("🔍 AMPLIAR", key="btn_exp_ven_det", use_container_width=True):
            show_expanded_table(pkg_ven_det, ['Vendedor', 'Cadena', 'Cliente', 'Marca'], "Gestión Detallada Vendedores", "ven_det")

        render_fragmented_grid(pkg_ven_det, height=600, key_suffix="ven_det", group_cols=['Vendedor', 'Cadena', 'Cliente', 'Marca'])

    _ui_mic("🎯 DESPLIEGUE EXITOSO: Sector de Ventas Sincronizado.", t_start=t_total)