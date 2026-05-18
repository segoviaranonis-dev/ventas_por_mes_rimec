# =============================================================================
# Tablas retail: vista simple con st.dataframe; jerarquía opcional con AgGrid.
# =============================================================================

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.sales_report.styles_sales_report import SalesGridStyles

# Alineado con Sales Report (tablas Enterprise — solo vista jerárquica)
_RETAIL_HIERARCHY_LOCALE = {
    "searchOoo": "Buscar…",
    "noRowsToShow": "No hay datos en el universo Nexus",
    "totalFooter": "TOTAL GENERAL",
    "footer": "Subtotal",
    "sum": "Suma",
    "avg": "Promedio",
    "pinColumn": "Fijar",
    "groupBy": "Agrupar por",
    "ungroupBy": "Desagrupar",
}

_COL_ES: dict[str, str] = {
    "holding": "Holding",
    "tienda": "Tienda",
    "linea_code": "Línea",
    "referencia_code": "Referencia",
    "marca": "Marca",
    "genero": "Género",
    "estilo": "Estilo",
    "tipo_1": "Tipo 1",
    "pares": "Pares",
    "cantidad": "Pares",
    "monto": "Monto (Gs)",
    "monto_gs": "Monto (Gs)",
    "origen_tienda": "Origen",
    "venta_pares": "Pares vendidos",
    "venta_gs": "Monto ventas",
    "material_id": "Material id",
    "color_id": "Color id",
    "sku_key": "SKU",
}


def _prepare_for_grid(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
        else:
            out[col] = (
                out[col]
                .astype(str)
                .str.strip()
                .replace(["nan", "None", "NaT", "<NA>", ""], "---")
            )
    return out


def render_retail_aggrid(
    df: pd.DataFrame,
    *,
    key: str,
    height: int = 360,
) -> None:
    """
    Tabla de lotes / vista simple.

    Usamos ``st.dataframe`` (nativo) en lugar de AgGrid para evitar el warning de Streamlit
    «PyArrow conversion failed… JsCode is not JSON serializable» al serializar el componente.
    """
    if df is None or df.empty:
        st.caption("Sin datos para esta tabla.")
        return
    disp = _prepare_for_grid(df)
    rename = {c: _COL_ES.get(c, c.replace("_", " ").title()) for c in disp.columns}
    disp = disp.rename(columns=rename)
    st.dataframe(disp, hide_index=True, height=height, width="stretch", key=key)


def render_retail_hierarchy_grid(
    df: pd.DataFrame,
    *,
    group_cols_en: list[str],
    key: str,
    height: int = 480,
) -> None:
    """
    AgGrid con rowGroup + estética Sales Report (Obsidiana / Piano Geometry):
    Holding → Tienda → Marca → Línea → Referencia (según `group_cols_en`).
    """
    if df is None or df.empty:
        st.caption("Sin datos para la vista jerárquica.")
        return
    missing = [c for c in group_cols_en if c not in df.columns]
    if missing:
        st.warning(f"Faltan columnas para agrupar: {missing}")
        return
    try:
        from st_aggrid import AgGrid, ColumnsAutoSizeMode, GridOptionsBuilder, GridUpdateMode
    except ImportError:
        st.dataframe(df, hide_index=True, width="stretch")
        return

    st.markdown(SalesGridStyles.get_header_overrides(), unsafe_allow_html=True)

    disp = _prepare_for_grid(df[group_cols_en + [c for c in df.columns if c not in group_cols_en]].copy())
    rename = {c: _COL_ES.get(c, c.replace("_", " ").title()) for c in disp.columns}
    disp = disp.rename(columns=rename)
    group_es = [_COL_ES.get(c, c.replace("_", " ").title()) for c in group_cols_en]

    gb = GridOptionsBuilder.from_dataframe(disp)
    gb.configure_default_column(
        filterable=True,
        sortable=True,
        resizable=True,
        wrapText=True,
        autoHeight=False,
    )
    for c in disp.columns:
        if c in group_es:
            gb.configure_column(c, rowGroup=True, hide=True)
        elif pd.api.types.is_numeric_dtype(disp[c]):
            gb.configure_column(
                c,
                aggFunc="sum",
                type=["numericColumn"],
                minWidth=110,
                valueFormatter=SalesGridStyles.get_value_formatter(False),
            )
        else:
            gb.configure_column(c, minWidth=120)

    grid_options = gb.build()
    grid_options.update(
        {
            "localeText": _RETAIL_HIERARCHY_LOCALE,
            "getRowStyle": SalesGridStyles.get_piano_geometry(),
            "groupDefaultExpanded": 1,
            "groupIncludeFooter": True,
            "groupIncludeTotalFooter": True,
            "animateRows": False,
            "suppressAggFuncInHeader": True,
            "autoGroupColumnDef": {
                "headerName": "ESTRUCTURA DE ANÁLISIS",
                "minWidth": 320,
                "pinned": "left",
                "cellRendererParams": {
                    "footerValueGetter": 'params.isFullWidth ? "TOTAL" : params.value'
                },
            },
        }
    )

    AgGrid(
        disp,
        gridOptions=grid_options,
        height=height,
        theme="balham",
        update_mode=GridUpdateMode.NO_UPDATE,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=True,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        key=key,
    )
