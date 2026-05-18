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
from core.fi_card import render_fi_card
from modules.facturacion.logic import get_fi_registro_por_numero, get_factura_lineas
from modules.pedido_proveedor.logic import get_fi_detalles_canonico
from core.tabla_articulos import render_tabla_5pilares

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

    # ── OT-COMPRA-WEB-507-001: Mostrar FAC-INT con render_fi_card ─────────────
    doc_ref = detail.get("factura") or detail.get("documento_ref", "")

    if doc_ref:
        fi_row = get_fi_registro_por_numero(doc_ref)

        if fi_row:
            # R3: Mostrar card FI igual que Facturación y Compra Legal
            st.markdown("### 📄 Factura Interna")
            render_fi_card(
                fi_row,
                detalles=get_fi_detalles_canonico(fi_row["id"]),
                mostrar_detalle=True,
                detalle_colapsado=False,
                key_prefix=f"cw_fi_{id_trp}",
                mostrar_descuentos=True,
            )
        else:
            # R5: Fallback legacy si no hay factura_interna
            st.warning(f"⚠️ Factura Interna **{doc_ref}** no encontrada en BD (legacy).")
            lineas = get_factura_lineas(doc_ref)
            if lineas:
                st.markdown("### 📋 Vista Legacy (5 Pilares)")
                render_tabla_5pilares(lineas, mostrar_totales=True)
    else:
        st.warning("Sin documento_ref vinculado (traspaso sin FAC-INT).")

    # ── R4: Vista técnica (opcional, colapsada) ───────────────────────────────
    df_lines = get_traspaso_detalle_lines(id_trp)

    with st.expander(
        f"🔧 Vista técnica: Stock por talla ({len(df_lines)} línea(s))",
        expanded=False,  # Colapsado por defecto
    ):
        if df_lines.empty:
            snap = detail.get("snapshot", {})
            st.caption("Líneas aún no resueltas (combinacion_id pendiente).")
            if snap:
                st.json(snap)
        else:
            cols_display = ["linea","referencia","material","color","talla","cantidad"]
            cols_rename = {
                "linea":     "Línea",
                "referencia":"Ref.",
                "material":  "Material",
                "color":     "Color",
                "talla":     "Talla",
                "cantidad":  "Pares",
            }

            if "caso_nombre" in df_lines.columns:
                cols_display.append("caso_nombre")
                cols_rename["caso_nombre"] = "Caso"
            if "precio" in df_lines.columns:
                cols_display.append("precio")
                cols_rename["precio"] = "Precio LP"

            st.dataframe(
                df_lines[cols_display].rename(columns=cols_rename),
                hide_index=True,
                use_container_width=True,
            )
