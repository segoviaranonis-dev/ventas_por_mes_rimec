# =============================================================================
# MÓDULO: Facturación
# ARCHIVO: modules/facturacion/ui.py
# DESCRIPCIÓN: Estación 3 del Ciclo Abastecimiento.
#
#  Vista Facturas: Lista FAC-INTs por estado de traspaso.
#    → "🚀 ENVIAR A WEB BAZAR" por factura (crea/envía traspaso)
#  Vista Carga Manual: Selecciona stock de Depósito → nuevo FAC-INT Cliente 5000
# =============================================================================

import streamlit as st
import pandas as pd

from core.tabla_articulos import render_tabla_5pilares
from modules.facturacion.logic import (
    get_facturas,
    get_factura_lineas,
    enviar_factura_a_bazar,
    get_pps_con_saldo,
    get_skus_con_saldo,
    save_carga_manual,
)

_ESTADO_TRP_LABEL = {
    "SIN_TRASPASO": "⚪ Sin Traspaso",
    "BORRADOR":     "🕒 Pendiente Envío",
    "ENVIADO":      "📤 En Compra Web",
    "CONFIRMADO":   "✅ Confirmado",
}
_ESTADO_TRP_COLOR = {
    "SIN_TRASPASO": "#64748B",
    "BORRADOR":     "#3B82F6",
    "ENVIADO":      "#F59E0B",
    "CONFIRMADO":   "#22C55E",
}


def render_facturacion():
    st.markdown(
        "<h2 style='color:#D4AF37;margin-bottom:4px;'>🧾 Facturación</h2>"
        "<p style='color:#94A3B8;margin-top:0;'>"
        "Puente RIMEC → Web Bazar — Estación 3 del Ciclo Abastecimiento</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    if st.session_state.get("fac_vista_carga"):
        _render_carga_manual()
    else:
        _render_facturas()


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: FACTURAS INTERNAS
# ─────────────────────────────────────────────────────────────────────────────

def _render_facturas():
    df = get_facturas()
    if df.empty:
        st.info("No hay Facturas Internas registradas.")
        st.caption("Las FAC-INT se crean desde el módulo Pedido Proveedor (Phase A/B).")
        return

    total_pares = int(df["pares"].sum())
    n_sin_trp   = int((df["traspaso_estado"] == "SIN_TRASPASO").sum())
    n_enviado   = int((df["traspaso_estado"] == "ENVIADO").sum())
    n_confirm   = int((df["traspaso_estado"] == "CONFIRMADO").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Facturas", len(df))
    c2.metric("Pares Totales",  f"{total_pares:,}")
    c3.metric("Sin Enviar",     n_sin_trp + int((df["traspaso_estado"] == "BORRADOR").sum()))
    c4.metric("Confirmados",    n_confirm)

    st.divider()

    # Ordenar por estado para priorizar las enviables
    orden = {"SIN_TRASPASO": 0, "BORRADOR": 1, "ENVIADO": 2, "CONFIRMADO": 3}
    df["_orden"] = df["traspaso_estado"].map(orden).fillna(9)
    df = df.sort_values(["_orden", "fecha"], ascending=[True, False])

    for _, row in df.iterrows():
        factura   = str(row["factura"])
        estado    = str(row["traspaso_estado"])
        e_label   = _ESTADO_TRP_LABEL.get(estado, estado)
        e_color   = _ESTADO_TRP_COLOR.get(estado, "#94A3B8")
        pares     = int(row["pares"] or 0)
        cliente   = str(row["cliente"])
        compra    = str(row["compra"])
        fecha_str = str(row["fecha"])[:10] if row["fecha"] else "—"

        with st.expander(
            f"🧾  {factura}  ·  {cliente}  ·  {pares:,} pares  ·  {e_label}",
            expanded=(estado in ("SIN_TRASPASO", "BORRADOR")),
        ):
            col_info, col_btn = st.columns([3, 1])
            col_info.markdown(
                f"**Marca:** {row['marca']}  ·  **PP:** {row['pedido']}  "
                f"·  **Compra:** {compra}  ·  **Fecha:** {fecha_str}"
            )
            col_info.markdown(
                f"<span style='background:{e_color}22;color:{e_color};"
                f"padding:2px 8px;border-radius:4px;font-size:.78rem;'>"
                f"{e_label}</span>",
                unsafe_allow_html=True,
            )

            if estado in ("SIN_TRASPASO", "BORRADOR"):
                if col_btn.button(
                    "🚀 ENVIAR",
                    key=f"fac_enviar_{factura}",
                    type="primary",
                    use_container_width=True,
                ):
                    ok, msg = enviar_factura_a_bazar(factura)
                    if ok:
                        st.success(f"✓ {msg}")
                        st.rerun()
                    else:
                        st.error(msg)
            elif estado == "ENVIADO":
                col_btn.markdown(
                    "<div style='color:#F59E0B;font-size:.78rem;text-align:center;"
                    "padding-top:8px;'>📤 En tránsito</div>",
                    unsafe_allow_html=True,
                )
            else:
                col_btn.markdown(
                    "<div style='color:#22C55E;font-size:.78rem;text-align:center;"
                    "padding-top:8px;'>✅ Confirmado</div>",
                    unsafe_allow_html=True,
                )

            # ── Detalle de artículos (5 Pilares + Tallas) ────────────────────
            df_lin = get_factura_lineas(factura)
            if not df_lin.empty:
                render_tabla_5pilares(df_lin)
            else:
                st.caption("Sin detalle de líneas registrado.")


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: CARGA MANUAL (stock Depósito → FAC-INT Cliente 5000)
# ─────────────────────────────────────────────────────────────────────────────

def _render_carga_manual():
    st.markdown(
        "<h3 style='color:#F1F5F9;margin-bottom:4px;'>📦 Carga Manual</h3>"
        "<p style='color:#94A3B8;margin-top:0;font-size:.85rem;'>"
        "Seleccioná un PP con saldo disponible y cargá unidades adicionales para enviar a Web Bazar.</p>",
        unsafe_allow_html=True,
    )

    pp_id_activo = st.session_state.get("fac_carga_pp_id")

    if pp_id_activo:
        _render_carga_formulario(int(pp_id_activo))
        return

    # ── Selector de PP ────────────────────────────────────────────────────────
    df_pps = get_pps_con_saldo()
    if df_pps.empty:
        st.info("No hay Pedidos Proveedor con saldo disponible.")
        return

    st.caption("Pedidos con saldo disponible:")
    cols = st.columns(2)
    for idx, (_, pp) in enumerate(df_pps.iterrows()):
        col = cols[idx % 2]
        saldo = int(pp["saldo_total"] or 0)
        with col:
            st.markdown(
                f"""<div style="background:linear-gradient(135deg,#1C2E3F,#0F1E2F);
                                border:1px solid #334155;border-radius:12px;
                                padding:16px 20px;margin-bottom:4px;">
                  <div style="font-size:.68rem;color:#64748B;text-transform:uppercase;">
                    Pedido Proveedor</div>
                  <div style="font-size:1rem;font-weight:700;color:#F1F5F9;">
                    {pp['numero_registro']}</div>
                  <div style="font-size:.78rem;color:#94A3B8;margin-top:2px;">
                    Proforma: {pp['numero_proforma']}
                    &nbsp;·&nbsp;{pp['marcas']}</div>
                  <div style="color:#22C55E;font-size:.95rem;font-weight:700;margin-top:6px;">
                    {saldo:,} pares disponibles</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button(
                "Cargar desde este PP",
                key=f"fac_sel_pp_{pp['id']}",
                use_container_width=True,
            ):
                st.session_state["fac_carga_pp_id"] = int(pp["id"])
                st.rerun()


def _render_carga_formulario(id_pp: int):
    df_skus = get_skus_con_saldo(id_pp)
    if df_skus.empty:
        st.warning("Este PP ya no tiene saldo disponible.")
        st.session_state.pop("fac_carga_pp_id", None)
        return

    st.markdown(
        f"<h4 style='color:#D4AF37;'>PP ID {id_pp} — Selección de Artículos</h4>",
        unsafe_allow_html=True,
    )
    st.caption("Ingresá la cantidad de pares por artículo (múltiplo de pares/caja). 0 = no incluir.")

    cod_cliente = st.text_input(
        "Código Cliente (destino)",
        value="5000",
        key="fac_carga_cliente",
        placeholder="Ej: 5000",
    )

    with st.form(key=f"fac_carga_form_{id_pp}"):
        # Cabecera
        header_cols = st.columns([2, 2, 2, 2, 1, 2])
        for h, lbl in zip(header_cols, ["Línea","Ref.","Material","Color","P/Caja","Pares"]):
            h.markdown(f"<div style='color:#64748B;font-size:.7rem;'>{lbl}</div>",
                       unsafe_allow_html=True)

        for _, sku in df_skus.iterrows():
            det_id    = int(sku["det_id"])
            ppx_caja  = max(int(sku.get("cantidad_cajas") or 1), 1)
            saldo     = int(sku["saldo"])
            c = st.columns([2, 2, 2, 2, 1, 2])
            c[0].markdown(f"<small>{sku['linea']}</small>", unsafe_allow_html=True)
            c[1].markdown(f"<small>{sku['referencia']}</small>", unsafe_allow_html=True)
            c[2].markdown(f"<small>{sku['material']}</small>", unsafe_allow_html=True)
            c[3].markdown(f"<small>{sku['color']}</small>", unsafe_allow_html=True)
            c[4].markdown(f"<small>{ppx_caja}</small>", unsafe_allow_html=True)
            c[5].number_input(
                "Pares", min_value=0, max_value=saldo,
                step=ppx_caja, value=0,
                key=f"_fac_pares_{id_pp}_{det_id}",
                label_visibility="collapsed",
            )

        submitted = st.form_submit_button("💾 Guardar Carga Manual", type="primary",
                                          use_container_width=True)

    if submitted:
        if not cod_cliente.strip():
            st.error("Ingresá un código de cliente.")
            return

        # Agrupar por marca
        marca_items: dict[int, list] = {}
        for _, sku in df_skus.iterrows():
            det_id   = int(sku["det_id"])
            n_pares  = int(st.session_state.get(f"_fac_pares_{id_pp}_{det_id}", 0))
            if n_pares <= 0:
                continue
            ppx_caja = max(int(sku.get("cantidad_cajas") or 1), 1)
            if n_pares % ppx_caja != 0:
                n_pares = ((n_pares // ppx_caja) + 1) * ppx_caja
            n_cajas  = n_pares // ppx_caja
            id_marca = int(sku.get("id_marca") or 0)
            marca_items.setdefault(id_marca, []).append({
                "det_id":  det_id,
                "n_cajas": n_cajas,
                "sku":     sku.to_dict(),
            })

        if not marca_items:
            st.warning("Seleccioná al menos un artículo con cantidad > 0.")
            return

        errores = []
        facturas_ok = []
        for id_marca, items in marca_items.items():
            ok, result = save_carga_manual(id_pp, id_marca, cod_cliente.strip(), items)
            if ok:
                facturas_ok.append(result)
            else:
                errores.append(result)

        if facturas_ok:
            st.success(f"✓ FAC-INT creada(s): {', '.join(facturas_ok)}")
            st.session_state.pop("fac_carga_pp_id", None)
            st.rerun()
        if errores:
            for e in errores:
                st.error(e)
