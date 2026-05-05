# =============================================================================
# MÓDULO: Aprobación de Pedidos RIMEC
# ARCHIVO: modules/aprobacion_pedidos/ui.py
# PARADIGMA: BD como único canal. Cada célula se aprueba individualmente.
#   - Tab "Pendientes": Pedidos web con células para aprobar/rechazar una a una
#   - Tab "Confirmadas": FIs aprobadas (historial)
#   - Tab "Anuladas": FIs rechazadas con stock revertido
# =============================================================================

import ast
import json
import streamlit as st
from modules.aprobacion_pedidos.logic import (
    get_pedidos_pendientes, get_pedidos_autorizados, get_pedidos_rechazados,
    rechazar_pedido, crear_preventa_desde_celula, get_linea_caso_map,
    get_preventa_de_celula, get_fi_detalles,
    # Flujo Reserva → Liberación
    get_fi_reservadas, get_fi_confirmadas, get_fi_anuladas,
    confirmar_fi, anular_fi,
)


def _parse_payload(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        try:
            return ast.literal_eval(raw)
        except Exception:
            return {}


_LISTAS = {1: "LPN", 2: "LPC02", 3: "LPC03", 4: "LPC04"}


def _fmt_gs(n) -> str:
    try:
        return f"Gs. {int(n):,}".replace(",", ".")
    except Exception:
        return "—"


def _descuentos_label(p: dict) -> str:
    ds = [p.get(f"descuento_{i}", 0) or 0 for i in range(1, 5)]
    activos = [f"{d}%" for d in ds if d]
    return " + ".join(activos) if activos else "Sin descuento"


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DE CÉLULAS
# ─────────────────────────────────────────────────────────────────────────────

def construir_celulas(lotes: list) -> list:
    """Reagrupa items por PP+Marca+Caso (caso desde pilar linea_caso)."""
    pp_ids = list({int(l["pp_id"]) for l in lotes if l.get("pp_id")})
    linea_caso_map = get_linea_caso_map(pp_ids)

    grupos: dict[str, dict] = {}
    for lote in lotes:
        pp_id  = lote.get("pp_id")
        pp_nro = lote.get("pp_nro", str(pp_id))
        for marca_data in lote.get("marcas", []):
            marca = marca_data.get("marca", "SIN_MARCA")
            for item in marca_data.get("items", []):
                linea_cod = str(item.get("linea_codigo", "")).strip()
                caso      = linea_caso_map.get(linea_cod) or linea_cod or "SIN_CASO"
                clave = f"{pp_id}|{marca}|{caso}"
                if clave not in grupos:
                    grupos[clave] = {
                        "pp_id":       pp_id,
                        "pp_nro":      pp_nro,
                        "marca":       marca,
                        "caso":        caso,
                        "items":       [],
                        "total_pares": 0,
                        "total_neto":  0,
                    }
                grupos[clave]["items"].append(item)
                grupos[clave]["total_pares"] += item.get("pares", 0)
                grupos[clave]["total_neto"]  += item.get("subtotal", 0)
    return list(grupos.values())


# ─────────────────────────────────────────────────────────────────────────────
# ACCIONES DE CÉLULA
# ─────────────────────────────────────────────────────────────────────────────

def aprobar_celula(pedido_id: int, celula: dict):
    from modules.aprobacion_pedidos.logic import crear_preventa_desde_celula
    ok, msg = crear_preventa_desde_celula(pedido_id, celula)

    if ok:
        st.success(f"✅ Preventa generada: {msg}")
        import time; time.sleep(1)
        st.rerun()
    else:
        st.error(f"❌ Error: {msg}")


def rechazar_celula(pedido_id: int, celula: dict, motivo: str):
    from core.auditoria import log_flujo
    log_flujo(
        entidad="pedido_venta_rimec", entidad_id=pedido_id,
        accion="CELULA_RECHAZADA",
        snap={
            "pp_id": celula.get("pp_id"),
            "marca": celula.get("marca"),
            "caso":  celula.get("caso"),
            "motivo": motivo,
        },
    )
    st.warning(f"⚠️ Célula rechazada — stock intacto. Motivo: {motivo or 'sin motivo'}")


# ─────────────────────────────────────────────────────────────────────────────
# RENDER DE UNA CÉLULA (dentro de un pedido pendiente)
# ─────────────────────────────────────────────────────────────────────────────

def _render_celula(pedido_id: int, celula: dict):
    clave    = f"{celula['pp_id']}|{celula['marca']}|{celula['caso']}"
    key_safe = clave.replace("|", "_").replace(" ", "_")

    preventa = get_preventa_de_celula(
        int(celula["pp_id"]), celula["marca"], celula["caso"]
    )

    with st.container():
        col_header, col_estado = st.columns([5, 1])
        with col_header:
            st.markdown(
                f"📦 **PP-{celula['pp_nro']}** · "
                f"**{celula['marca']}** · "
                f"Caso: `{celula['caso']}` · "
                f"{celula['total_pares']:,} pares · "
                f"{_fmt_gs(celula['total_neto'])}"
            )
        with col_estado:
            if preventa:
                st.success(f"✅ {preventa['nro_factura']}")

        # Detalle de items
        for item in celula["items"]:
            ci, cd, cn = st.columns([1, 4, 2])
            with ci:
                img = item.get("imagen_url", "")
                if img:
                    try:
                        st.image(img, width=55)
                    except Exception:
                        st.write("📦")
                else:
                    st.write("📦")
            with cd:
                linea = item.get("linea_codigo", "?")
                ref   = item.get("ref_codigo",   "?")
                color = item.get("color_nombre", "")
                st.markdown(
                    f"**L{linea} · R{ref}** "
                    f"<span style='color:#64748B;font-size:0.8em'>{color}</span>",
                    unsafe_allow_html=True,
                )
                gradas = item.get("gradas_fmt", "")
                if gradas:
                    st.caption(gradas)
            with cn:
                st.write(f"{item.get('cajas', 0)} caj · {item.get('pares', 0)} p")
                st.caption(_fmt_gs(item.get("subtotal", 0)))

        # Acciones: aprobar/rechazar solo si aún no tiene preventa
        if not preventa:
            col_a, col_r, col_mot = st.columns([1, 1, 3])
            with col_a:
                if st.button("✅ Aprobar", key=f"ap_{key_safe}_{pedido_id}", type="primary"):
                    aprobar_celula(pedido_id, celula)
            with col_mot:
                st.text_input(
                    "Motivo rechazo",
                    key=f"mot_{key_safe}_{pedido_id}",
                    label_visibility="collapsed",
                    placeholder="Motivo de rechazo (opcional)",
                )
            with col_r:
                if st.button("❌ Rechazar", key=f"rch_{key_safe}_{pedido_id}"):
                    motivo = st.session_state.get(f"mot_{key_safe}_{pedido_id}", "Sin motivo")
                    rechazar_celula(pedido_id, celula, motivo)
                    st.rerun()

        st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# TARJETA DE PEDIDO PENDIENTE
# ─────────────────────────────────────────────────────────────────────────────

def _render_tarjeta_pendiente(p: dict):
    nro    = p.get("nro_pedido", f"#{p['id']}")
    cli    = p.get("cliente_nombre", "—")
    total_p = p.get("total_pares", 0)
    total_m = p.get("total_monto",  0)

    with st.expander(f"**{nro}** · {cli} · {total_p:,} pares · {_fmt_gs(total_m)}", expanded=True):

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cliente",  cli)
        c2.metric("Vendedor", p.get("vendedor_nombre") or "—")
        c3.metric("Plazo",    p.get("plazo_nombre")    or "—")
        c4.metric("Lista",    _LISTAS.get(p.get("lista_precio_id", 1), "?"))
        st.caption(f"Descuentos: {_descuentos_label(p)}")

        st.divider()
        st.markdown("### Células de Aprobación")
        st.caption("Cada célula se aprueba por separado. El pedido pasa a AUTORIZADO cuando todas estén aprobadas.")

        payload = _parse_payload(p.get("payload_json"))
        lotes   = payload.get("lotes", [])
        celulas = construir_celulas(lotes)

        if not celulas:
            st.warning("⚠️ No se encontraron ítems en este pedido.")
            return

        for celula in celulas:
            _render_celula(p["id"], celula)

        # Rechazo total del pedido
        st.divider()
        col_mot, col_btn = st.columns([3, 1])
        with col_mot:
            motivo_total = st.text_input(
                "Motivo rechazo TOTAL del pedido",
                key=f"mot_total_{p['id']}",
                placeholder="Rechazar el pedido completo…",
            )
        with col_btn:
            st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
            if st.button("❌ Rechazar pedido", key=f"rech_{p['id']}", use_container_width=True):
                if not motivo_total.strip():
                    st.warning("Ingresá un motivo para rechazar el pedido completo.")
                else:
                    ok, msg = rechazar_pedido(p["id"], motivo_total)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)


# ─────────────────────────────────────────────────────────────────────────────
# RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_aprobacion():
    st.markdown("## ✅ Aprobación de Pedidos RIMEC")
    st.caption("Cada célula (PP+Marca+Caso) se aprueba individualmente. El pedido cierra cuando todas estén confirmadas.")

    tab_pend, tab_conf, tab_anul = st.tabs([
        "📋 Pendientes",
        "✅ Confirmadas",
        "❌ Anuladas",
    ])

    # ── Tab Pendientes: Pedidos web con células para aprobar ─────────────
    with tab_pend:
        pedidos = get_pedidos_pendientes()
        if not pedidos:
            st.info("No hay pedidos pendientes de aprobación.", icon="📋")
        else:
            st.caption(f"{len(pedidos)} pedido(s) esperando autorización")
            for p in pedidos:
                _render_tarjeta_pendiente(p)

    # ── Tab Confirmadas: FIs aprobadas con detalle completo ──────────────
    with tab_conf:
        fis = get_fi_confirmadas()
        if not fis:
            st.info("No hay facturas confirmadas aún.")
        else:
            st.caption(f"Últimas {len(fis)} facturas confirmadas")
            for fi in fis:
                nro = fi.get("nro_factura", "")
                cli = fi.get("cliente_nombre", "—")
                marca = fi.get("marca", "—")
                caso = fi.get("caso", "—")
                pares = fi.get("total_pares", 0)
                monto = fi.get("total_monto", 0)
                nro_pp = fi.get("nro_pp", "—")
                vendedor = fi.get("vendedor_nombre", "—")

                with st.expander(
                    f"✅ **{nro}** · {cli} · {marca} · {pares:,} pares · {_fmt_gs(monto)}",
                    expanded=True,
                ):
                    # Cabecera
                    c0, c1, c2, c3, c4 = st.columns([2, 1, 1, 1, 1])
                    c0.markdown(f"### `{nro}`")
                    c0.caption(f"PP {nro_pp} · Caso: {caso}")
                    c1.metric("Cliente", cli)
                    c2.metric("Marca", marca)
                    c3.metric("Pares", f"{pares:,}")
                    c4.metric("Monto", _fmt_gs(monto))
                    st.caption(
                        f"Vendedor: {vendedor} · "
                        f"Descuentos: {_descuentos_label(fi)}"
                    )

                    # Productos con miniatura
                    detalles = get_fi_detalles(fi["id"])
                    if detalles:
                        st.markdown("---")
                        for det in detalles:
                            snap = det.get("linea_snapshot", {})
                            ci, cd, cn = st.columns([1, 4, 2])
                            with ci:
                                img = snap.get("imagen_url", "")
                                if img:
                                    try:
                                        st.image(img, width=55)
                                    except Exception:
                                        st.write("📦")
                                else:
                                    st.write("📦")
                            with cd:
                                linea = snap.get("linea_codigo", "?")
                                ref = snap.get("ref_codigo", "?")
                                color = snap.get("color_nombre", "")
                                st.markdown(
                                    f"**L{linea} · R{ref}** "
                                    f"<span style='color:#64748B;font-size:0.8em'>{color}</span>",
                                    unsafe_allow_html=True,
                                )
                                gradas = snap.get("gradas_fmt", "")
                                if gradas:
                                    st.caption(gradas)
                            with cn:
                                st.write(f"{det.get('cajas', 0)} caj · {det.get('pares', 0)} p")
                                st.caption(f"Neto: {_fmt_gs(det.get('precio_neto', 0))}")
                                st.caption(f"Sub: {_fmt_gs(det.get('subtotal', 0))}")

    # ── Tab Anuladas: Historial de FIs rechazadas ────────────────────────
    with tab_anul:
        fis = get_fi_anuladas()
        if not fis:
            st.info("No hay facturas anuladas.")
        else:
            st.caption(f"Últimas {len(fis)} facturas anuladas")
            for fi in fis:
                st.markdown(
                    f"❌ **{fi.get('nro_factura','')}** · "
                    f"{fi.get('cliente_nombre','—')} · "
                    f"PP-{fi.get('nro_pp','—')} — "
                    f"_{fi.get('notas','sin motivo')}_"
                )
