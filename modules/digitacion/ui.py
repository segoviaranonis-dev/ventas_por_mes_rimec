"""
DIGITACIÓN — ui.py
Bandeja del operador logístico.
Vista: PENDIENTES (ICs sin asignar) + EN PROCESO (PPs abiertos).
"""

import streamlit as st
from modules.digitacion.logic import (
    get_ics_pendientes,
    get_pps_abiertos,
    get_ics_de_pp,
    get_eventos_cerrados,
    crear_pp_digitacion,
    asignar_ic,
    cerrar_pp,
    devolver_ic,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _seccion(titulo: str, subtitulo: str = ""):
    st.markdown(
        f"<div style='margin-top:24px;margin-bottom:6px;'>"
        f"<span style='color:#D4AF37;font-weight:700;font-size:1rem;'>{titulo}</span>"
        f"<span style='color:#64748B;font-size:0.8rem;margin-left:8px;'>{subtitulo}</span>"
        f"</div>",
        unsafe_allow_html=True
    )


def _metrica_pendientes(n: int):
    color = "#EF4444" if n > 0 else "#10B981"
    st.markdown(
        f"<div style='background:#1e293b;border-left:4px solid {color};"
        f"padding:16px 24px;border-radius:8px;margin-bottom:20px;'>"
        f"<div style='color:#94a3b8;font-size:0.72rem;text-transform:uppercase;"
        f"letter-spacing:.08em;'>ICs pendientes de procesar</div>"
        f"<div style='color:{color};font-size:2.4rem;font-weight:800;line-height:1;'>{n}</div>"
        f"</div>",
        unsafe_allow_html=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# BANDEJA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def _render_bandeja():
    df_pend = get_ics_pendientes()
    df_pps  = get_pps_abiertos()

    n_pend = len(df_pend) if df_pend is not None and not df_pend.empty else 0
    _metrica_pendientes(n_pend)

    # ── PENDIENTES ────────────────────────────────────────────────────────────
    _seccion("PENDIENTES", "ICs autorizadas sin número de fábrica asignado")

    if n_pend == 0:
        st.success("✅ No hay ICs pendientes. Bandeja limpia.")
    else:
        for _, row in df_pend.iterrows():
            ic_id = int(row["id"])
            eta   = str(row.get("eta", "—"))[:10] if row.get("eta") else "—"
            evento = row.get("evento_precio") or "Sin evento"

            col_info, col_asig, col_dev = st.columns([5, 1.2, 1.2])
            col_info.markdown(
                f"**{row['nro_ic']}** · {row['marca']} · {row['categoria']} · "
                f"ETA: {eta} · {int(row['pares']):,} pares · 📋 {evento}"
            )
            if col_asig.button("Asignar →", key=f"asig_{ic_id}", type="primary",
                               use_container_width=True):
                st.session_state["dg_ic_id"]  = ic_id
                st.session_state["dg_ic_data"] = row.to_dict()
                st.session_state["dg_vista"]   = "asignacion"
                st.rerun()

            if col_dev.button("← Devolver", key=f"dev_{ic_id}", type="secondary",
                              use_container_width=True):
                st.session_state[f"devolviendo_{ic_id}"] = True
                st.rerun()

            # Panel de devolución — aparece al presionar ← Devolver
            if st.session_state.get(f"devolviendo_{ic_id}"):
                with st.container():
                    st.warning(f"Devolver **{row['nro_ic']}** a Administración")
                    motivo = st.text_area(
                        "Motivo de devolución (obligatorio)",
                        key=f"motivo_{ic_id}",
                        placeholder="Ej: Línea 1122 descontinuada por fábrica. "
                                    "Solicitar reducción de cantidad o cancelación.",
                    )
                    col_conf, col_canc = st.columns(2)
                    if col_conf.button("Confirmar devolución", key=f"conf_dev_{ic_id}",
                                      type="primary", disabled=not motivo.strip()):
                        if devolver_ic(ic_id, motivo):
                            st.session_state.pop(f"devolviendo_{ic_id}", None)
                            st.rerun()
                        else:
                            st.error("Error al devolver. Revisá los logs.")
                    if col_canc.button("Cancelar", key=f"canc_dev_{ic_id}"):
                        st.session_state.pop(f"devolviendo_{ic_id}", None)
                        st.rerun()

    st.markdown("---")

    # ── EN PROCESO ────────────────────────────────────────────────────────────
    _seccion("EN PROCESO", "Pedidos Proveedor abiertos — cerrar requiere número de factura")

    if df_pps is None or df_pps.empty:
        st.info("No hay PPs abiertos en este momento.")
    else:
        for _, pp in df_pps.iterrows():
            n_ics = int(pp.get("ics_asignadas", 0))
            with st.expander(
                f"📦 **{pp['nro_pp']}** · {n_ics} IC(s) · "
                f"Factura: {pp.get('factura') or 'pendiente'}"
            ):
                df_ics = get_ics_de_pp(int(pp["id"]))
                if df_ics is not None and not df_ics.empty:
                    st.dataframe(
                        df_ics.rename(columns={
                            "nro_ic": "IC", "marca": "Marca",
                            "nro_pedido_fabrica": "Nro. Fábrica",
                            "evento_precio": "Evento Precio"
                        }),
                        use_container_width=True, hide_index=True
                    )

                st.markdown("**Cerrar este Pedido Proveedor:**")
                col_fac, col_btn = st.columns([3, 1])
                nro_fac = col_fac.text_input(
                    "Nro. Factura de importación",
                    key=f"fac_{pp['id']}",
                    placeholder="Ej: FAC-2026-00123"
                )
                if col_btn.button("🔒 Cerrar PP", key=f"cerrar_{pp['id']}", type="primary"):
                    if not nro_fac.strip():
                        st.error("La factura de importación es obligatoria para cerrar.")
                    else:
                        ok = cerrar_pp(int(pp["id"]), nro_fac)
                        if ok:
                            st.success(f"✅ PP {pp['nro_pp']} cerrado. Pasa a Compra Legal.")
                            st.rerun()
                        else:
                            st.error("Error al cerrar el PP. Revisá los logs.")


# ─────────────────────────────────────────────────────────────────────────────
# VISTA DE ASIGNACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def _render_asignacion():
    ic      = st.session_state.get("dg_ic_data", {})
    ic_id   = st.session_state.get("dg_ic_id")

    if st.button("← Volver a Bandeja"):
        st.session_state["dg_vista"] = "bandeja"
        st.rerun()

    # Cabecera IC
    st.markdown(
        f"<div style='background:#1e293b;border-left:4px solid #D4AF37;"
        f"padding:14px 20px;border-radius:6px;margin-bottom:20px;'>"
        f"<div style='color:#94a3b8;font-size:0.72rem;text-transform:uppercase;'>Intención de Compra</div>"
        f"<div style='color:#f1f5f9;font-size:1.2rem;font-weight:700;'>"
        f"{ic.get('nro_ic','—')} &nbsp;·&nbsp; {ic.get('marca','—')} &nbsp;·&nbsp; {ic.get('categoria','—')}"
        f"</div>"
        f"<div style='color:#64748b;font-size:0.78rem;margin-top:4px;'>"
        f"ETA: {str(ic.get('eta','—'))[:10]} &nbsp;·&nbsp; {int(ic.get('pares',0)):,} pares"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True
    )

    # Selector de evento de precio
    df_eventos = get_eventos_cerrados()
    if df_eventos is None or df_eventos.empty:
        st.error("No hay eventos de precio cerrados. Cerrá un listado antes de digitalizar.")
        return

    opciones_ev = {
        f"{row['nombre_evento']} ({str(row.get('fecha_vigencia_desde',''))[:10]})": int(row["id"])
        for _, row in df_eventos.iterrows()
    }

    # Pre-seleccionar el evento ya asignado a la IC si existe
    ev_actual = ic.get("precio_evento_id")
    idx_default = 0
    if ev_actual:
        ids_list = list(opciones_ev.values())
        if int(ev_actual) in ids_list:
            idx_default = ids_list.index(int(ev_actual))

    evento_label = st.selectbox(
        "Evento de precio (listado de precios)",
        list(opciones_ev.keys()),
        index=idx_default
    )
    precio_evento_id = opciones_ev[evento_label]

    # Número de fábrica
    nro_fabrica = st.text_input(
        "Nro. de Pedido Fábrica (Beira Rio)",
        placeholder="Ej: 112233"
    )

    # Asignación a PP
    st.markdown("**Asignar a Pedido Proveedor:**")
    df_pps = get_pps_abiertos()

    opciones_pp = {}
    if df_pps is not None and not df_pps.empty:
        for _, pp in df_pps.iterrows():
            n = int(pp.get("ics_asignadas", 0))
            opciones_pp[f"{pp['nro_pp']} ({n} ICs asignadas)"] = int(pp["id"])

    modo = st.radio(
        "Destino:",
        ["PP existente", "Crear PP nuevo"] if opciones_pp else ["Crear PP nuevo"],
        horizontal=True
    )

    pp_id_seleccionado = None
    if modo == "PP existente" and opciones_pp:
        pp_label = st.selectbox("Seleccionar PP abierto", list(opciones_pp.keys()))
        pp_id_seleccionado = opciones_pp[pp_label]
    else:
        st.info("Se creará un nuevo Pedido Proveedor automáticamente.")

    st.markdown("---")
    col_cancel, col_ok = st.columns([1, 2])

    if col_cancel.button("✕ Cancelar"):
        st.session_state["dg_vista"] = "bandeja"
        st.rerun()

    if col_ok.button("✅ Asignar →", type="primary"):
        if not nro_fabrica.strip():
            st.error("El número de pedido de fábrica es obligatorio.")
        else:
            # Crear PP nuevo si hace falta
            pp_id = pp_id_seleccionado
            if pp_id is None:
                pp_id = crear_pp_digitacion()
                if not pp_id:
                    st.error("Error al crear el PP. Revisá los logs.")
                    return

            ok = asignar_ic(
                ic_id=ic_id,
                pp_id=pp_id,
                nro_pedido_fabrica=nro_fabrica,
                precio_evento_id=precio_evento_id,
            )
            if ok:
                st.success(f"✅ IC asignada correctamente al PP.")
                st.session_state["dg_vista"] = "bandeja"
                st.rerun()
            else:
                st.error("Error al asignar. Revisá los logs o si la IC ya está asignada.")


# ─────────────────────────────────────────────────────────────────────────────
# RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_digitacion():
    st.markdown("## ⌨️ Digitación")
    st.markdown("---")

    vista = st.session_state.get("dg_vista", "bandeja")

    if vista == "bandeja":
        _render_bandeja()
    elif vista == "asignacion":
        _render_asignacion()
