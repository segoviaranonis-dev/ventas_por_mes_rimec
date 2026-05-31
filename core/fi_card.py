"""
core/fi_card.py — Componente CANÓNICO de Factura Interna (FI).

LEY FUNDAMENTAL:
    Toda referencia a una `factura_interna` en la UI debe renderizarse con
    `render_fi_card(...)`. Es la única fuente de verdad visual.

Datos mínimos esperados (dict `fi`):
    id, nro_factura, pp_id, marca, caso, total_pares, total_monto, estado
Opcionales (mejoran el render):
    nro_pp, cliente_nombre, vendedor_nombre, marca_id, caso_id, created_at

Items (lista de dict `detalles`):
    pares, cajas, subtotal, precio_neto, linea_snapshot (dict con
    linea_codigo, ref_codigo, color_nombre, gradas_fmt, imagen_url)

Acciones (lista `actions`, opcional):
    Cada acción: {
        "label":    "✅ Confirmar",
        "key":      "conf_fi_123",
        "type":     "primary" | None,
        "on_click": callable que retorna (ok: bool, msg: str),
        "show_if":  str | None  (estado requerido para mostrar, ej. "RESERVADA")
    }
"""
from __future__ import annotations

import ast
import json
from typing import Callable, Iterable

import streamlit as st


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_gs(n) -> str:
    try:
        return f"Gs. {int(n):,}".replace(",", ".")
    except Exception:
        return "—"


def _parse_snap(snap) -> dict:
    if isinstance(snap, dict):
        return snap
    if isinstance(snap, str):
        try:
            return json.loads(snap)
        except Exception:
            try:
                return ast.literal_eval(snap)
            except Exception:
                return {}
    return {}


def _estado_badge(estado: str) -> tuple[str, str, str]:
    """Devuelve (color_fondo, color_texto, label) según estado de la FI."""
    estado = (estado or "").upper()
    if estado == "CONFIRMADA":
        return "#15803D", "#FFFFFF", "✅ CONFIRMADA"
    if estado == "RESERVADA":
        return "#CA8A04", "#FFFFFF", "⏳ RESERVADA"
    if estado == "ANULADA":
        return "#B91C1C", "#FFFFFF", "❌ ANULADA"
    if estado == "FACTURADA":
        return "#1D4ED8", "#FFFFFF", "📄 FACTURADA"
    if estado == "CANCELADA":
        return "#7F1D1D", "#FFFFFF", "🚫 CANCELADA"
    return "#475569", "#FFFFFF", estado or "—"


# ─────────────────────────────────────────────────────────────────────────────
# Render principal
# ─────────────────────────────────────────────────────────────────────────────

def render_fi_card(
    fi: dict,
    detalles: Iterable[dict] | None = None,
    *,
    actions: list[dict] | None = None,
    mostrar_detalle: bool = True,
    detalle_colapsado: bool = False,
    key_prefix: str = "fi",
    mostrar_descuentos: bool = False,
    modo_edicion: bool = False,
    on_actualizar: Callable | None = None,
    plazos_disponibles: list[dict] | None = None,
):
    """Renderiza UNA factura interna con el formato canónico.

    Parameters
    ----------
    fi : dict
        Datos de la FI (ver docstring del módulo).
    detalles : iterable[dict] | None
        Items de la FI. Si None y `mostrar_detalle=True`, se omite la sección.
    actions : list[dict] | None
        Botones a mostrar. Cada acción puede tener `show_if` para limitarse
        a ciertos estados (ej. "RESERVADA").
    mostrar_detalle : bool
        Si True y hay detalles, renderiza los items.
    detalle_colapsado : bool
        Si True, los items se envuelven en un `expander` colapsado.
    key_prefix : str
        Prefijo para keys de Streamlit (evita colisiones entre módulos).
    mostrar_descuentos : bool
        Si True, muestra la línea con descuentos aplicados.
    modo_edicion : bool
        Si True y estado=RESERVADA, muestra controles para editar lista_precio,
        descuentos y plazo.
    on_actualizar : callable | None
        Función callback que se llama al hacer click en "Actualizar encabezado".
        Recibe (fi_id, lista_precio_id, desc1, desc2, desc3, desc4, plazo_id).
    plazos_disponibles : list[dict] | None
        Lista de plazos disponibles [{id_plazo, descp_plazo}, ...].
    """
    fi_id   = int(fi.get("id") or 0)
    nro_fi  = fi.get("nro_factura") or "—"
    marca   = fi.get("marca") or "Sin marca"
    caso    = fi.get("caso")  or "Sin caso"
    pares   = int(fi.get("total_pares") or 0)
    monto   = int(fi.get("total_monto") or 0)
    estado  = fi.get("estado") or "—"
    nro_pp  = fi.get("nro_pp") or fi.get("pp_id") or "—"
    proforma = fi.get("proforma") or ""

    # Matrimonio PP + Proforma
    pp_display = nro_pp
    if proforma:
        pp_display = f"{nro_pp} ({proforma})"

    bg, fg, badge_label = _estado_badge(estado)
    key_safe = f"{key_prefix}_{fi_id}"

    # ── Cabecera ───────────────────────────────────────────────────────────
    col_header, col_estado = st.columns([5, 1.25])

    with col_header:
        st.markdown(
            f"📦 **{nro_fi}** · "
            f"**{pp_display}** · "
            f"**{marca}** · Caso: <code>{caso}</code> · "
            f"**{pares:,}** pares · **{_fmt_gs(monto)}**",
            unsafe_allow_html=True,
        )
        # Sub-línea opcional con cliente / vendedor / descuentos / quincena
        sub_partes = []
        if fi.get("cliente_nombre"):
            sub_partes.append(f"👤 {fi['cliente_nombre']}")
        if fi.get("vendedor_nombre"):
            sub_partes.append(f"🧑‍💼 {fi['vendedor_nombre']}")
        # Cable de acero: mostrar quincena (dato duro)
        if fi.get("quincena_llegada"):
            sub_partes.append(f"📦 {fi['quincena_llegada']}")
        if mostrar_descuentos:
            ds = [fi.get(f"descuento_{i}", 0) or 0 for i in range(1, 5)]
            activos = [f"{d}%" for d in ds if d]
            if activos:
                sub_partes.append("Desc: " + " + ".join(activos))
        if sub_partes:
            st.caption(" · ".join(sub_partes))

    with col_estado:
        st.markdown(
            f"<div style='background:{bg};color:{fg};padding:6px 12px;"
            f"border-radius:18px;text-align:center;font-weight:700;"
            f"font-size:.75rem;letter-spacing:.05em;'>{badge_label}</div>",
            unsafe_allow_html=True,
        )

    if actions:
        visibles = [
            a for a in actions
            if not a.get("show_if") or a["show_if"].upper() == estado.upper()
        ]
        if visibles:
            with st.expander("⚙️ Acciones de factura interna", expanded=False):
                st.markdown('<div class="nx-action-panel">', unsafe_allow_html=True)
                for action in visibles:
                    if st.button(
                        action["label"],
                        key=f"{key_safe}_{action['key']}",
                        type=action.get("type") or "secondary",
                        use_container_width=True,
                    ):
                        if action.get("on_click"):
                            action["on_click"](fi)
                st.markdown('</div>', unsafe_allow_html=True)

    # ── Encabezado Editable ────────────────────────────────────────────────
    if modo_edicion and estado.upper() == "RESERVADA" and on_actualizar:
        st.markdown("---")
        st.markdown("### ⚙️ Editar Encabezado de FI")
        st.caption("Modifica lista de precio, descuentos o plazo. Los precios se recalcularán automáticamente.")

        col_lp, col_plazo = st.columns(2)

        with col_lp:
            listas_precio = {1: "LPN", 2: "LPC02", 3: "LPC03", 4: "LPC04"}
            lista_actual = int(fi.get("lista_precio_id") or 1)
            lista_nueva = st.selectbox(
                "Lista de Precio",
                options=list(listas_precio.keys()),
                format_func=lambda x: listas_precio[x],
                index=list(listas_precio.keys()).index(lista_actual),
                key=f"{key_safe}_lista_precio"
            )

        with col_plazo:
            if plazos_disponibles:
                plazo_actual = int(fi.get("plazo_id") or 1)
                plazo_options = {p["id_plazo"]: p["descp_plazo"] for p in plazos_disponibles}
                plazo_nuevo = st.selectbox(
                    "Plazo",
                    options=list(plazo_options.keys()),
                    format_func=lambda x: plazo_options[x],
                    index=list(plazo_options.keys()).index(plazo_actual) if plazo_actual in plazo_options else 0,
                    key=f"{key_safe}_plazo"
                )

        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        with col_d1:
            desc_1 = st.number_input(
                "Descuento 1 (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(fi.get("descuento_1") or 0),
                step=0.5,
                key=f"{key_safe}_desc1"
            )
        with col_d2:
            desc_2 = st.number_input(
                "Descuento 2 (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(fi.get("descuento_2") or 0),
                step=0.5,
                key=f"{key_safe}_desc2"
            )
        with col_d3:
            desc_3 = st.number_input(
                "Descuento 3 (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(fi.get("descuento_3") or 0),
                step=0.5,
                key=f"{key_safe}_desc3"
            )
        with col_d4:
            desc_4 = st.number_input(
                "Descuento 4 (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(fi.get("descuento_4") or 0),
                step=0.5,
                key=f"{key_safe}_desc4"
            )

        col_btn, col_spacer = st.columns([1, 3])
        with col_btn:
            if st.button("💾 Actualizar Encabezado", key=f"{key_safe}_actualizar", type="primary"):
                on_actualizar(fi_id, lista_nueva, desc_1, desc_2, desc_3, desc_4, plazo_nuevo)

    # ── Detalle de items ──────────────────────────────────────────────────
    if mostrar_detalle and detalles:
        det_list = list(detalles)
        if detalle_colapsado:
            with st.expander(f"Ver detalle ({len(det_list)} item{'s' if len(det_list) != 1 else ''})",
                             expanded=False):
                _render_items(det_list)
        else:
            _render_items(det_list)


def _render_items(detalles: list[dict]) -> None:
    """Tabla visual de items de una FI — formato canónico."""
    for det in detalles:
        snap = _parse_snap(det.get("linea_snapshot", {}))

        col_img, col_data, col_cant = st.columns([1, 4, 2])

        with col_img:
            img = snap.get("imagen_url", "")
            if img:
                try:
                    st.image(img, width=58)
                except Exception:
                    st.write("📦")
            else:
                st.write("📦")

        with col_data:
            linea = snap.get("linea_codigo", "?")
            ref   = snap.get("ref_codigo",   "?")
            color = snap.get("color_nombre", "")
            st.markdown(
                f"**L{linea} · R{ref}** "
                f"<span style='color:#94A3B8;font-size:.78rem;'>{color}</span>",
                unsafe_allow_html=True,
            )
            gradas = snap.get("gradas_fmt", "")
            if gradas:
                st.caption(gradas)

        with col_cant:
            cajas = int(det.get("cajas") or 0)
            pares = int(det.get("pares") or 0)
            st.write(f"**{cajas}** caj · **{pares}** p")
            st.caption(_fmt_gs(det.get("subtotal", 0)))
