# =============================================================================
# MÓDULO: Compra Web
# ARCHIVO: modules/compra_web/ui.py
# DESCRIPCIÓN: Estación 4 — Panel Web Bazar.
#
#  Ve traspasos en estado ENVIADO desde Facturación RIMEC.
#  Botón "📥 CONFIRMAR RECEPCIÓN" → CONFIRMADO + crea movimiento en ALM_WEB_01.
#  Después, el stock aparece en Depósito Web.
# =============================================================================

import streamlit as st
import pandas as pd

from modules.compra_legal.logic import (
    get_traspasos,
    get_traspaso_detail,
    get_traspaso_detalle_lines,
    procesar_ingreso_bazar,
)

_ESTADO_COLOR = {
    "BORRADOR":   "#64748B",
    "ENVIADO":    "#F59E0B",
    "CONFIRMADO": "#22C55E",
}
_ESTADO_LABEL = {
    "BORRADOR":   "🕒 En Tránsito",
    "ENVIADO":    "✅ Listo p/ Recibir",
    "CONFIRMADO": "📦 Recibido",
}


def _fmt_date(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    return str(val)[:10]


def render_compra_web():
    st.markdown(
        "<h2 style='color:#D4AF37;margin-bottom:4px;'>🛒 Compra Web</h2>"
        "<p style='color:#94A3B8;margin-top:0;'>"
        "Recepción de mercadería enviada desde Facturación RIMEC</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    if st.session_state.get("cw_trp_selected_id"):
        _render_detalle_traspaso(int(st.session_state["cw_trp_selected_id"]))
    else:
        _render_lista_traspasos()


# ─────────────────────────────────────────────────────────────────────────────
# LISTA DE TRASPASOS
# ─────────────────────────────────────────────────────────────────────────────

def _render_lista_traspasos():
    estado_f = st.session_state.get("cw_estado_filtro", "ENVIADO")
    df = get_traspasos(estado=estado_f)

    if df.empty:
        st.info("No hay traspasos disponibles.")
        st.caption("Los traspasos aparecen aquí cuando Facturación presiona '🚀 ENVIAR A WEB BAZAR'.")
        return

    total_pares = int(df["pares_detalle"].sum())
    n_env = int((df["estado"] == "ENVIADO").sum())
    n_con = int((df["estado"] == "CONFIRMADO").sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Traspasos", len(df))
    c2.metric("Listos p/ Recibir", n_env)
    c3.metric("Confirmados", n_con)

    st.divider()

    cols = st.columns(2)
    for idx, (_, trp) in enumerate(df.iterrows()):
        col    = cols[idx % 2]
        estado = str(trp["estado"])
        e_col  = _ESTADO_COLOR.get(estado, "#94A3B8")
        e_lab  = _ESTADO_LABEL.get(estado, estado)
        pares  = int(trp["pares_detalle"] or 0)

        with col:
            st.markdown(
                f"""<div style="background:linear-gradient(135deg,#1C2E3F,#0F1E2F);
                                border:1px solid #334155;border-radius:12px;
                                padding:16px 20px;margin-bottom:4px;">
                  <div style="display:flex;justify-content:space-between;">
                    <div>
                      <div style="font-size:.68rem;color:#64748B;text-transform:uppercase;">
                        Traspaso</div>
                      <div style="font-size:1rem;font-weight:700;color:#F1F5F9;">
                        {trp['numero_registro']}</div>
                      <div style="font-size:.75rem;color:#94A3B8;margin-top:2px;">
                        FAC: {trp['factura']}
                        &nbsp;·&nbsp;Compra: {trp['compra']}</div>
                    </div>
                    <span style="background:{e_col}22;color:{e_col};font-size:.68rem;
                                 font-weight:600;padding:3px 8px;border-radius:4px;">
                      {e_lab}
                    </span>
                  </div>
                  <div style="margin-top:10px;color:#94A3B8;font-size:.78rem;">
                    {pares:,} pares resueltos
                    &nbsp;·&nbsp;{_fmt_date(trp['fecha_traspaso'])}
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button(
                "📋 Ver detalle",
                key=f"cw_trp_{trp['id']}",
                use_container_width=True,
                type="primary" if estado == "ENVIADO" else "secondary",
            ):
                st.session_state["cw_trp_selected_id"] = int(trp["id"])
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# DETALLE + CONFIRMAR RECEPCIÓN
# ─────────────────────────────────────────────────────────────────────────────

def _render_detalle_traspaso(id_trp: int):
    detail = get_traspaso_detail(id_trp)
    if not detail:
        st.error("Traspaso no encontrado.")
        return

    estado = detail["estado"]
    e_col  = _ESTADO_COLOR.get(estado, "#94A3B8")
    e_lab  = _ESTADO_LABEL.get(estado, estado)

    st.markdown(
        f"<h2 style='color:#D4AF37;margin-bottom:2px;'>🛒 {detail['numero_registro']}</h2>"
        f"<p style='color:#94A3B8;margin:0;'>"
        f"FAC: <b style='color:#F1F5F9;'>{detail['factura']}</b>"
        f"&nbsp;·&nbsp;Compra: <b style='color:#F1F5F9;'>{detail['compra']}</b>"
        f"&nbsp;·&nbsp;<b style='color:{e_col};'>{e_lab}</b></p>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Botón CONFIRMAR RECEPCIÓN ─────────────────────────────────────────────
    if estado in ("ENVIADO", "BORRADOR"):
        col_btn, col_info = st.columns([2, 3])
        col_info.caption(
            "Al confirmar, el sistema registra el ingreso en el Depósito Web (ALM_WEB_01) "
            "y el stock queda disponible en la galería de la tienda."
        )
        if col_btn.button(
            "📥  CONFIRMAR RECEPCIÓN",
            key=f"cw_confirmar_{id_trp}",
            type="primary",
            use_container_width=True,
        ):
            ok, msg = procesar_ingreso_bazar(id_trp)
            if ok:
                st.success(f"✓ {msg}")
                st.session_state.pop("cw_trp_selected_id", None)
                st.rerun()
            else:
                st.error(msg)
    elif estado == "CONFIRMADO":
        st.success("📦 Recepción confirmada — stock ingresado al Depósito Web.")

    st.divider()

    # ── Líneas de artículos ───────────────────────────────────────────────────
    df_lines = get_traspaso_detalle_lines(id_trp)

    with st.expander(
        f"📋  Artículos (5 Pilares + Talla)  —  {len(df_lines)} línea(s)",
        expanded=True,
    ):
        if df_lines.empty:
            snap = detail.get("snapshot", {})
            st.warning("Líneas aún no resueltas (combinacion_id pendiente).")
            if snap:
                st.json(snap)
        else:
            st.dataframe(
                df_lines[["linea","referencia","material","color","talla","cantidad"]].rename(
                    columns={
                        "linea":     "Línea",
                        "referencia":"Ref.",
                        "material":  "Material",
                        "color":     "Color",
                        "talla":     "Talla",
                        "cantidad":  "Pares",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
