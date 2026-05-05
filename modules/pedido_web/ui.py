# =============================================================================
# MÓDULO: Pedidos Web — UI
# ARCHIVO: modules/pedido_web/ui.py
# DESCRIPCIÓN: Panel de recepción y gestión de pedidos desde el catálogo Bazzar Web.
#              Confirmar → descuenta stock vía VENTA_WEB.
#              Rechazar  → cambia estado sin tocar stock.
# =============================================================================

import streamlit as st
import pandas as pd
from modules.pedido_web.logic import (
    get_resumen_estados,
    get_pedidos,
    get_detalle_pedido,
    confirmar_pedido,
    rechazar_pedido,
)

NAVY   = "#1E3A5F"
ORANGE = "#F97316"

ESTADO_COLOR = {
    "PENDIENTE":  "#F97316",
    "CONFIRMADO": "#10B981",
    "RECHAZADO":  "#EF4444",
}
ESTADO_ICONO = {
    "PENDIENTE":  "🟠",
    "CONFIRMADO": "🟢",
    "RECHAZADO":  "🔴",
}


def _badge(estado: str) -> str:
    color = ESTADO_COLOR.get(estado, "#94A3B8")
    return f'<span style="background:{color};color:white;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700">{estado}</span>'


def _fmt_gs(valor) -> str:
    try:
        return f"Gs. {int(valor):,}".replace(",", ".")
    except Exception:
        return "Consultar"


def render_pedido_web():
    st.markdown(
        f'<h2 style="color:{NAVY};margin-bottom:4px">🛒 Pedidos Web</h2>'
        f'<p style="color:#64748b;font-size:13px;margin-bottom:20px">'
        f'Recepción de órdenes del catálogo Bazzar · Confirmar descuenta stock</p>',
        unsafe_allow_html=True,
    )

    # ── Métricas rápidas ──
    resumen = get_resumen_estados()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🟠 Pendientes",  resumen.get("PENDIENTE",  0))
    with col2:
        st.metric("🟢 Confirmados", resumen.get("CONFIRMADO", 0))
    with col3:
        st.metric("🔴 Rechazados",  resumen.get("RECHAZADO",  0))

    st.markdown("---")

    # ── Filtro estado desde sidebar ──
    estado_filtro = st.session_state.get("pw_estado_filtro", "PENDIENTE")

    # ── Feedback de acciones ──
    if "_pw_msg" in st.session_state:
        msg, ok = st.session_state.pop("_pw_msg")
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    # ── Lista de pedidos ──
    pedidos = get_pedidos(estado_filtro)

    if pedidos.empty:
        st.info(f"No hay pedidos en estado **{estado_filtro}**.")
        return

    st.markdown(
        f'<p style="color:#64748b;font-size:12px">'
        f'{len(pedidos)} pedido(s) en estado <b>{estado_filtro}</b></p>',
        unsafe_allow_html=True,
    )

    for _, pedido in pedidos.iterrows():
        pid      = int(pedido["id"])
        numero   = f"#{pid:06d}"
        cliente  = pedido.get("cliente_nombre") or "—"
        cedula   = pedido.get("cedula") or "—"
        telefono = pedido.get("cliente_telefono") or "—"
        total_gs = _fmt_gs(pedido.get("total", 0))
        fecha    = str(pedido.get("created_at", ""))[:16]
        notas    = pedido.get("notas_cliente") or ""

        with st.expander(
            f"{ESTADO_ICONO.get(estado_filtro,'⚪')}  **{numero}** — {cliente}  ·  {total_gs}  ·  {fecha}",
            expanded=(estado_filtro == "PENDIENTE"),
        ):
            # Datos cliente
            col_a, col_b, col_c = st.columns([2, 2, 2])
            with col_a:
                st.markdown(f"**👤 Cliente:** {cliente}")
                st.markdown(f"**🪪 Cédula:** {cedula}")
            with col_b:
                st.markdown(f"**📞 Teléfono:** {telefono}")
                email = pedido.get("cliente_email") or "—"
                st.markdown(f"**✉ Email:** {email}")
            with col_c:
                st.markdown(f"**💰 Total:** {total_gs}")
                st.markdown(f"**📅 Fecha:** {fecha}")

            if notas:
                st.info(f"📝 Notas del cliente: {notas}")

            # Detalle de artículos
            detalle = get_detalle_pedido(pid)
            if not detalle.empty:
                st.markdown("**Artículos:**")
                for _, item in detalle.iterrows():
                    precio_str = _fmt_gs(item.get("precio_unitario", 0))
                    st.markdown(
                        f"• **{item['marca']}** &nbsp;|&nbsp; "
                        f"<span style='color:{NAVY};font-weight:700'>{item['linea_codigo']}</span>"
                        f"<span style='color:#94a3b8'> · </span>"
                        f"<span style='color:{ORANGE};font-weight:700'>{item['referencia_codigo']}</span>"
                        f" &nbsp;— {item['color_nombre']} T.{item['talla_codigo']}"
                        f" &nbsp;✕ {item['cantidad']} &nbsp;= {precio_str}",
                        unsafe_allow_html=True,
                    )

            # ── Acciones (solo para PENDIENTE) ──
            if estado_filtro == "PENDIENTE":
                st.markdown("---")
                col_ok, col_no, col_motivo = st.columns([1, 1, 3])
                with col_motivo:
                    motivo = st.text_input(
                        "Motivo de rechazo (opcional)",
                        key=f"motivo_{pid}",
                        placeholder="Ej: Sin stock suficiente",
                        label_visibility="collapsed",
                    )
                with col_ok:
                    if st.button(
                        "✅ Confirmar",
                        key=f"conf_{pid}",
                        use_container_width=True,
                        type="primary",
                    ):
                        ok, msg = confirmar_pedido(pid)
                        st.session_state["_pw_msg"] = (msg, ok)
                        st.rerun()
                with col_no:
                    if st.button(
                        "❌ Rechazar",
                        key=f"rech_{pid}",
                        use_container_width=True,
                    ):
                        ok, msg = rechazar_pedido(pid, motivo)
                        st.session_state["_pw_msg"] = (msg, ok)
                        st.rerun()

            # Notas admin (CONFIRMADO / RECHAZADO)
            if estado_filtro in ("CONFIRMADO", "RECHAZADO"):
                notas_admin = pedido.get("notas_admin") or ""
                if notas_admin:
                    st.caption(f"📋 Nota admin: {notas_admin}")
