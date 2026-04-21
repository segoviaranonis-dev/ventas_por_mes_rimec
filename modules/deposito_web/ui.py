import streamlit as st
from modules.deposito_web.logic import get_stock_web, get_resumen_web


def render_deposito_web():
    st.markdown(
        "<h2 style='color:#D4AF37;margin-bottom:4px;'>🌐 Depósito Web</h2>"
        "<p style='color:#94A3B8;margin-top:0;'>"
        "Stock real en ALM_WEB_01 — motor de la galería de la tienda (5 Pilares + Talla)</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    df_res = get_resumen_web()

    if df_res.empty:
        st.info("Sin stock confirmado en el Depósito Web.")
        st.caption(
            "El stock aparece aquí cuando Compra Web confirma la recepción de un traspaso."
        )
        return

    total_stock = int(df_res["stock_total"].sum())
    n_articulos = len(df_res)

    c1, c2 = st.columns(2)
    c1.metric("Artículos disponibles", n_articulos)
    c2.metric("Pares en depósito",     f"{total_stock:,}")

    st.divider()

    # Cargar detalle con tallas una sola vez
    df_det = get_stock_web()

    # ── Acordeón por Marca (igual al Depósito RIMEC) ──────────────────────────
    marcas = df_res["marca"].unique().tolist()

    for marca in marcas:
        df_m   = df_res[df_res["marca"] == marca]
        tot_m  = int(df_m["stock_total"].sum())
        n_refs = len(df_m)

        with st.expander(
            f"🏷️  {marca}  —  {tot_m:,} pares disponibles  ·  {n_refs} artículo(s)",
            expanded=False,
        ):
            # ── Tabla plana: Línea | Ref. | Material | Color | Stock ──────────
            st.dataframe(
                df_m[["linea", "referencia", "material", "color", "stock_total"]].rename(
                    columns={
                        "linea":       "Línea",
                        "referencia":  "Ref.",
                        "material":    "Material",
                        "color":       "Color",
                        "stock_total": "Stock",
                    }
                ),
                column_config={
                    "Línea":    st.column_config.TextColumn(width=80),
                    "Ref.":     st.column_config.TextColumn(width=90),
                    "Material": st.column_config.TextColumn(width=140),
                    "Color":    st.column_config.TextColumn(width=140),
                    "Stock":    st.column_config.NumberColumn(format="%d", width=80),
                },
                hide_index=True,
                use_container_width=True,
            )

            # ── Desglose por talla (opcional) ─────────────────────────────────
            df_tallas = df_det[df_det["marca"] == marca]
            if not df_tallas.empty:
                with st.expander("Ver desglose por talla", expanded=False):
                    try:
                        pivot = df_tallas.pivot_table(
                            index=["linea", "referencia", "material", "color"],
                            columns="talla",
                            values="stock",
                            aggfunc="sum",
                            fill_value=0,
                        ).reset_index()
                        pivot.columns.name = None
                        pivot = pivot.rename(columns={
                            "linea": "Línea", "referencia": "Ref.",
                            "material": "Material", "color": "Color",
                        })
                        st.dataframe(pivot, hide_index=True, use_container_width=True)
                    except Exception:
                        st.dataframe(
                            df_tallas[["linea", "referencia", "material", "color", "talla", "stock"]].rename(
                                columns={
                                    "linea": "Línea", "referencia": "Ref.",
                                    "material": "Material", "color": "Color",
                                    "talla": "Talla", "stock": "Stock",
                                }
                            ),
                            hide_index=True, use_container_width=True,
                        )
