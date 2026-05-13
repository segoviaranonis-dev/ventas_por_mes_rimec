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
    """
    fi_id   = int(fi.get("id") or 0)
    nro_fi  = fi.get("nro_factura") or "—"
    marca   = fi.get("marca") or "Sin marca"
    caso    = fi.get("caso")  or "Sin caso"
    pares   = int(fi.get("total_pares") or 0)
    monto   = int(fi.get("total_monto") or 0)
    estado  = fi.get("estado") or "—"
    nro_pp  = fi.get("nro_pp") or fi.get("pp_id") or "—"

    bg, fg, badge_label = _estado_badge(estado)
    key_safe = f"{key_prefix}_{fi_id}"

    # ── Cabecera ───────────────────────────────────────────────────────────
    col_header, col_estado, col_actions = st.columns([5, 1.2, 2])

    with col_header:
        st.markdown(
            f"📦 **{nro_fi}** · "
            f"**PP-{nro_pp}** · "
            f"**{marca}** · Caso: <code>{caso}</code> · "
            f"**{pares:,}** pares · **{_fmt_gs(monto)}**",
            unsafe_allow_html=True,
        )
        # Sub-línea opcional con cliente / vendedor / descuentos
        sub_partes = []
        if fi.get("cliente_nombre"):
            sub_partes.append(f"👤 {fi['cliente_nombre']}")
        if fi.get("vendedor_nombre"):
            sub_partes.append(f"🧑‍💼 {fi['vendedor_nombre']}")
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

    with col_actions:
        if actions:
            visibles = [
                a for a in actions
                if not a.get("show_if") or a["show_if"].upper() == estado.upper()
            ]
            if visibles:
                cols = st.columns(len(visibles))
                for col, action in zip(cols, visibles):
                    with col:
                        if st.button(
                            action["label"],
                            key=f"{key_safe}_{action['key']}",
                            type=action.get("type") or "secondary",
                            use_container_width=True,
                        ):
                            if action.get("on_click"):
                                action["on_click"](fi)

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
