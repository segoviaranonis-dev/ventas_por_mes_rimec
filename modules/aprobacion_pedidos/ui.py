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
    # Lectura de FIs ya creadas por el RPC 028
    get_fis_de_pedido, get_fi_detalles_lite,
    # Flujo Reserva → Liberación
    get_fi_reservadas, get_fi_confirmadas, get_fi_anuladas,
    confirmar_fi, anular_fi,
)
from core.fi_card import render_fi_card


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
    """Reagrupa items por PP+Marca+Caso. Soporta DOS formatos de payload:

      · NUEVO (rimec-web post-fix A):  lote.facturas[].items[]
        Cada factura ya viene con marca/caso → se respeta tal cual.

      · VIEJO (pre-028):  lote.marcas[].items[]
        Marca viene del nivel 2; caso se infiere desde el pilar `linea`.

    Fallback solo se usa cuando un pedido no tiene FIs creadas (caso raro).
    """
    pp_ids = list({int(l["pp_id"]) for l in lotes if l.get("pp_id")})
    linea_caso_map = get_linea_caso_map(pp_ids)

    grupos: dict[str, dict] = {}
    for lote in lotes:
        pp_id  = lote.get("pp_id")
        pp_nro = lote.get("pp_nro", str(pp_id))

        # ── Formato NUEVO: lote.facturas[] ──────────────────────────────
        facturas_block = lote.get("facturas")
        if isinstance(facturas_block, list) and facturas_block:
            for f in facturas_block:
                marca = f.get("marca") or "SIN_MARCA"
                caso  = f.get("caso")  or "SIN_CASO"
                clave = f"{pp_id}|{marca}|{caso}"
                if clave not in grupos:
                    grupos[clave] = {
                        "pp_id": pp_id, "pp_nro": pp_nro,
                        "marca": marca, "caso": caso,
                        "items": [], "total_pares": 0, "total_neto": 0,
                    }
                for item in f.get("items", []):
                    grupos[clave]["items"].append(item)
                    grupos[clave]["total_pares"] += item.get("pares", 0)
                    grupos[clave]["total_neto"]  += item.get("subtotal", 0)
            continue

        # ── Formato VIEJO: lote.marcas[] ────────────────────────────────
        for marca_data in lote.get("marcas", []):
            marca = marca_data.get("marca", "SIN_MARCA")
            for item in marca_data.get("items", []):
                linea_cod = str(item.get("linea_codigo", "")).strip()
                caso      = linea_caso_map.get(linea_cod) or linea_cod or "SIN_CASO"
                clave = f"{pp_id}|{marca}|{caso}"
                if clave not in grupos:
                    grupos[clave] = {
                        "pp_id": pp_id, "pp_nro": pp_nro,
                        "marca": marca, "caso": caso,
                        "items": [], "total_pares": 0, "total_neto": 0,
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
# RENDER DE UNA CÉLULA = UNA FI YA CREADA por el RPC 028 (camino limpio)
# ─────────────────────────────────────────────────────────────────────────────

def _confirmar_fi_action(fi: dict):
    """Acción 'Confirmar' delegada por render_fi_card."""
    fi_id = int(fi["id"])
    ok, msg = confirmar_fi(fi_id)
    if ok:
        st.success(msg)
        import time; time.sleep(0.5)
        st.rerun()
    else:
        st.error(msg)


def _anular_fi_action(fi: dict):
    """Acción 'Anular' — abre el diálogo de motivo en session_state."""
    fi_id = int(fi["id"])
    st.session_state[f"anular_fi_{fi_id}"] = True
    st.rerun()


def _render_dialogo_anulacion(fi_id: int, key_suffix: str = ""):
    """Diálogo modal-like para capturar el motivo de anulación."""
    flag_key = f"anular_fi_{fi_id}"
    if not st.session_state.get(flag_key):
        return
    motivo = st.text_input(
        "Motivo de anulación",
        key=f"motivo_anul_{fi_id}{key_suffix}",
        placeholder="Ingresá el motivo…",
    )
    col_ok, col_cancel = st.columns([1, 3])
    with col_ok:
        if st.button("Confirmar anulación",
                     key=f"anul_ok_{fi_id}{key_suffix}", type="primary"):
            if not motivo.strip():
                st.warning("Ingresá un motivo para anular.")
            else:
                ok, msg = anular_fi(fi_id, motivo)
                if ok:
                    st.session_state.pop(flag_key, None)
                    st.success(msg)
                    import time; time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(msg)
    with col_cancel:
        if st.button("Cancelar", key=f"anul_cancel_{fi_id}{key_suffix}"):
            st.session_state.pop(flag_key, None)
            st.rerun()


_FI_ACTIONS_RESERVADA = [
    {
        "label": "✅ Confirmar", "key": "conf", "type": "primary",
        "on_click": _confirmar_fi_action, "show_if": "RESERVADA",
    },
    {
        "label": "❌ Anular", "key": "anul",
        "on_click": _anular_fi_action,    "show_if": "RESERVADA",
    },
]


def _render_celula_fi(pedido_id: int, fi: dict):
    """Render canónico (core/fi_card) + acciones específicas del módulo Aprobación."""
    fi_id = int(fi["id"])
    detalles = get_fi_detalles_lite(fi_id)
    render_fi_card(
        fi,
        detalles=detalles,
        actions=_FI_ACTIONS_RESERVADA,
        key_prefix=f"aprob_pvr_{pedido_id}",
        mostrar_descuentos=False,
    )
    _render_dialogo_anulacion(fi_id, key_suffix=f"_pvr{pedido_id}")
    st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# RENDER DE UNA CÉLULA (LEGADO: armada desde payload, pre-028)
# ─────────────────────────────────────────────────────────────────────────────

def _render_celula(pedido_id: int, celula: dict):
    clave    = f"{celula['pp_id']}|{celula['marca']}|{celula['caso']}"
    key_safe = clave.replace("|", "_").replace(" ", "_")

    preventa = get_preventa_de_celula(
        int(celula["pp_id"]), celula["marca"], celula["caso"]
    )

    with st.container():
        col_header, col_estado, col_confirm = st.columns([4, 1, 1])
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
                estado = preventa.get('estado', 'RESERVADA')
                if estado == 'CONFIRMADA':
                    st.success(f"✅ {preventa['nro_factura']}")
                elif estado == 'RESERVADA':
                    st.warning(f"⏳ {preventa['nro_factura']}")
        with col_confirm:
            if preventa and preventa.get('estado') == 'RESERVADA':
                if st.button("✅ Confirmar", key=f"conf_{key_safe}_{pedido_id}", type="primary"):
                    ok, msg = confirmar_fi(preventa['id'])
                    if ok:
                        st.success(msg)
                        import time; time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(msg)

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
        st.caption(
            "Cada célula = una factura interna (PP × Marca × Caso). "
            "El pedido pasa a AUTORIZADO cuando todas las FIs estén CONFIRMADAS."
        )

        # ── Camino limpio: las FIs ya fueron creadas por el RPC 028 ─────
        fis = get_fis_de_pedido(p["id"])
        if fis:
            for fi in fis:
                _render_celula_fi(p["id"], fi)
        else:
            # ── Fallback: pedido viejo (pre-028) que no tiene FIs ──────
            payload = _parse_payload(p.get("payload_json"))
            lotes   = payload.get("lotes", [])
            celulas = construir_celulas(lotes)
            if not celulas:
                st.warning(
                    "⚠️ Este pedido no tiene facturas internas creadas y "
                    "tampoco se pudieron armar células desde el payload. "
                    "Revisar manualmente."
                )
                return
            st.info(
                "🔧 Modo legado: armando células desde payload_json "
                "(este pedido es anterior al RPC 028).",
                icon="ℹ️",
            )
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
    st.caption("Flujo: Aprobar célula → FI RESERVADA → Confirmar individualmente → FI CONFIRMADA")

    tab_pend, tab_res, tab_conf, tab_anul = st.tabs([
        "📋 Pendientes",
        "⏳ Reservadas",
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

    # ── Tab Reservadas: FIs esperando confirmación (formato canónico) ────
    with tab_res:
        fis_reservadas = get_fi_reservadas()
        if not fis_reservadas:
            st.info("No hay facturas reservadas esperando confirmación.", icon="⏳")
        else:
            st.caption(f"{len(fis_reservadas)} factura(s) esperando confirmación individual")
            st.markdown("---")
            for fi in fis_reservadas:
                fi_id = int(fi["id"])
                detalles = get_fi_detalles_lite(fi_id)
                render_fi_card(
                    fi,
                    detalles=detalles,
                    actions=_FI_ACTIONS_RESERVADA,
                    key_prefix="aprob_res",
                    detalle_colapsado=True,
                    mostrar_descuentos=True,
                )
                _render_dialogo_anulacion(fi_id, key_suffix="_res")
                st.markdown("---")

    # ── Tab Confirmadas: historial de FIs aprobadas (formato canónico) ───
    with tab_conf:
        fis = get_fi_confirmadas()
        if not fis:
            st.info("No hay facturas confirmadas aún.")
        else:
            st.caption(f"Últimas {len(fis)} facturas confirmadas")
            st.markdown("---")
            for fi in fis:
                detalles = get_fi_detalles(int(fi["id"]))
                render_fi_card(
                    fi,
                    detalles=detalles,
                    key_prefix="aprob_conf",
                    detalle_colapsado=True,
                    mostrar_descuentos=True,
                )
                st.markdown("---")

    # ── Tab Anuladas: historial de FIs rechazadas (formato canónico) ─────
    with tab_anul:
        fis = get_fi_anuladas()
        if not fis:
            st.info("No hay facturas anuladas.")
        else:
            st.caption(f"Últimas {len(fis)} facturas anuladas")
            st.markdown("---")
            for fi in fis:
                render_fi_card(
                    fi,
                    detalles=None,
                    mostrar_detalle=False,
                    key_prefix="aprob_anul",
                )
                if fi.get("notas"):
                    st.caption(f"📝 Motivo: _{fi['notas']}_")
                st.markdown("---")
