# VERSIÓN RÁPIDA - Sin @st.dialog, usa containers inline
# Esta versión renderiza los formularios directamente sin rerun

import streamlit as st
from core.ux_celebrate import celebrate_save
from core.database import get_dataframe

# Cache de datos
@st.cache_data(ttl=300)
def get_clientes_fast():
    df = get_dataframe("SELECT id_cliente, descp_cliente FROM cliente_v2 ORDER BY descp_cliente")
    return df if df is not None and not df.empty else None

@st.cache_data(ttl=300)
def get_plazos_fast():
    df = get_dataframe("SELECT id_plazo, descp_plazo FROM plazo_v2 ORDER BY id_plazo")
    return df if df is not None and not df.empty else None


def render_editar_descuentos_inline(fi: dict):
    """Renderiza formulario de descuentos inline - RÁPIDO."""
    fi_id = int(fi["id"])
    nro_factura = fi.get("nro_factura", f"FI {fi_id}")

    # Container visual destacado
    with st.container():
        st.markdown(f"""
        <div class="nx-editor-header">
            <h3>✏️ Editar descuentos: {nro_factura}</h3>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            lista = st.selectbox(
                "Lista de Precio",
                options=[1, 2, 3, 4],
                format_func=lambda x: ["LPN", "LPC02", "LPC03", "LPC04"][x-1],
                index=(fi.get("lista_precio_id", 1) - 1),
                key=f"fast_lista_{fi_id}"
            )
            d1 = st.number_input("Desc 1 (%)", 0.0, 100.0, float(fi.get("descuento_1") or 0), step=0.5, key=f"fast_d1_{fi_id}")
            d2 = st.number_input("Desc 2 (%)", 0.0, 100.0, float(fi.get("descuento_2") or 0), step=0.5, key=f"fast_d2_{fi_id}")

        with col2:
            plazos = get_plazos_fast()
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
                    key=f"fast_plazo_{fi_id}"
                )
            else:
                plazo = st.number_input("Plazo ID", value=fi.get("plazo_id", 1), key=f"fast_plazo_{fi_id}")

            d3 = st.number_input("Desc 3 (%)", 0.0, 100.0, float(fi.get("descuento_3") or 0), step=0.5, key=f"fast_d3_{fi_id}")
            d4 = st.number_input("Desc 4 (%)", 0.0, 100.0, float(fi.get("descuento_4") or 0), step=0.5, key=f"fast_d4_{fi_id}")

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("💾 Guardar", type="primary", use_container_width=True, key=f"fast_save_desc_{fi_id}"):
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
                    celebrate_save(msg, emoji="✅")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

        with col_btn2:
            if st.button("❌ Cancelar", use_container_width=True, key=f"fast_cancel_desc_{fi_id}"):
                st.session_state.pop("dialog_descuentos_fi", None)
                st.rerun()

        st.markdown("---")


def render_cambiar_cliente_inline(fi: dict):
    """Renderiza formulario de cambio de cliente inline - RÁPIDO."""
    fi_id = int(fi["id"])
    nro_factura = fi.get("nro_factura", f"FI {fi_id}")
    cliente_actual_id = fi.get("cliente_id")

    with st.container():
        st.markdown(f"""
        <div class="nx-editor-header">
            <h3>👤 Cambiar cliente: {nro_factura}</h3>
        </div>
        """, unsafe_allow_html=True)

        st.info(f"**Cliente actual:** {fi.get('cliente_nombre', 'N/A')}")

        clientes = get_clientes_fast()
        if clientes is None:
            st.error("No se pudieron cargar los clientes.")
            return

        cliente_options = clientes["id_cliente"].tolist()
        cliente_labels = clientes["descp_cliente"].tolist()

        try:
            cliente_idx = cliente_options.index(cliente_actual_id) if cliente_actual_id else 0
        except ValueError:
            cliente_idx = 0

        nuevo_cliente = st.selectbox(
            "Nuevo Cliente",
            options=cliente_options,
            format_func=lambda x: cliente_labels[cliente_options.index(x)],
            index=cliente_idx,
            key=f"fast_cliente_{fi_id}"
        )

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("💾 Cambiar", type="primary", use_container_width=True, key=f"fast_save_cli_{fi_id}"):
                if nuevo_cliente == cliente_actual_id:
                    st.warning("⚠️ Mismo cliente seleccionado.")
                else:
                    from .logic import cambiar_cliente_fi
                    ok, msg = cambiar_cliente_fi(fi_id=fi_id, nuevo_cliente_id=nuevo_cliente)
                    if ok:
                        st.session_state.pop("dialog_cliente_fi", None)
                        celebrate_save(msg, emoji="✅")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        with col_btn2:
            if st.button("❌ Cancelar", use_container_width=True, key=f"fast_cancel_cli_{fi_id}"):
                st.session_state.pop("dialog_cliente_fi", None)
                st.rerun()

        st.markdown("---")


def render_editar_items_inline(fi: dict):
    """Renderiza formulario de items inline - RÁPIDO."""
    fi_id = int(fi["id"])
    nro_factura = fi.get("nro_factura", f"FI {fi_id}")

    with st.container():
        st.markdown(f"""
        <div class="nx-editor-header">
            <h3>📦 Editar items: {nro_factura}</h3>
        </div>
        """, unsafe_allow_html=True)

        from .logic import get_fi_detalles
        detalles = get_fi_detalles(fi_id)

        if not detalles:
            st.warning("Esta FI no tiene items.")
            return

        for idx, item in enumerate(detalles):
            item_id = int(item["id"])

            # Parsear linea_snapshot
            snap = item.get("linea_snapshot", {})
            if not isinstance(snap, dict):
                snap = {}

            linea_codigo = snap.get("linea_codigo", "?")
            ref_codigo = snap.get("ref_codigo", "?")
            color_nombre = snap.get("color_nombre", "?")
            gradas_fmt = snap.get("gradas_fmt", "")

            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

            with col1:
                st.markdown(f"**{linea_codigo}-{ref_codigo}**")
                st.caption(f"{color_nombre} • {gradas_fmt}")

            with col2:
                new_cajas = st.number_input(
                    "Cajas",
                    min_value=0,
                    value=int(item.get("cajas", 0)),
                    key=f"fast_cajas_{item_id}_{idx}",
                    label_visibility="collapsed"
                )

            with col3:
                # Calcular pares automáticamente desde cajas × pares_por_caja
                from .logic import _calcular_pares_por_caja_desde_snapshot
                linea_snapshot = item.get("linea_snapshot", {})
                pares_por_caja = _calcular_pares_por_caja_desde_snapshot(linea_snapshot)
                new_pares = new_cajas * pares_por_caja

                # Mostrar pares calculados sin estado persistente.
                # Estilos inline para blindar contraste ante modo claro/oscuro del navegador.
                st.markdown(
                    f"""
                    <div style="
                        background:#111827;
                        border:1px solid rgba(212,175,55,.45);
                        border-radius:10px;
                        padding:8px 12px;
                        text-align:center;
                        min-height:54px;
                        box-shadow:inset 0 1px 0 rgba(255,255,255,.05), 0 6px 16px rgba(0,0,0,.18);
                    ">
                        <div style="
                            font-size:.64rem;
                            color:#CBD5E1;
                            text-transform:uppercase;
                            letter-spacing:.08em;
                            font-weight:800;
                        ">Pares</div>
                        <div style="
                            font-size:1.35rem;
                            font-weight:900;
                            color:#FFFFFF;
                            line-height:1.15;
                            font-variant-numeric:tabular-nums;
                        ">{new_pares}</div>
                        <div style="
                            font-size:.70rem;
                            color:#D4AF37;
                            margin-top:3px;
                            font-weight:700;
                        ">{new_cajas} × {pares_por_caja} = {new_pares}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col4:
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾", key=f"fast_save_item_{item_id}_{idx}"):
                        if new_pares != item.get("pares") or new_cajas != item.get("cajas"):
                            from .logic import modificar_cantidad_item_fi
                            ok, msg = modificar_cantidad_item_fi(item_id, new_cajas, new_pares)
                            if ok:
                                celebrate_save(msg, emoji="✅")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
                with col_btn2:
                    if st.button("🗑️", key=f"fast_del_item_{item_id}_{idx}"):
                        if len(detalles) <= 1:
                            st.error("No puedes eliminar el único item.")
                        else:
                            from .logic import eliminar_item_fi
                            ok, msg = eliminar_item_fi(item_id)
                            if ok:
                                celebrate_save(msg, emoji="🗑️")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")

            st.markdown("---")

        if st.button("✅ Cerrar", type="primary", use_container_width=True, key=f"fast_close_items_{fi_id}"):
            st.session_state.pop("dialog_items_fi", None)
            st.rerun()
