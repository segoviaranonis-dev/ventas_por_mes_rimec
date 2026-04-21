import streamlit as st
from core.tabla_articulos import render_tabla_5pilares
from modules.deposito.logic import (
    get_stock_deposito,
    get_stock_deposito_tallas,
    get_compras_distribuidas,
)


def render_deposito():
    st.markdown(
        "<h2 style='color:#D4AF37;margin-bottom:4px;'>🏗️ Depósito RIMEC</h2>"
        "<p style='color:#94A3B8;margin-top:0;'>"
        "Stock físico disponible — Compra Inicial − Venta Tránsito</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Filtro por Compra ─────────────────────────────────────────────────────
    df_cl = get_compras_distribuidas()
    opciones = ["Todas las compras"]
    id_cl: int | None = None

    if not df_cl.empty:
        for _, row in df_cl.iterrows():
            opciones.append(f"{row['numero_registro']} [{row['estado']}]")

        sel = st.selectbox("Filtrar por Compra", opciones,
                           key="dep_filtro_cl", label_visibility="collapsed")
        if sel != "Todas las compras":
            idx = opciones.index(sel) - 1
            id_cl = int(df_cl.iloc[idx]["id"])

    # ── Tabla de stock ────────────────────────────────────────────────────────
    df      = get_stock_deposito(id_cl)
    df_tall = get_stock_deposito_tallas(id_cl)

    if df.empty:
        st.info("Sin saldo disponible en depósito.")
        return

    total_saldo = int(df["saldo"].sum())
    total_ini   = int(df["cantidad_inicial"].sum())
    total_vend  = int(df["vendido"].sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Compra Inicial", f"{total_ini:,} pares")
    c2.metric("Venta Tránsito", f"{total_vend:,} pares")
    c3.metric("Saldo Disponible", f"{total_saldo:,} pares")

    st.divider()

    # Agrupar por marca en acordeones
    for marca in df["marca"].unique().tolist():
        df_m    = df[df["marca"] == marca]
        saldo_m = int(df_m["saldo"].sum())

        with st.expander(
            f"🏷️  {marca}  —  {saldo_m:,} pares disponibles",
            expanded=False,
        ):
            # ── Tabla resumen: PP | Línea | Ref. | Material | Color | Grada | Inicial | Vendido | Saldo
            # Cada fila = un ppd único. Dos gradaciones distintas del mismo artículo
            # aparecen como filas separadas — la columna Grada las distingue.
            show_cols = [c for c in
                         ["pedido","linea","referencia","material","color","grada",
                          "cantidad_inicial","vendido","saldo"]
                         if c in df_m.columns]
            st.dataframe(
                df_m[show_cols].rename(columns={
                    "pedido":           "PP",
                    "linea":            "Línea",
                    "referencia":       "Ref.",
                    "material":         "Material",
                    "color":            "Color",
                    "grada":            "Grada",
                    "cantidad_inicial": "Inicial",
                    "vendido":          "Vendido",
                    "saldo":            "Saldo",
                }),
                column_config={
                    "PP":      st.column_config.TextColumn(width=100),
                    "Línea":   st.column_config.TextColumn(width=75),
                    "Ref.":    st.column_config.TextColumn(width=75),
                    "Material":st.column_config.TextColumn(width=130),
                    "Color":   st.column_config.TextColumn(width=130),
                    "Grada":   st.column_config.TextColumn(width=75),
                    "Inicial": st.column_config.NumberColumn(format="%d", width=75),
                    "Vendido": st.column_config.NumberColumn(format="%d", width=75),
                    "Saldo":   st.column_config.NumberColumn(format="%d", width=75),
                },
                hide_index=True,
                use_container_width=True,
            )

            # ── Distribución por talla — una fila por unidad de stock (ppd_id) ──
            # Cada gradación diferente aparece en su propia fila con sus tallas.
            # Misma lógica para reposiciones: 2 PPs del mismo artículo = 2 filas.
            df_t = df_tall[df_tall["marca"] == marca] if not df_tall.empty else df_tall
            if not df_t.empty:
                with st.expander("Ver distribución por talla", expanded=False):
                    render_tabla_5pilares(df_t, extra_izq=["pedido"])
