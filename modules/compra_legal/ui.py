# =============================================================================
# MÓDULO: Compra (compra_legal)
# ARCHIVO: modules/compra_legal/ui.py
# DESCRIPCIÓN: Estación de trabajo RIMEC — Consolidador de PPs.
#
#  Flujo:
#    PP → "Enviar a Compra" → aparece aquí en PENDIENTE
#    "Finalizar y Distribuir" → crea traspasos (BORRADOR), estado=DISTRIBUIDA
#    Siguiente estación: FACTURACIÓN
# =============================================================================

import streamlit as st
import pandas as pd

from core.tabla_articulos import render_tabla_5pilares
from modules.compra_legal.logic import (
    get_compras_legales,
    get_compra_header,
    get_compra_hija_deposito,
    get_compra_hija_facturacion,
    get_pps_de_compra,
    finalizar_compra,
    rechazar_pp_de_compra,
)


_ESTADO_COLOR = {
    # Estados de Compra Legal
    "PENDIENTE":   "#3B82F6",
    "DISTRIBUIDA": "#F59E0B",
    "CERRADA":     "#22C55E",
    # Estados de PP (para mostrar en la sección de PPs recibidos)
    "ABIERTO":     "#22C55E",
    "ENVIADO":     "#F59E0B",
    "CERRADO":     "#94A3B8",
    "ANULADO":     "#EF4444",
}

_ESTADO_TRP_LABEL = {
    "BORRADOR":    "🕒 En Tránsito",
    "ENVIADO":     "✅ En Facturación",
    "CONFIRMADO":  "📦 En Depósito Web",
    "SIN_TRASPASO": "—",
}

_ESTADO_TRP_COLOR = {
    "BORRADOR":   "#64748B",
    "ENVIADO":    "#F59E0B",
    "CONFIRMADO": "#22C55E",
}


def _fmt_date(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    return str(val)[:10]


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def render_compra_legal():
    st.markdown(
        "<h2 style='color:#D4AF37;margin-bottom:4px;'>🏭 Compra</h2>"
        "<p style='color:#94A3B8;margin-top:0;'>"
        "Consolidador de Pedidos Proveedor — Estación 1 del Ciclo Abastecimiento</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    if st.session_state.get("cl_selected_id"):
        _render_detalle_compra(int(st.session_state["cl_selected_id"]))
    else:
        _render_lista_compras()


# ─────────────────────────────────────────────────────────────────────────────
# LISTA DE COMPRAS
# ─────────────────────────────────────────────────────────────────────────────

def _render_lista_compras():
    df = get_compras_legales()
    if df.empty:
        st.info("No hay Compras registradas aún.")
        st.caption("Desde el Pedido Proveedor → botón '📦 Enviar a Compra'.")
        return

    df["_fecha_dt"] = pd.to_datetime(df["fecha_factura"], errors="coerce")
    df = df.sort_values("_fecha_dt", ascending=True, na_position="last")
    df["_mes_label"] = df["_fecha_dt"].apply(
        lambda d: d.strftime("%B %Y").capitalize() if pd.notna(d) else "Sin fecha"
    )
    meses = list(dict.fromkeys(df["_mes_label"].tolist()))

    for mes in meses:
        df_m  = df[df["_mes_label"] == mes]
        n_cl  = len(df_m)
        total = int(df_m["total_pares"].sum())

        with st.expander(
            f"📅  {mes}  —  {n_cl} compra(s)  ·  {total:,} pares",
            expanded=True,
        ):
            cols = st.columns(2)
            for idx, (_, cl) in enumerate(df_m.iterrows()):
                col    = cols[idx % 2]
                estado = str(cl["estado"])
                e_color= _ESTADO_COLOR.get(estado, "#94A3B8")
                n_trp  = int(cl["n_traspasos"] or 0)
                n_conf = int(cl["n_confirmados"] or 0)
                pares  = int(cl["total_pares"] or 0)

                with col:
                    st.markdown(
                        f"""<div style="background:linear-gradient(135deg,#1C2E3F,#0F1E2F);
                                        border:1px solid #334155;border-radius:14px;
                                        padding:20px 22px;margin-bottom:4px;">
                          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                            <div>
                              <div style="font-size:.68rem;color:#64748B;text-transform:uppercase;
                                          letter-spacing:.06em;">Compra</div>
                              <div style="font-size:1.1rem;font-weight:700;color:#F1F5F9;">
                                {cl['numero_registro']}</div>
                              <div style="font-size:.78rem;color:#94A3B8;margin-top:2px;">
                                Proforma: {cl['proforma_referencia'] or '—'}
                                &nbsp;·&nbsp;PPs: {cl['pps_vinculados']}</div>
                            </div>
                            <span style="background:{e_color}22;color:{e_color};font-size:.68rem;
                                         font-weight:600;padding:3px 8px;border-radius:4px;">
                              {estado}
                            </span>
                          </div>
                          <div style="display:flex;gap:20px;margin-top:14px;">
                            <div>
                              <div style="color:#64748B;font-size:.66rem;text-transform:uppercase;">Pares F9</div>
                              <div style="color:#F1F5F9;font-size:1rem;font-weight:700;">{pares:,}</div>
                            </div>
                            <div>
                              <div style="color:#64748B;font-size:.66rem;text-transform:uppercase;">Traspasos</div>
                              <div style="color:#D4AF37;font-size:1rem;font-weight:700;">{n_trp}</div>
                            </div>
                            <div>
                              <div style="color:#64748B;font-size:.66rem;text-transform:uppercase;">Confirmados</div>
                              <div style="color:#22C55E;font-size:1rem;font-weight:700;">{n_conf}</div>
                            </div>
                          </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "📋 Abrir Compra",
                        key=f"cl_open_{cl['id']}",
                        use_container_width=True,
                        type="primary",
                    ):
                        st.session_state["cl_selected_id"] = int(cl["id"])
                        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# DETALLE DE COMPRA
# ─────────────────────────────────────────────────────────────────────────────

def _render_detalle_compra(id_cl: int):
    header = get_compra_header(id_cl)
    if not header:
        st.error("Compra no encontrada.")
        return

    estado  = header["estado"]
    e_color = _ESTADO_COLOR.get(estado, "#94A3B8")
    saldo   = header["total_pares_f9"] - header["pares_facturados"]
    pct     = round(header["pares_facturados"] / header["total_pares_f9"] * 100, 1) \
              if header["total_pares_f9"] > 0 else 0.0

    st.markdown(
        f"<h2 style='color:#D4AF37;margin-bottom:2px;'>🏭 {header['numero_registro']}</h2>"
        f"<p style='color:#94A3B8;margin:0;'>"
        f"Proforma: <b style='color:#F1F5F9;'>{header['proforma']}</b>"
        f"&nbsp;·&nbsp;PPs: <b style='color:#F1F5F9;'>{header['pps_vinculados']}</b>"
        f"&nbsp;·&nbsp;Estado: <b style='color:{e_color};'>{estado}</b></p>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pares F9",        f"{header['total_pares_f9']:,}")
    c2.metric("Facturados",      f"{header['pares_facturados']:,}")
    c3.metric("En Depósito",     f"{saldo:,}")
    c4.metric("% Ejecutado",     f"{pct} %")

    st.divider()

    # ── PPs recibidos — Revisión y Rechazo ───────────────────────────────────
    df_pps = get_pps_de_compra(id_cl)
    n_pps  = len(df_pps)

    with st.expander(
        f"📋  Pedidos Proveedor recibidos  —  {n_pps} PP(s)",
        expanded=True,
    ):
        if df_pps.empty:
            st.info("Sin PPs vinculados a esta compra.")
        else:
            for _, pp in df_pps.iterrows():
                pp_id    = int(pp["id"])
                vendido  = int(pp["total_vendido"] or 0)
                total    = int(pp["total_pares"] or 0)
                saldo_pp = total - vendido
                pp_est   = str(pp["estado"])
                pp_color = _ESTADO_COLOR.get(pp_est, "#94A3B8")

                col_info, col_btn = st.columns([4, 1])
                col_info.markdown(
                    f"<div style='background:#0F1E2F;border:1px solid #334155;"
                    f"border-radius:8px;padding:10px 16px;margin-bottom:4px;'>"
                    f"<span style='color:#D4AF37;font-weight:700;'>{pp['numero_registro']}</span>"
                    f"&nbsp;&nbsp;"
                    f"<span style='background:{pp_color}22;color:{pp_color};font-size:.7rem;"
                    f"padding:2px 7px;border-radius:4px;'>{pp_est}</span>"
                    f"<br><span style='color:#94A3B8;font-size:.8rem;'>"
                    f"{pp['marcas']} &nbsp;·&nbsp; Proforma {pp['numero_proforma']}"
                    f"&nbsp;·&nbsp; {total:,} pares F9"
                    f"&nbsp;·&nbsp; {vendido:,} facturados"
                    f"&nbsp;·&nbsp; {saldo_pp:,} saldo"
                    f"</span></div>",
                    unsafe_allow_html=True,
                )
                if estado == "PENDIENTE":
                    if col_btn.button(
                        "❌ Rechazar",
                        key=f"cl_rechazar_{id_cl}_{pp_id}",
                        use_container_width=True,
                    ):
                        ok, msg = rechazar_pp_de_compra(id_cl, pp_id)
                        if ok:
                            st.warning(f"PP {pp['numero_registro']} rechazado → devuelto a ABIERTO.")
                            st.rerun()
                        else:
                            st.error(msg)

    st.divider()

    # ── Botón FINALIZAR Y DISTRIBUIR ─────────────────────────────────────────
    if estado in ("PENDIENTE", "BORRADOR"):
        col_btn, col_info = st.columns([2, 3])
        col_info.caption(
            "Al finalizar, el sistema crea los Traspasos por cada Factura Interna. "
            "Los datos quedan disponibles en Facturación para envío a Web Bazar."
        )
        err_key = f"cl_finalizar_err_{id_cl}"
        if st.session_state.get(err_key):
            st.error(st.session_state.pop(err_key))

        if col_btn.button(
            "✅  Finalizar y Distribuir",
            key=f"cl_finalizar_{id_cl}",
            type="primary",
            use_container_width=True,
        ):
            ok, msg = finalizar_compra(id_cl)
            if ok:
                st.success(f"✓ {msg}")
                st.rerun()
            else:
                st.session_state[err_key] = msg
                st.rerun()
    elif estado == "DISTRIBUIDA":
        st.markdown(
            "<div style='background:#F59E0B22;border:1px solid #F59E0B;"
            "border-radius:8px;padding:10px 16px;color:#F59E0B;font-weight:600;'>"
            "📤 Distribuida — los datos están en Facturación para envío a Web Bazar</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='background:#22C55E22;border:1px solid #22C55E;"
            "border-radius:8px;padding:10px 16px;color:#22C55E;font-weight:600;'>"
            "📦 Cerrada — stock confirmado en Depósito Web</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Hija Depósito (saldo por artículo) ───────────────────────────────────
    df_dep   = get_compra_hija_deposito(id_cl)
    dep_tot  = int(df_dep["saldo"].sum()) if not df_dep.empty else 0

    with st.expander(
        f"📦  Depósito RIMEC (Saldo)  —  {dep_tot:,} pares",
        expanded=False,
    ):
        if df_dep.empty:
            st.info("Sin saldo disponible.")
        else:
            df_show = df_dep[df_dep["saldo"] > 0]
            st.dataframe(
                df_show[["marca","linea","referencia","material","color",
                          "cantidad_inicial","vendido","saldo"]].rename(columns={
                    "marca":"Marca","linea":"Línea","referencia":"Ref.",
                    "material":"Material","color":"Color",
                    "cantidad_inicial":"Inicial","vendido":"Vendido","saldo":"Saldo",
                }),
                hide_index=True, use_container_width=True,
            )

    # ── Hija Facturación (FAC-INTs) ───────────────────────────────────────────
    df_fac  = get_compra_hija_facturacion(id_cl)
    fac_tot = int(df_fac["pares"].sum()) if not df_fac.empty else 0

    with st.expander(
        f"🧾  Facturas Internas (FAC-INT)  —  {fac_tot:,} pares",
        expanded=True,
    ):
        if df_fac.empty:
            st.info("Sin facturas internas en los PPs de esta compra.")
        else:
            for fac in df_fac["factura"].unique():
                df_f  = df_fac[df_fac["factura"] == fac]
                t_fac = int(df_f["pares"].sum())
                t_est = str(df_f["traspaso_estado"].iloc[0])
                t_lab = _ESTADO_TRP_LABEL.get(t_est, t_est)
                cli   = str(df_f["cliente"].iloc[0])

                with st.expander(
                    f"🧾  {fac}  |  {cli}  |  {t_fac:,} pares  |  {t_lab}",
                    expanded=False,
                ):
                    render_tabla_5pilares(df_f)
