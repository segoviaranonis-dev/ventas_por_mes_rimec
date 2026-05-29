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
from core.ux_celebrate import celebrate_save
from modules.aprobacion_pedidos.logic import (
    get_pedidos_pendientes, get_pedidos_autorizados, get_pedidos_rechazados,
    rechazar_pedido, crear_preventa_desde_celula, get_linea_caso_map,
    get_preventa_de_celula, get_fi_detalles,
    # Lectura de FIs ya creadas por el RPC 028
    get_fis_de_pedido, get_fi_detalles_lite,
    # Flujo Reserva → Liberación
    get_fi_reservadas, get_fi_confirmadas, get_fi_anuladas,
    confirmar_fi, anular_fi,
    # Edición de encabezado
    actualizar_fi_encabezado,
)
from core.database import get_dataframe
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


def _get_plazos() -> list[dict]:
    """Obtiene lista de plazos disponibles."""
    df = get_dataframe("SELECT id_plazo, descp_plazo FROM plazo_v2 ORDER BY id_plazo")
    if df is None or df.empty:
        return []
    return df.to_dict("records")


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
        proforma = lote.get("proforma", "")

        # ── Formato NUEVO: lote.facturas[] ──────────────────────────────
        facturas_block = lote.get("facturas")
        if isinstance(facturas_block, list) and facturas_block:
            for f in facturas_block:
                marca = f.get("marca") or "SIN_MARCA"
                caso  = f.get("caso")  or "SIN_CASO"
                clave = f"{pp_id}|{marca}|{caso}"
                if clave not in grupos:
                    grupos[clave] = {
                        "pp_id": pp_id, "pp_nro": pp_nro, "proforma": proforma,
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
                        "pp_id": pp_id, "pp_nro": pp_nro, "proforma": proforma,
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
        celebrate_save(
            f"Preventa generada: {msg}",
            modulo="Aprobaciones",
            contexto="aprobacion",
            balloons=True,
        )
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

def _ver_pdf_action(fi: dict):
    """Genera y descarga el PDF de la FI individual."""
    fi_id = fi.get("id")
    if not fi_id:
        st.warning("⚠️ Esta FI no tiene ID válido.")
        return

    try:
        from core.pdf_factura_individual import generar_pdf_fi_individual

        with st.spinner("⏳ Generando PDF..."):
            pdf_bytes = generar_pdf_fi_individual(fi_id)

            if pdf_bytes:
                filename = f"FI_{fi.get('nro_factura', 'Factura')}.pdf"
                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                    key=f"download_pdf_{fi_id}"
                )
                st.success("✅ PDF generado exitosamente.")
            else:
                st.error("❌ Error al generar PDF")

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        import traceback
        with st.expander("🔍 Ver detalles técnicos"):
            st.code(traceback.format_exc())


def _confirmar_fi_action(fi: dict):
    """Acción 'Confirmar' delegada por render_fi_card."""
    fi_id = int(fi["id"])
    ok, msg = confirmar_fi(fi_id)
    if ok:
        celebrate_save(msg, modulo="Aprobaciones", contexto="factura_creada", balloons=True)
        import time; time.sleep(0.5)
        # Limpiar cache para forzar refresh de datos
        st.cache_data.clear()
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
                    celebrate_save(
                        msg,
                        modulo="Aprobaciones",
                        contexto="aprobacion",
                        balloons=False,
                    )
                    import time; time.sleep(0.5)
                    # Limpiar cache para forzar refresh de datos
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(msg)
    with col_cancel:
        if st.button("Cancelar", key=f"anul_cancel_{fi_id}{key_suffix}"):
            st.session_state.pop(flag_key, None)
            st.rerun()


def _cambiar_cliente_action(fi: dict):
    """Acción 'Cambiar Cliente' — abre el diálogo de cambio de cliente."""
    st.session_state["dialog_cliente_fi"] = fi


def _editar_items_action(fi: dict):
    """Acción 'Editar Items' — abre el diálogo de edición de items."""
    st.session_state["dialog_items_fi"] = fi


def _editar_descuentos_confirmada_action(fi: dict):
    """Acción 'Editar Descuentos' — abre el diálogo de edición de descuentos."""
    st.session_state["dialog_descuentos_fi"] = fi


# ─────────────────────────────────────────────────────────────────────────────
# CACHE DE QUERIES PESADAS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _get_clientes_cached():
    """Cache de clientes por 5 minutos."""
    df = get_dataframe("SELECT id_cliente, descp_cliente FROM cliente_v2 ORDER BY descp_cliente")
    if df is not None and not df.empty:
        return df
    return None

@st.cache_data(ttl=300)
def _get_plazos_cached():
    """Cache de plazos por 5 minutos."""
    df = get_dataframe("SELECT id_plazo, descp_plazo FROM plazo_v2 ORDER BY id_plazo")
    if df is not None and not df.empty:
        return df
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DIÁLOGOS EMERGENTES (MODALS)
# ─────────────────────────────────────────────────────────────────────────────

@st.dialog("✏️ Editar Descuentos", width="large")
def _dialog_editar_descuentos():
    """Diálogo modal para editar descuentos de una FI CONFIRMADA."""
    fi = st.session_state.get("dialog_descuentos_fi")
    if not fi:
        st.error("Error: No se encontró la factura.")
        return

    fi_id = int(fi["id"])
    nro_factura = fi.get("nro_factura", f"FI {fi_id}")

    st.caption(f"**Factura:** {nro_factura}")
    st.caption("Todos los precios se recalcularán automáticamente según v_stock_rimec")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        lista = st.selectbox(
            "Lista de Precio",
            options=[1, 2, 3, 4],
            format_func=lambda x: ["LPN", "LPC02", "LPC03", "LPC04"][x-1],
            index=(fi.get("lista_precio_id", 1) - 1),
            key=f"dlg_lista_{fi_id}"
        )
        d1 = st.number_input("Descuento 1 (%)", 0.0, 100.0, float(fi.get("descuento_1") or 0), step=0.5, key=f"dlg_d1_{fi_id}")
        d2 = st.number_input("Descuento 2 (%)", 0.0, 100.0, float(fi.get("descuento_2") or 0), step=0.5, key=f"dlg_d2_{fi_id}")

    with col2:
        # Obtener plazos (cacheado)
        plazos = _get_plazos_cached()
        if plazos is not None:
            plazo_actual_id = fi.get("plazo_id", 1)
            plazo_options = plazos["id_plazo"].tolist()
            plazo_labels = plazos["descp_plazo"].tolist()
            try:
                plazo_idx = plazo_options.index(plazo_actual_id)
            except ValueError:
                plazo_idx = 0
            plazo = st.selectbox(
                "Plazo",
                options=plazo_options,
                format_func=lambda x: plazo_labels[plazo_options.index(x)],
                index=plazo_idx,
                key=f"dlg_plazo_{fi_id}"
            )
        else:
            plazo = st.number_input("Plazo ID", value=fi.get("plazo_id", 1), key=f"dlg_plazo_{fi_id}")

        d3 = st.number_input("Descuento 3 (%)", 0.0, 100.0, float(fi.get("descuento_3") or 0), step=0.5, key=f"dlg_d3_{fi_id}")
        d4 = st.number_input("Descuento 4 (%)", 0.0, 100.0, float(fi.get("descuento_4") or 0), step=0.5, key=f"dlg_d4_{fi_id}")

    st.divider()
    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
            from .logic import editar_descuentos_fi_confirmada
            ok, msg = editar_descuentos_fi_confirmada(
                fi_id=fi_id,
                lista_precio_id=int(lista),
                descuento_1=float(d1),
                descuento_2=float(d2),
                descuento_3=float(d3),
                descuento_4=float(d4),
                plazo_id=int(plazo)
            )
            if ok:
                st.session_state.pop("dialog_descuentos_fi", None)
                celebrate_save(msg, emoji="✅", modulo="Aprobaciones")
                st.rerun()
            else:
                st.error(f"❌ {msg}")

    with col_btn2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.pop("dialog_descuentos_fi", None)
            st.rerun()


@st.dialog("👤 Cambiar Cliente", width="large")
def _dialog_cambiar_cliente():
    """Diálogo modal para cambiar el cliente de una FI."""
    fi = st.session_state.get("dialog_cliente_fi")
    if not fi:
        st.error("Error: No se encontró la factura.")
        return

    fi_id = int(fi["id"])
    nro_factura = fi.get("nro_factura", f"FI {fi_id}")
    cliente_actual_id = fi.get("cliente_id")

    st.caption(f"**Factura:** {nro_factura}")
    st.info(f"**Cliente actual:** {fi.get('cliente_nombre', 'N/A')}")
    st.divider()

    # Obtener clientes (cacheado)
    clientes = _get_clientes_cached()
    if clientes is None:
        st.error("No se pudieron cargar los clientes.")
        return

    cliente_options = clientes["id_cliente"].tolist()
    cliente_labels = clientes["descp_cliente"].tolist()

    # Buscar índice del cliente actual
    try:
        cliente_idx = cliente_options.index(cliente_actual_id) if cliente_actual_id else 0
    except ValueError:
        cliente_idx = 0

    nuevo_cliente = st.selectbox(
        "Seleccionar Nuevo Cliente",
        options=cliente_options,
        format_func=lambda x: f"{cliente_labels[cliente_options.index(x)]}",
        index=cliente_idx,
        key=f"dlg_new_client_{fi_id}"
    )

    st.divider()
    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if st.button("💾 Cambiar Cliente", type="primary", use_container_width=True):
            if nuevo_cliente == cliente_actual_id:
                st.warning("⚠️ Seleccionaste el mismo cliente.")
            else:
                from .logic import cambiar_cliente_fi
                ok, msg = cambiar_cliente_fi(fi_id=fi_id, nuevo_cliente_id=nuevo_cliente)
                if ok:
                    st.session_state.pop("dialog_cliente_fi", None)
                    celebrate_save(msg, emoji="✅", modulo="Aprobaciones")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    with col_btn2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.pop("dialog_cliente_fi", None)
            st.rerun()


@st.dialog("📦 Editar Items", width="large")
def _dialog_editar_items():
    """Diálogo modal para editar items de una FI."""
    fi = st.session_state.get("dialog_items_fi")
    if not fi:
        st.error("Error: No se encontró la factura.")
        return

    fi_id = int(fi["id"])
    nro_factura = fi.get("nro_factura", f"FI {fi_id}")

    st.caption(f"**Factura:** {nro_factura}")
    st.caption("Modifica cantidades o elimina items (los totales se recalcularán automáticamente)")
    st.divider()

    # Obtener items actuales
    from .logic import get_fi_detalles
    detalles = get_fi_detalles(fi_id)

    if not detalles:
        st.warning("Esta FI no tiene items.")
        return

    for idx, item in enumerate(detalles):
        item_id = int(item["id"])

        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

        with col1:
            st.markdown(f"**{item['linea_codigo']}-{item['ref_codigo']}**")
            st.caption(f"{item['color_nombre']} • {item['gradas_fmt']}")

        with col2:
            new_cajas = st.number_input(
                "Cajas",
                min_value=0,
                value=int(item.get("cajas", 0)),
                key=f"dlg_cajas_{item_id}_{idx}",
                label_visibility="collapsed"
            )

        with col3:
            new_pares = st.number_input(
                "Pares",
                min_value=1,
                value=int(item.get("pares", 1)),
                key=f"dlg_pares_{item_id}_{idx}",
                label_visibility="collapsed"
            )

        with col4:
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("💾", key=f"dlg_save_{item_id}_{idx}", help="Guardar cambios"):
                    if new_pares != item.get("pares") or new_cajas != item.get("cajas"):
                        from .logic import modificar_cantidad_item_fi
                        ok, msg = modificar_cantidad_item_fi(item_id, new_cajas, new_pares)
                        if ok:
                            celebrate_save(msg, emoji="✅", modulo="Aprobaciones")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
            with col_btn2:
                if st.button("🗑️", key=f"dlg_del_{item_id}_{idx}", help="Eliminar item"):
                    if len(detalles) <= 1:
                        st.error("No puedes eliminar el único item. Anula la FI completa.")
                    else:
                        from .logic import eliminar_item_fi
                        ok, msg = eliminar_item_fi(item_id)
                        if ok:
                            celebrate_save(msg, emoji="🗑️", modulo="Aprobaciones")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")

        st.markdown("---")

    st.divider()
    if st.button("✅ Cerrar", type="primary", use_container_width=True):
        st.session_state.pop("dialog_items_fi", None)
        st.rerun()


# ── Acciones disponibles por estado ────────────────────────────────────────

_FI_ACTIONS_RESERVADA = [
    {
        "label": "📄 Ver PDF", "key": "pdf",
        "on_click": _ver_pdf_action, "show_if": "RESERVADA",
    },
    {
        "label": "✅ Confirmar", "key": "conf", "type": "primary",
        "on_click": _confirmar_fi_action, "show_if": "RESERVADA",
    },
    {
        "label": "👤 Cliente", "key": "change_client",
        "on_click": _cambiar_cliente_action, "show_if": "RESERVADA",
    },
    {
        "label": "📦 Items", "key": "edit_items",
        "on_click": _editar_items_action, "show_if": "RESERVADA",
    },
    {
        "label": "❌ Anular", "key": "anul",
        "on_click": _anular_fi_action, "show_if": "RESERVADA",
    },
]

_FI_ACTIONS_CONFIRMADA = [
    {
        "label": "📄 Ver PDF", "key": "pdf",
        "on_click": _ver_pdf_action, "show_if": "CONFIRMADA",
    },
    {
        "label": "✏️ Descuentos", "key": "edit_desc",
        "on_click": _editar_descuentos_confirmada_action, "show_if": "CONFIRMADA",
    },
    {
        "label": "👤 Cliente", "key": "change_client",
        "on_click": _cambiar_cliente_action, "show_if": "CONFIRMADA",
    },
    {
        "label": "📦 Items", "key": "edit_items",
        "on_click": _editar_items_action, "show_if": "CONFIRMADA",
    },
]


def _render_celula_fi(pedido_id: int, fi: dict):
    """Render canónico (core/fi_card) + acciones específicas del módulo Aprobación."""
    fi_id = int(fi["id"])
    estado = (fi.get("estado") or "").upper()
    detalles = get_fi_detalles_lite(fi_id)

    # Callback para actualizar encabezado
    def on_actualizar_callback(fi_id, lista_precio_id, desc1, desc2, desc3, desc4, plazo_id):
        ok, msg = actualizar_fi_encabezado(
            fi_id, lista_precio_id, desc1, desc2, desc3, desc4, plazo_id
        )
        if ok:
            celebrate_save(
                msg,
                modulo="Aprobaciones",
                contexto="fi_actualizada",
                balloons=False,
            )
            import time; time.sleep(0.5)
            st.rerun()
        else:
            st.error(f"❌ {msg}")

    # Obtener plazos disponibles
    plazos = _get_plazos()

    render_fi_card(
        fi,
        detalles=detalles,
        actions=_FI_ACTIONS_RESERVADA,
        key_prefix=f"aprob_pvr_{pedido_id}",
        mostrar_descuentos=True,
        modo_edicion=(estado == "RESERVADA"),
        on_actualizar=on_actualizar_callback,
        plazos_disponibles=plazos,
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
            # Matrimonio PP + Proforma
            pp_display = celula['pp_nro']
            if celula.get('proforma'):
                pp_display = f"{pp_display} ({celula['proforma']})"

            st.markdown(
                f"📦 **{pp_display}** · "
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
                        celebrate_save(
                            msg,
                            modulo="Aprobaciones",
                            contexto="factura_creada",
                            balloons=True,
                        )
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
    # Header con botón de refresh
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("## ✅ Aprobación de Pedidos RIMEC")
        st.caption("Flujo: Aprobar célula → FI RESERVADA → Confirmar individualmente → FI CONFIRMADA")
    with col2:
        if st.button("🔄 Refrescar", use_container_width=True, help="Recargar pedidos sin perder sesión"):
            st.cache_data.clear()
            st.rerun()

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
                # NO cargar detalles aquí (lazy loading)
                render_fi_card(
                    fi,
                    detalles=None,  # ⚡ CRÍTICO: No cargar hasta que usuario lo pida
                    actions=_FI_ACTIONS_RESERVADA,
                    key_prefix="aprob_res",
                    detalle_colapsado=True,
                    mostrar_descuentos=True,
                    mostrar_detalle=False,  # ⚡ No mostrar items en listado
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

            from .ui_fast import (
                render_editar_descuentos_inline,
                render_cambiar_cliente_inline,
                render_editar_items_inline
            )

            for fi in fis:
                fi_id = int(fi["id"])
                nro_factura = fi.get("nro_factura", f"FI {fi_id}")

                # Mostrar tarjeta básica SIN botones de acción
                render_fi_card(
                    fi,
                    detalles=None,
                    actions=None,  # ⚡ Sin botones, usamos expanders abajo
                    key_prefix="aprob_conf",
                    detalle_colapsado=True,
                    mostrar_descuentos=True,
                    mostrar_detalle=False,
                )

                # Expanders de edición DIRECTOS (se abren instantáneamente)
                # Fila 1: Acciones rápidas (compactas)
                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("📄 Ver PDF", key=f"pdf_conf_{fi_id}", use_container_width=True):
                        _ver_pdf_action(fi)

                with col2:
                    with st.expander("✏️ Descuentos", expanded=False):
                        render_editar_descuentos_inline(fi)

                with col3:
                    with st.expander("👤 Cliente", expanded=False):
                        render_cambiar_cliente_inline(fi)

                # Fila 2: Items (necesita más espacio por su contenido extenso)
                with st.expander("📦 Items - Editar Cantidades", expanded=False):
                    render_editar_items_inline(fi)

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

