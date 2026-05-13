"""
Helpers compartidos para mostrar tablas de artículos con los 5 Pilares.
5 Pilares: Línea · Referencia · Material · Color · Talla (+ Grada)
"""
import streamlit as st

_TALLA_COLS   = ["t33", "t34", "t35", "t36", "t37", "t38", "t39", "t40"]
_TALLA_LABELS = {t: t[1:] for t in _TALLA_COLS}   # "t33" → "33"


def render_tabla_5pilares(df, extra_izq: list[str] | None = None) -> None:
    """
    Muestra una tabla con los 5 Pilares + Grada + distribución de tallas.

    Columnas base (en orden):
      extra_izq (ej. ["marca","pedido"]) → linea → referencia → material
      → color → grada → tXX activas → total/saldo

    Solo incluye las columnas talla que tengan al menos un par.
    """
    base_fija  = [c for c in (extra_izq or []) if c in df.columns]
    base_sku   = [c for c in ["linea", "referencia", "material", "color", "grada"]
                  if c in df.columns]
    talla_act  = [t for t in _TALLA_COLS
                  if t in df.columns and df[t].fillna(0).sum() > 0]
    total_col  = [c for c in ["pares", "saldo"] if c in df.columns][:1]

    show_cols  = base_fija + base_sku + talla_act + total_col
    rename_map = {
        "marca":      "Marca",
        "pedido":     "PP",
        "fecha":      "Fecha",
        "precio":     "Precio",
        "linea":      "Línea",
        "referencia": "Ref.",
        "material":   "Material",
        "color":      "Color",
        "grada":      "Grada",
        "pares":      "Total",
        "saldo":      "Saldo",
        **_TALLA_LABELS,
    }
    col_cfg = {
        "Marca":    st.column_config.TextColumn(width=100),
        "PP":       st.column_config.TextColumn(width=100),
        "Fecha":    st.column_config.DateColumn(width=90),
        "Precio":   st.column_config.NumberColumn(format="Gs. %,.0f", width=95),
        "Línea":    st.column_config.TextColumn(width=75),
        "Ref.":     st.column_config.TextColumn(width=75),
        "Material": st.column_config.TextColumn(width=130),
        "Color":    st.column_config.TextColumn(width=130),
        "Grada":    st.column_config.TextColumn(width=60),
        "Total":    st.column_config.NumberColumn(format="%d", width=70),
        "Saldo":    st.column_config.NumberColumn(format="%d", width=70),
        **{_TALLA_LABELS[t]: st.column_config.NumberColumn(format="%d", width=44)
           for t in talla_act},
    }
    st.dataframe(
        df[show_cols].rename(columns=rename_map),
        column_config=col_cfg,
        hide_index=True,
        use_container_width=True,
    )
