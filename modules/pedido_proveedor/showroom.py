# =============================================================================
# MÓDULO: Pedido Proveedor
# ARCHIVO: modules/pedido_proveedor/showroom.py
# DESCRIPCIÓN: Auditoría Global de Saldo — vista transversal de todos los PPs
#
#  Vista "Auditoría de Facturación Interna":
#    - Resumen por marca: pares F9 vs facturados vs saldo + % ejecución
#    - Drill-down por PP: abre la vista detalle desde aquí
#    - Futuro: exportación para módulo Compra/Traslado
# =============================================================================

import streamlit as st

from modules.pedido_proveedor.logic import (
    get_auditoria_global,
    get_pedidos_proveedor,
)


def render_showroom():
    """
    Pantalla de Auditoría Global — accesible desde sidebar "Auditoría".
    Muestra el estado de ejecución de facturación interna por marca.
    """
    st.markdown(
        "<h2 style='color:#D4AF37;margin-bottom:4px;'>📊 Auditoría de Facturación Interna</h2>"
        "<p style='color:#94A3B8;margin-top:0;'>"
        "Stock F9 vs. Facturas Internas — % de Ejecución por Marca</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    df_audit = get_auditoria_global()

    if df_audit.empty:
        st.info("No hay datos de facturación interna registrados.")
        return

    # ── KPIs globales ─────────────────────────────────────────────────────────
    total_f9      = int(df_audit["pares_f9"].sum())
    total_fac     = int(df_audit["pares_facturados"].sum())
    total_saldo   = int(df_audit["saldo"].sum())
    pct_global    = round(total_fac / total_f9 * 100, 1) if total_f9 > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pares en F9",       f"{total_f9:,}")
    c2.metric("Pares Facturados",  f"{total_fac:,}")
    c3.metric("Saldo Real",        f"{total_saldo:,}")
    c4.metric("% Ejecución Global", f"{pct_global} %")

    st.divider()

    # ── Tabla por marca ───────────────────────────────────────────────────────
    st.markdown("#### Ejecución por Marca")

    for _, row in df_audit.iterrows():
        marca     = str(row["marca"])
        pares_f9  = int(row["pares_f9"])
        facturado = int(row["pares_facturados"])
        saldo     = int(row["saldo"])
        pct       = float(row["pct_ejecucion"] or 0)
        num_pps   = int(row["num_pps"])

        # Color de barra según % ejecución
        if pct >= 80:
            bar_color = "#22C55E"
        elif pct >= 40:
            bar_color = "#F59E0B"
        else:
            bar_color = "#EF4444"

        bar_w = min(int(pct), 100)

        st.markdown(
            f"""
            <div style="background:#1C1F2E;border:1px solid #334155;
                        border-radius:10px;padding:14px 20px;margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;
                          align-items:baseline;margin-bottom:8px;">
                <span style="font-size:1.05rem;font-weight:700;color:#F1F5F9;">
                  {marca}
                </span>
                <span style="font-size:.78rem;color:#64748B;">
                  {num_pps} PP{"s" if num_pps != 1 else ""}
                </span>
              </div>
              <div style="display:flex;gap:32px;margin-bottom:10px;flex-wrap:wrap;">
                <div>
                  <div style="color:#64748B;font-size:.68rem;letter-spacing:.05em;">
                    PARES F9</div>
                  <div style="color:#F1F5F9;font-size:1rem;font-weight:600;">
                    {pares_f9:,}</div>
                </div>
                <div>
                  <div style="color:#64748B;font-size:.68rem;letter-spacing:.05em;">
                    FACTURADOS</div>
                  <div style="color:#D4AF37;font-size:1rem;font-weight:600;">
                    {facturado:,}</div>
                </div>
                <div>
                  <div style="color:#64748B;font-size:.68rem;letter-spacing:.05em;">
                    SALDO REAL</div>
                  <div style="color:#22C55E;font-size:1rem;font-weight:600;">
                    {saldo:,}</div>
                </div>
                <div>
                  <div style="color:#64748B;font-size:.68rem;letter-spacing:.05em;">
                    EJECUCIÓN</div>
                  <div style="color:{bar_color};font-size:1rem;font-weight:700;">
                    {pct} %</div>
                </div>
              </div>
              <div style="background:#0F1E2F;border-radius:4px;height:6px;">
                <div style="background:{bar_color};width:{bar_w}%;
                            height:6px;border-radius:4px;
                            transition:width .3s ease;"></div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Selector rápido para abrir un PP ──────────────────────────────────────
    st.markdown("#### Abrir Pedido Proveedor")
    df_pps = get_pedidos_proveedor()
    if not df_pps.empty:
        opts = {
            f"{r['numero_registro']}  ·  Proforma {r['numero_proforma']}  ·  {r['marcas']}": int(r["id"])
            for _, r in df_pps.iterrows()
        }
        col_sel, col_btn = st.columns([4, 1])
        sel_label = col_sel.selectbox(
            "Seleccionar PP:",
            list(opts.keys()),
            key="audit_pp_sel",
            label_visibility="collapsed",
        )
        if col_btn.button("📋 Abrir", type="primary",
                          use_container_width=True, key="audit_btn_abrir"):
            st.session_state["pp_selected_id"]    = opts[sel_label]
            st.session_state["pp_vista_showroom"] = False
            st.rerun()
