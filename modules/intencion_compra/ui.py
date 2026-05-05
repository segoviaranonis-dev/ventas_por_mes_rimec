# =============================================================================
# MÓDULO: Intención de Compra
# ARCHIVO: modules/intencion_compra/ui.py
# DESCRIPCIÓN: UI V3 — bandeja de tarjetas editables + historial.
#
#  Flujo:
#    Dashboard (tabs PENDIENTES / HISTORIAL)
#    → Nueva IC: Paso A (tipo+categoría) → Paso B (formulario)
#
#  PROHIBIDO en este módulo: material, color, línea, referencia, proforma.
#  Solo cabecera financiera.
# =============================================================================

import streamlit as st
import pandas as pd
from datetime import date

from modules.intencion_compra.logic import (
    get_proveedores, get_vendedores, get_marcas, get_plazos,
    get_tipos, get_categorias,
    buscar_cliente, get_eventos_precio_cerrados,
    get_ics_pendientes, get_ics_historial, get_ics_devueltas,
    update_campo_ic, autorizar_ic, eliminar_ic, reutorizar_ic, anular_ic,
    calcular_neto, save_intencion,
    get_lineas_con_caso, get_listados_para_caso, get_comisiones,
    # Preventa
    get_pps_para_preventa, get_marcas_del_pp,
    cargar_stock_preventa_pp, crear_ic_preventa,
)
from modules.rimec_engine.hiedra import extraer_valor_numerico_talla

# IDs de categoria_v2: 2=COMPRA PREVIA, 3=PROGRAMADO
_ID_COMPRA_PREVIA = 2
_ID_PROGRAMADO    = 3

VISTA_DASHBOARD = "dashboard"
VISTA_PASO_A    = "paso_a"
VISTA_FORM      = "form"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _opts(df: pd.DataFrame, id_col: str, label_col: str) -> dict:
    return {row[label_col]: row[id_col] for _, row in df.iterrows()}


def _fmt_gs(v) -> str:
    try:
        return f"Gs. {float(v):,.0f}"
    except Exception:
        return "Gs. 0"


def _go(vista: str) -> None:
    st.session_state["ic_vista"] = vista
    st.rerun()


def _idx(opts: dict, current_id) -> int:
    """Índice del valor actual en un dict {label: id}."""
    ids = list(opts.values())
    try:
        return ids.index(current_id)
    except (ValueError, TypeError):
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACKS on_change — guardado automático
# ─────────────────────────────────────────────────────────────────────────────

def _cb_select(ic_id: int, campo: str, key: str, opts: dict):
    """on_change para selectboxes: convierte label → id y guarda."""
    label = st.session_state.get(key)
    valor = opts.get(label)
    update_campo_ic(ic_id, campo, valor)


def _cb_valor(ic_id: int, campo: str, key: str):
    """on_change para text_input, number_input, date_input."""
    valor = st.session_state.get(key)
    if isinstance(valor, date):
        valor = str(valor)
    update_campo_ic(ic_id, campo, valor)


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGOS COMPARTIDOS (cargados una vez por render)
# ─────────────────────────────────────────────────────────────────────────────

def _cargar_catalogos() -> dict:
    df_tipos  = get_tipos()
    df_cats   = get_categorias()
    df_marcas = get_marcas()
    df_evs    = get_eventos_precio_cerrados()

    opts_tipos  = {r["descp_tipo"]:      int(r["id_tipo"])      for _, r in df_tipos.iterrows()}
    opts_cats   = {r["descp_categoria"]: int(r["id_categoria"]) for _, r in df_cats.iterrows()}
    opts_marcas = {r["descp_marca"]:     int(r["id_marca"])     for _, r in df_marcas.iterrows()}

    opts_evs = {"— Sin vincular —": None}
    if df_evs is not None and not df_evs.empty:
        for _, ev in df_evs.iterrows():
            lbl = f"{ev['nombre_evento']}  ·  {str(ev['fecha_vigencia_desde'])[:10]}"
            opts_evs[lbl] = int(ev["id"])

    return {
        "tipos":  opts_tipos,
        "cats":   opts_cats,
        "marcas": opts_marcas,
        "evs":    opts_evs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TARJETA IC EDITABLE
# ─────────────────────────────────────────────────────────────────────────────

def _render_tarjeta(ic: dict, cats: dict, tipos: dict, marcas: dict, evs: dict):
    ic_id   = int(ic["id"])
    nro     = ic["numero_registro"]
    cliente = str(ic.get("cliente") or "—")
    vendedor= str(ic.get("vendedor") or "—")
    proveedor = str(ic.get("proveedor") or "—")

    # ── encabezado ───────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:16px;margin-bottom:8px;"
        f"background:#0F1E2F;border-radius:8px;padding:8px 14px;'>"
        f"<span style='color:#D4AF37;font-weight:700;font-size:0.95rem;'>{nro}</span>"
        f"<span style='color:#64748B;font-size:.75rem;'>|</span>"
        f"<span style='color:#64748B;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;'>Cliente</span>"
        f"<span style='color:#F1F5F9;font-size:.85rem;font-weight:600;'>{cliente}</span>"
        f"<span style='color:#64748B;font-size:.75rem;'>|</span>"
        f"<span style='color:#64748B;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;'>Vendedor</span>"
        f"<span style='color:#F1F5F9;font-size:.85rem;font-weight:600;'>{vendedor}</span>"
        f"<span style='color:#64748B;font-size:.75rem;'>|</span>"
        f"<span style='color:#64748B;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;'>Proveedor</span>"
        f"<span style='color:#94A3B8;font-size:.82rem;'>{proveedor}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── FILA 1: Tipo · Categoría · Marca · ETA · Pares · Monto Neto ─────────
    c1, c2, c3, c4, c5, c6 = st.columns([1.4, 1.4, 1.8, 1.4, 1, 1.6])

    key_tipo = f"tp_{ic_id}"
    c1.selectbox(
        "Tipo", list(tipos.keys()),
        index=_idx(tipos, ic.get("tipo_id")),
        key=key_tipo,
        on_change=_cb_select, args=(ic_id, "tipo_id", key_tipo, tipos),
        label_visibility="visible",
    )

    key_cat = f"cat_{ic_id}"
    c2.selectbox(
        "Categoría", list(cats.keys()),
        index=_idx(cats, ic.get("categoria_id")),
        key=key_cat,
        on_change=_cb_select, args=(ic_id, "categoria_id", key_cat, cats),
    )

    key_marc = f"marc_{ic_id}"
    c3.selectbox(
        "Marca", list(marcas.keys()),
        index=_idx(marcas, ic.get("id_marca")),
        key=key_marc,
        on_change=_cb_select, args=(ic_id, "id_marca", key_marc, marcas),
    )

    eta_val = None
    try:
        raw = ic.get("fecha_llegada")
        if raw and str(raw) not in ("None", "nan", "NaT"):
            eta_val = pd.to_datetime(raw).date()
    except Exception:
        pass
    key_eta = f"eta_{ic_id}"
    c4.date_input(
        "ETA", value=eta_val,
        key=key_eta,
        on_change=_cb_valor, args=(ic_id, "fecha_llegada", key_eta),
    )

    key_pares = f"par_{ic_id}"
    c5.number_input(
        "Pares", min_value=0, step=12,
        value=int(ic.get("pares") or 0),
        key=key_pares,
        on_change=_cb_valor, args=(ic_id, "cantidad_total_pares", key_pares),
    )

    key_neto = f"neto_{ic_id}"
    c6.number_input(
        "Monto Neto (Gs.)", min_value=0.0, step=100_000.0, format="%.0f",
        value=float(ic.get("monto_neto") or 0),
        key=key_neto,
        on_change=_cb_valor, args=(ic_id, "monto_neto", key_neto),
    )

    # ── FILA 2: Evento · Notas · Acciones ────────────────────────────────────
    ce, cn, ca = st.columns([2, 2.5, 1.8])

    key_ev = f"ev_{ic_id}"
    ce.selectbox(
        "Evento de Precio", list(evs.keys()),
        index=_idx(evs, ic.get("precio_evento_id")),
        key=key_ev,
        on_change=_cb_select, args=(ic_id, "precio_evento_id", key_ev, evs),
    )

    key_nota = f"nota_{ic_id}"
    cn.text_input(
        "Notas",
        value=ic.get("nota_pedido") or "",
        key=key_nota,
        on_change=_cb_valor, args=(ic_id, "nota_pedido", key_nota),
    )

    with ca:
        st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
        col_del, col_auth = st.columns(2)

        if col_del.button("✗ Eliminar", key=f"del_{ic_id}", type="secondary",
                          use_container_width=True):
            eliminar_ic(ic_id)
            st.rerun()

        # Validación mínima antes de autorizar
        _ok = (
            ic.get("tipo_id") is not None
            and ic.get("categoria_id") is not None
            and int(ic.get("pares") or 0) > 0
            and eta_val is not None
        )
        if col_auth.button("✓ AUTORIZAR", key=f"auth_{ic_id}", type="primary",
                           use_container_width=True, disabled=not _ok):
            ok, err = autorizar_ic(ic_id)
            if ok:
                st.rerun()
            else:
                st.error(f"No se pudo autorizar: {err}")
        if not _ok:
            ca.caption("⚠ Tipo, Categoría, Pares y ETA son obligatorios.")

    st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# TARJETA DEVUELTA — misma tarjeta editable + banner de motivo + acciones
# ─────────────────────────────────────────────────────────────────────────────

def _render_tarjeta_devuelta(ic: dict, cats: dict, tipos: dict, marcas: dict, evs: dict):
    motivo    = ic.get("motivo_devolucion") or "Sin motivo registrado"
    devuelto  = str(ic.get("devuelto_at") or "")[:16].replace("T", " ")
    st.error(f"**Devuelta por Digitación** ({devuelto}): {motivo}")

    # Reutiliza la misma tarjeta editable — update_campo_ic bloquea por estado,
    # así que extendemos la whitelist habilitando edición en DEVUELTO_ADMIN también.
    _render_tarjeta(ic, cats, tipos, marcas, evs)

    ic_id = int(ic["id"])
    col1, col2 = st.columns(2)
    if col1.button("↩ Re-autorizar", key=f"reauth_{ic_id}", type="primary",
                   use_container_width=True):
        if reutorizar_ic(ic_id):
            st.rerun()
        else:
            st.error("Error al re-autorizar.")
    if col2.button("✗ Anular definitivamente", key=f"anular_{ic_id}", type="secondary",
                   use_container_width=True):
        if anular_ic(ic_id):
            st.rerun()
        else:
            st.error("Error al anular.")
    st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# VISTA 1 — DASHBOARD (tres tabs)
# ─────────────────────────────────────────────────────────────────────────────

def _render_dashboard():
    df_pend = get_ics_pendientes()
    n_pend  = len(df_pend) if df_pend is not None and not df_pend.empty else 0

    # ── Botón nueva IC ────────────────────────────────────────────────────────
    col_m1, col_m2, col_m3, _, col_btn = st.columns([1, 1, 1, 0.3, 1.5])
    col_m1.metric("Pendientes", n_pend)
    if df_pend is not None and not df_pend.empty:
        col_m2.metric("Pares",   f"{int(df_pend['pares'].sum()):,}")
        col_m3.metric("Neto",    _fmt_gs(df_pend["monto_neto"].sum()))
    else:
        col_m2.metric("Pares", "0")
        col_m3.metric("Neto",  "Gs. 0")

    if col_btn.button("➕ Nueva Intención", type="primary",
                      use_container_width=True, key="ic_dash_nueva"):
        st.session_state.pop("ic_tipo_id", None)
        st.session_state.pop("ic_cat_id",  None)
        _go(VISTA_PASO_A)

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    df_dev  = get_ics_devueltas()
    n_dev   = len(df_dev) if df_dev is not None and not df_dev.empty else 0

    tab_pend, tab_dev, tab_hist = st.tabs([
        f"📋 PENDIENTES  ({n_pend})",
        f"🔄 DEVUELTAS  ({n_dev})" if n_dev > 0 else "🔄 DEVUELTAS",
        "📁 HISTORIAL",
    ])

    # ── PESTAÑA PENDIENTES ────────────────────────────────────────────────────
    with tab_pend:
        if n_pend == 0:
            st.info("No hay intenciones pendientes. Usá **Nueva Intención** para crear la primera.")
        else:
            cats = _cargar_catalogos()
            for _, ic in df_pend.iterrows():
                _render_tarjeta(
                    ic.to_dict(),
                    cats["cats"], cats["tipos"], cats["marcas"], cats["evs"],
                )

    # ── PESTAÑA DEVUELTAS ─────────────────────────────────────────────────────
    with tab_dev:
        if n_dev == 0:
            st.info("No hay ICs devueltas pendientes de revisión.")
        else:
            cats = _cargar_catalogos()
            for _, ic in df_dev.iterrows():
                _render_tarjeta_devuelta(
                    ic.to_dict(),
                    cats["cats"], cats["tipos"], cats["marcas"], cats["evs"],
                )

    # ── PESTAÑA HISTORIAL ─────────────────────────────────────────────────────
    with tab_hist:
        df_hist = get_ics_historial()
        if df_hist is None or df_hist.empty:
            st.info("Aún no hay intenciones autorizadas.")
        else:
            df_hist["fecha_llegada"] = pd.to_datetime(
                df_hist["eta"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")
            st.dataframe(
                df_hist.rename(columns={
                    "numero_registro": "IC Nro.",
                    "tipo":            "Tipo",
                    "categoria":       "Categoría",
                    "marca":           "Marca",
                    "cliente":         "Cliente",
                    "vendedor":        "Vendedor",
                    "fecha_llegada":   "ETA",
                    "pares":           "Pares",
                    "monto_neto":      "Neto (Gs.)",
                    "evento_precio":   "Evento Precio",
                    "estado":          "Estado",
                }).drop(columns=["eta"], errors="ignore"),
                column_config={
                    "Pares":      st.column_config.NumberColumn(format="%d"),
                    "Neto (Gs.)": st.column_config.NumberColumn(format="%.0f"),
                },
                use_container_width=True,
                hide_index=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# VISTA 2 — PASO A: DEFINICIÓN ESTRATÉGICA
# ─────────────────────────────────────────────────────────────────────────────

def _render_paso_a():
    st.markdown("### Paso 1 — Definición Estratégica")
    st.caption(
        "Clasificá esta IC antes de continuar. "
        "Estos campos conectan la compra con el Sales Report y son obligatorios."
    )
    st.divider()

    # ── Pre-carga Hiedra ──────────────────────────────────────────────────────
    hiedra_meta = st.session_state.get("hiedra_meta", {})
    if hiedra_meta.get("reconocido") and not st.session_state.get("ic_cat_id"):
        st.session_state["ic_cat_id"] = hiedra_meta["categoria_id"]
        cat_label = "COMPRA PREVIA" if hiedra_meta["categoria_codigo"] == "CP" else "PROGRAMADO"
        st.info(
            f"🌿 **Hiedra** pre-cargó la categoría: **{cat_label}** "
            f"· Proforma: **{hiedra_meta['nro_proforma_fabrica']}** "
            f"· PP Externo: **{hiedra_meta['nro_pp_externo']}**"
        )

    df_tipos = get_tipos()
    df_cats  = get_categorias()

    tipo_actual = st.session_state.get("ic_tipo_id")
    cat_actual  = st.session_state.get("ic_cat_id")

    # ── TIPO ─────────────────────────────────────────────────────────────────
    st.markdown("#### ¿Qué división?")
    cols_tipo = st.columns(max(len(df_tipos), 1))
    for i, (_, row) in enumerate(df_tipos.iterrows()):
        tid  = int(row["id_tipo"])
        tnm  = row["descp_tipo"]
        sel  = tipo_actual == tid
        lbl  = f"✅  {tnm}" if sel else tnm
        if cols_tipo[i].button(lbl, key=f"ic_tipo_{tid}", use_container_width=True,
                               type="primary" if sel else "secondary"):
            st.session_state["ic_tipo_id"] = tid
            st.rerun()

    st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)

    # ── CATEGORÍA ────────────────────────────────────────────────────────────
    st.markdown("#### ¿Qué estrategia de compra?")

    _CAT_INFO = {
        "PRE VENTA":  ("COMPRA PREVIA",  "Mercadería para la importadora.\nSe ofrece por catálogo durante los 90 días de tránsito."),
        "PROGRAMADO": ("PROGRAMADO",      "Intermediación directa fábrica → cliente.\nLa importadora gestiona el puente."),
    }

    cols_cat = st.columns(max(len(df_cats), 1))
    for i, (_, row) in enumerate(df_cats.iterrows()):
        cid      = int(row["id_categoria"])
        raw_name = row["descp_categoria"]
        sel      = cat_actual == cid
        display_name, desc = _CAT_INFO.get(raw_name, (raw_name, ""))
        border   = "#D4AF37" if sel else "#334155"

        with cols_cat[i]:
            st.markdown(
                f"""<div style='border:2px solid {border};border-radius:8px;
                        padding:14px 16px;margin-bottom:8px;background:#1C1F2E;'>
                    <div style='color:#F8FAFC;font-size:0.95rem;font-weight:bold;margin-bottom:6px;'>
                        {"✅ " if sel else ""}{display_name}
                    </div>
                    <div style='color:#94A3B8;font-size:0.82rem;line-height:1.45;
                                white-space:pre-line;'>{desc}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("✅ Seleccionado" if sel else "Seleccionar",
                         key=f"ic_cat_{cid}", use_container_width=True,
                         type="primary" if sel else "secondary"):
                st.session_state["ic_cat_id"] = cid
                st.rerun()

    st.divider()

    col_back, _, col_next = st.columns([1, 2, 1])
    if col_back.button("← Dashboard", key="ic_paso_a_back", use_container_width=True):
        _go(VISTA_DASHBOARD)

    listo = tipo_actual is not None and cat_actual is not None
    if listo:
        if col_next.button("Continuar →", type="primary", key="ic_paso_a_ok",
                           use_container_width=True):
            _go(VISTA_FORM)
    else:
        col_next.button("Continuar →", disabled=True, key="ic_paso_a_dis",
                        use_container_width=True,
                        help="Seleccioná División y Estrategia para continuar.")


# ─────────────────────────────────────────────────────────────────────────────
# VISTA 3 — PASO B: FORMULARIO
# ─────────────────────────────────────────────────────────────────────────────

def _render_form():
    tipo_id = st.session_state.get("ic_tipo_id")
    cat_id  = st.session_state.get("ic_cat_id")

    df_tipos = get_tipos()
    df_cats  = get_categorias()
    tipo_nm  = next((r["descp_tipo"]      for _, r in df_tipos.iterrows() if int(r["id_tipo"])      == tipo_id), "—")
    cat_nm   = next((r["descp_categoria"] for _, r in df_cats.iterrows()  if int(r["id_categoria"]) == cat_id),  "—")

    st.markdown(
        f"""<div style='background:#1C1F2E;border-left:4px solid #D4AF37;
                padding:10px 16px;border-radius:4px;margin-bottom:16px;'>
            <span style='color:#94A3B8;font-size:0.78rem;'>CLASIFICACIÓN ESTRATÉGICA</span><br>
            <span style='color:#F8FAFC;font-size:0.95rem;'>
                <b>División:</b> {tipo_nm} &nbsp;·&nbsp; <b>Estrategia:</b> {cat_nm}
            </span>
        </div>""",
        unsafe_allow_html=True,
    )

    if st.button("← Cambiar clasificación", key="ic_form_back"):
        _go(VISTA_PASO_A)

    st.markdown("#### Nueva Intención de Compra")
    st.caption("El número de registro IC-YYYY-XXXX se asigna automáticamente al guardar.")

    df_prov = get_proveedores()
    df_vend = get_vendedores()
    df_marc = get_marcas()
    df_plaz = get_plazos()

    if df_prov.empty or df_vend.empty or df_marc.empty:
        st.error("No se pudieron cargar los catálogos. Verificar conexión a BD.")
        return

    opts_prov = _opts(df_prov, "id",         "nombre")
    opts_vend = _opts(df_vend, "id_vendedor", "descp_vendedor")
    opts_marc = _opts(df_marc, "id_marca",    "descp_marca")
    opts_plaz = {"SIN DEFINIR": None}
    opts_plaz.update(_opts(df_plaz, "id_plazo", "descp_plazo"))

    c1, c2 = st.columns(2)
    sel_prov = c1.selectbox("Proveedor", list(opts_prov.keys()), key="ic_prov")
    sel_marc = c2.selectbox("Marca",     list(opts_marc.keys()), key="ic_marc")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**Cliente** — Ingresá el código del papel/email")
        cod_cliente = st.number_input("Código de Cliente", min_value=1, step=1,
                                      value=276, key="ic_cod_cli",
                                      label_visibility="collapsed")
        nombre_cliente = buscar_cliente(int(cod_cliente))
        if nombre_cliente:
            st.success(f"✔ {cod_cliente} — {nombre_cliente}")
        else:
            st.error(f"✗ Código {cod_cliente} no encontrado en la BD.")

    with c4:
        sel_vend = st.selectbox("Vendedor Responsable", list(opts_vend.keys()), key="ic_vend")

    c5, c6, c7, c8 = st.columns([2, 1, 1, 1])
    sel_plaz  = c5.selectbox("Plazo de Pago",     list(opts_plaz.keys()), key="ic_plaz")
    pares     = c6.number_input("Total Pares",    min_value=0, step=12, value=0, key="ic_pares")
    fecha_reg = c7.date_input("Fecha Registro",   value=date.today(), key="ic_fecha_reg")
    fecha_eta = c8.date_input("ETA (Llegada PY)", value=None, key="ic_fecha_eta",
                               help="Fecha estimada de arribo a Paraguay")

    # Pre-llenado Hiedra
    _hm = st.session_state.get("hiedra_meta", {})
    _nota_default = (
        f"HIEDRA · Proforma: {_hm['nro_proforma_fabrica']} · PP Externo: {_hm['nro_pp_externo']}"
        if _hm.get("reconocido") else ""
    )
    nota_pedido = st.text_input(
        "Nota / Referencia del Pedido",
        value=_nota_default,
        placeholder="Ej: Email 30-03 | Nota pedido #4567 | Proforma 3130",
        key="ic_nota",
        help="Referencia del papel o email recibido con la orden del cliente.",
    )

    st.markdown("**Condiciones Financieras** — Montos pueden registrarse en 0 para definir en etapa posterior")
    monto_bruto = st.number_input("Monto Bruto Total (Gs.)", min_value=0.0,
                                   step=1_000_000.0, value=0.0, format="%.0f",
                                   key="ic_bruto")
    cd1, cd2, cd3, cd4 = st.columns(4)
    d1 = cd1.number_input("Desc. 1 (%)", 0.0, 100.0, 0.0, 0.5, key="ic_d1", format="%.2f")
    d2 = cd2.number_input("Desc. 2 (%)", 0.0, 100.0, 0.0, 0.5, key="ic_d2", format="%.2f")
    d3 = cd3.number_input("Desc. 3 (%)", 0.0, 100.0, 0.0, 0.5, key="ic_d3", format="%.2f")
    d4 = cd4.number_input("Desc. 4 (%)", 0.0, 100.0, 0.0, 0.5, key="ic_d4", format="%.2f")

    monto_neto = calcular_neto(monto_bruto, d1, d2, d3, d4)
    st.markdown(
        f"""<div style="background:#1C1F2E;border-left:4px solid #D4AF37;
                padding:10px 16px;border-radius:4px;margin:8px 0;">
            <span style="color:#94A3B8;font-size:0.8rem;">MONTO NETO CALCULADO</span><br>
            <span style="color:#D4AF37;font-size:1.4rem;font-weight:bold;">{_fmt_gs(monto_neto)}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    observaciones = st.text_area("Observaciones", height=70,
                                  placeholder="Condiciones especiales, notas de negociación...",
                                  key="ic_obs")

    # Listado de precios
    st.markdown("**Listado de Precios** — Vincular al evento de precio vigente")
    df_eventos_precio = get_eventos_precio_cerrados()
    opts_ev = {"— Sin vincular por ahora —": None}
    if df_eventos_precio is not None and not df_eventos_precio.empty:
        for _, ev in df_eventos_precio.iterrows():
            lbl = (f"{ev['nombre_evento']}  ·  "
                   f"{str(ev['fecha_vigencia_desde'])[:10]}  ·  "
                   f"{int(ev['total_skus']):,} SKUs")
            opts_ev[lbl] = int(ev["id"])
    sel_ev_label = st.selectbox("Lista de precios", list(opts_ev.keys()), key="ic_precio_ev")
    precio_ev_id = opts_ev[sel_ev_label]
    if precio_ev_id:
        st.caption(f"✅ Esta IC quedará vinculada al listado **{sel_ev_label.split('  ·  ')[0]}**.")

    # ── Matriz de Negociación (Línea → Caso → Listado → Comisión) ────────────
    st.divider()
    listado_precio_id  = None
    comision_id        = None
    comision_pct_snap  = None

    if cat_id == _ID_PROGRAMADO:
        st.markdown("#### 📌 Negociación PROGRAMADO — Línea → Caso → Listado")
        st.caption("La línea determina el caso automáticamente. El listado define la escala de precio.")

        proveedor_id_sel = opts_prov.get(sel_prov)
        df_lineas = get_lineas_con_caso(proveedor_id_sel)

        if df_lineas is None or df_lineas.empty:
            st.warning("No hay líneas configuradas para este proveedor. "
                       "Asignalas en Motor de Precios → Admin Líneas.")
        else:
            opts_lineas = {
                f"{int(r['codigo_proveedor'])} — {r['descripcion'] or '—'}"
                f"{' · [' + r['caso_nombre'] + ']' if r.get('caso_nombre') else ' · ⚠ sin caso'}":
                {"id": int(r["id"]), "caso_nombre": r.get("caso_nombre")}
                for _, r in df_lineas.iterrows()
            }
            linea_label = st.selectbox("Línea del pedido", list(opts_lineas.keys()),
                                       key="ic_linea_neg")
            linea_data  = opts_lineas[linea_label]
            caso_nombre = linea_data.get("caso_nombre")

            if caso_nombre:
                st.info(f"📌 Caso detectado automáticamente: **{caso_nombre}**")

                if precio_ev_id:
                    listados_disp = get_listados_para_caso(precio_ev_id, caso_nombre)
                    if listados_disp:
                        opts_lp = {l["nombre"]: l["id"] for l in listados_disp}
                        lp_label = st.selectbox("Listado de precio aplicable",
                                                list(opts_lp.keys()), key="ic_lp_neg")
                        listado_precio_id = opts_lp[lp_label]

                        df_com = get_comisiones()
                        if df_com is not None and not df_com.empty:
                            opts_com = {"— Sin comisión —": None}
                            opts_com.update({
                                f"{r['nombre']} ({float(r['porcentaje']):.1f}%)": int(r["id"])
                                for _, r in df_com.iterrows()
                            })
                            com_label = st.selectbox("Comisión vendedor", list(opts_com.keys()),
                                                     key="ic_com_neg")
                            comision_id = opts_com[com_label]
                            if comision_id:
                                pct_row = df_com[df_com["id"] == comision_id]
                                if not pct_row.empty:
                                    comision_pct_snap = float(pct_row["porcentaje"].iloc[0])
                                    st.metric("Comisión snapshot", f"{comision_pct_snap:.1f}%")
                    else:
                        st.warning("El evento de precio seleccionado no tiene valores "
                                   "calculados para este caso. Calculá el evento primero.")
                else:
                    st.caption("Seleccioná un evento de precio arriba para ver listados disponibles.")
            else:
                st.warning("⚠ Esta línea no tiene caso asignado. "
                           "Asignalo en Motor de Precios → Admin Líneas.")

    elif cat_id == _ID_COMPRA_PREVIA:
        st.markdown("#### 📋 Listado de referencia — COMPRA PREVIA (opcional)")
        st.caption("En Compra Previa el precio final se define al momento de la venta. Default: LPN.")
        opts_lp_cp = {
            "LPN — referencia base": 1,
            "Sin definir — se determina en ventas": None,
        }
        lp_cp_label = st.selectbox("Listado de referencia", list(opts_lp_cp.keys()),
                                   key="ic_lp_cp")
        listado_precio_id = opts_lp_cp[lp_cp_label]

    _, col_btn = st.columns([3, 1])
    if col_btn.button("🔒 REGISTRAR", type="primary", use_container_width=True, key="ic_submit"):
        if not nombre_cliente:
            st.error(f"El código de cliente {cod_cliente} no existe.")
            return
        if pares == 0:
            st.warning("Ingresá la cantidad de pares antes de registrar.")
            return
        if not fecha_eta:
            st.warning("La fecha de llegada (ETA) es obligatoria.")
            return

        ok, resultado = save_intencion({
            "id_proveedor":         opts_prov[sel_prov],
            "id_cliente":           int(cod_cliente),
            "id_vendedor":          opts_vend[sel_vend],
            "id_marca":             opts_marc[sel_marc],
            "id_plazo":             opts_plaz[sel_plaz],
            "tipo_id":              tipo_id,
            "categoria_id":         cat_id,
            "cantidad_total_pares": pares,
            "monto_bruto":          monto_bruto,
            "descuento_1": d1, "descuento_2": d2,
            "descuento_3": d3, "descuento_4": d4,
            "fecha_registro":           fecha_reg,
            "fecha_llegada":            fecha_eta,
            "nota_pedido":              nota_pedido,
            "observaciones":            observaciones,
            "precio_evento_id":         precio_ev_id,
            "listado_precio_id":        listado_precio_id,
            "comision_vendedor_id":     comision_id,
            "comision_porcentaje_snap": comision_pct_snap,
        })

        if ok:
            st.success(f"Registrado: **{resultado}** | {sel_marc} | {pares:,} pares | ETA {fecha_eta}")
            st.session_state["ic_vista"] = VISTA_DASHBOARD
            st.session_state.pop("ic_tipo_id",  None)
            st.session_state.pop("ic_cat_id",   None)
            st.session_state.pop("hiedra_meta", None)
            st.rerun()
        else:
            st.error(resultado)


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULO PREVENTA — catálogo + carrito + creación IC
# ─────────────────────────────────────────────────────────────────────────────

_MARCO_TRANSITO = "#F59E0B"   # ámbar
_MARCO_DEPOSITO = "#10B981"   # verde


def _get_url_imagen(linea: str, referencia: str) -> str:
    return f"https://placehold.co/200x200/1a1a2e/white?text={linea}.{referencia}"


def _agregar_al_carrito(item: dict, cajas: int) -> None:
    carrito = st.session_state.setdefault("carrito_preventa", {})
    key = f"{item['pp_id']}_{item['det_id']}"
    pares_por_caja = int(item.get("pares_por_caja") or 0)
    pares = cajas * pares_por_caja
    carrito[key] = {
        "key":                    key,
        "pp_id":                  item["pp_id"],
        "det_id":                 item["det_id"],
        "proveedor_importacion_id": item.get("proveedor_importacion_id"),
        "evento_id":              item.get("evento_id"),
        "id_marca":               item.get("id_marca"),
        "marca":                  item.get("marca", "—"),
        "linea":                  item.get("linea", ""),
        "referencia":             item.get("referencia", ""),
        "nombre":                 item.get("nombre", ""),
        "style_code":             item.get("style_code", ""),
        "mat_cod":                item.get("material_code", ""),
        "mat_desc":               item.get("mat_desc", ""),
        "col_cod":                item.get("color_code", ""),
        "col_desc":               item.get("col_desc", ""),
        "cajas":                  cajas,
        "pares_por_caja":         pares_por_caja,
        "pares":                  pares,
        "lpn":                    item.get("lpn"),
        "disponible_pares":       int(item.get("cantidad_pares") or 0),
        "disponible_cajas":       int(item.get("cantidad_cajas") or 0),
    }


def _formatear_gradas(grades_json_str) -> str:
    """Convierte grades_json {"34":1,"35":2,...} → "34(1-2-...)39"."""
    import json
    try:
        if not grades_json_str:
            return "—"
        gj = json.loads(grades_json_str) if isinstance(grades_json_str, str) else grades_json_str
        if not gj:
            return "—"
        gradas = sorted(
            [{"talla_etiqueta": k, "cantidad": v} for k, v in gj.items() if v],
            key=lambda g: extraer_valor_numerico_talla(g["talla_etiqueta"]),
        )
        if not gradas:
            return "—"
        curva = "-".join(str(g["cantidad"]) for g in gradas)
        return f"{gradas[0]['talla_etiqueta']}({curva}){gradas[-1]['talla_etiqueta']}"
    except Exception:
        return "—"


def _render_miniatura(item: dict) -> None:
    color_marco = _MARCO_TRANSITO if item.get("origen", "transito") == "transito" else _MARCO_DEPOSITO
    url_img = _get_url_imagen(item.get("linea", ""), item.get("referencia", ""))
    det_id = item["det_id"]

    st.markdown(
        f"""<div style="border:3px solid {color_marco};border-radius:8px;
                padding:4px;margin-bottom:6px;">
            <img src="{url_img}"
                 style="width:100%;border-radius:4px;"
                 onerror="this.src='https://placehold.co/200x200/1a1a2e/white?text={item.get('referencia','?')}'"
            >
        </div>""",
        unsafe_allow_html=True,
    )

    nombre_corto = (item.get("nombre") or "")[:24]
    lpn_val = item.get("lpn")
    pares_caja = int(item.get("pares_por_caja") or 0)
    disp_cajas = int(item.get("cantidad_cajas") or 0)
    gradas_fmt = _formatear_gradas(item.get("grades_json"))

    st.caption(
        f"**L{item.get('linea','')} · R{item.get('referencia','')}**  \n"
        f"{nombre_corto}  \n"
        f"📦 {gradas_fmt}"
    )
    if lpn_val:
        st.caption(f"LPN: Gs. {float(lpn_val):,.0f}")
    else:
        st.caption("Sin precio")

    key_cajas = f"cajas_{det_id}"
    if key_cajas not in st.session_state:
        st.session_state[key_cajas] = 0

    col_menos, col_cantidad, col_mas = st.columns([1, 2, 1])
    with col_menos:
        if st.button("−", key=f"menos_{det_id}", use_container_width=True):
            if st.session_state[key_cajas] > 0:
                st.session_state[key_cajas] -= 1
                st.rerun()
    with col_cantidad:
        cajas = st.session_state[key_cajas]
        pares = cajas * pares_caja
        st.markdown(
            f"<div style='text-align:center;line-height:1.3'>"
            f"<b>{cajas} cajas</b><br>"
            f"<small>{pares} pares</small>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_mas:
        if st.button("+", key=f"mas_{det_id}", use_container_width=True):
            if st.session_state[key_cajas] < disp_cajas:
                st.session_state[key_cajas] += 1
                st.rerun()

    if st.session_state[key_cajas] > 0:
        if st.button("Agregar →", key=f"add_{det_id}", type="primary",
                     use_container_width=True):
            _agregar_al_carrito(item, st.session_state[key_cajas])
            st.session_state[key_cajas] = 0
            st.rerun()


def _render_catalogo_preventa(pp_id: int) -> None:
    st.subheader("Catálogo de Preventa")

    marcas_pp = get_marcas_del_pp(pp_id)
    col_marca, col_buscar = st.columns([2, 3])
    with col_marca:
        filtro_marca = st.selectbox("Marca", ["Todas"] + marcas_pp,
                                    key="pv_filtro_marca")
    with col_buscar:
        buscar = st.text_input("Buscar línea / ref / material",
                               key="pv_buscar", placeholder="ej: 2133 o CHINELO")

    stock = cargar_stock_preventa_pp(pp_id, filtro_marca, buscar)

    if not stock:
        st.info("Sin artículos disponibles con los filtros seleccionados.")
        return

    st.caption(f"{len(stock)} artículos disponibles")

    cols = st.columns(4)
    for idx, item in enumerate(stock):
        with cols[idx % 4]:
            _render_miniatura(item)


def _render_carrito_preventa() -> None:
    carrito: dict = st.session_state.get("carrito_preventa", {})

    if not carrito:
        st.info("El carrito está vacío. Agregá artículos desde el catálogo.")
        return

    total_art   = len(carrito)
    total_pares = sum(i["pares"] for i in carrito.values())
    total_monto = sum(
        i["pares"] * (i.get("lpn") or 0) for i in carrito.values()
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Artículos", total_art)
    c2.metric("Total pares", f"{total_pares:,}")
    c3.metric("Monto est. (Gs.)", f"{total_monto:,.0f}")

    st.divider()

    # NIVEL 1: agrupar por PP (Lote)
    por_pp: dict[int, list[dict]] = {}
    for item in carrito.values():
        pp_id = item["pp_id"]
        por_pp.setdefault(pp_id, []).append(item)

    for pp_id, items_pp in por_pp.items():
        pares_pp = sum(i["pares"] for i in items_pp)
        with st.expander(f"📦 PP-{pp_id}  ·  {pares_pp:,} pares", expanded=True):
            # NIVEL 2: agrupar por Marca
            por_marca: dict[str, list[dict]] = {}
            for item in items_pp:
                por_marca.setdefault(item.get("marca", "—"), []).append(item)

            for marca, items_marca in por_marca.items():
                pares_marca = sum(i["pares"] for i in items_marca)
                st.markdown(f"**{marca}** — {pares_marca:,} pares")

                hdr = st.columns([1, 1, 1.8, 1, 1, 1.5, 0.5])
                for h, lbl in zip(hdr, ["Línea","Ref.","Material","Cajas","Pares","Monto",""]):
                    h.caption(lbl)

                # NIVEL 3: items individuales
                for item in items_marca:
                    c_lin, c_ref, c_mat, c_caj, c_par, c_mnt, c_del = st.columns(
                        [1, 1, 1.8, 1, 1, 1.5, 0.5]
                    )
                    c_lin.write(item.get("linea", "—"))
                    c_ref.write(item.get("referencia", "—"))
                    c_mat.write((item.get("mat_desc") or "—")[:22])
                    c_caj.write(str(item["cajas"]))
                    c_par.write(str(item["pares"]))
                    monto = item["pares"] * (item.get("lpn") or 0)
                    c_mnt.write(f"{monto:,.0f}")
                    if c_del.button("✕", key=f"del_{item['key']}"):
                        del st.session_state["carrito_preventa"][item["key"]]
                        st.rerun()

                st.divider()

    # ── Confirmar ─────────────────────────────────────────────────────────────
    with st.expander("✓ CONFIRMAR PREVENTA", expanded=False):
        _render_confirmar_preventa(carrito)


def _render_confirmar_preventa(carrito: dict) -> None:
    st.caption(
        "Completá los datos de la IC que se creará en la bandeja de Pendientes."
    )

    df_tipos = get_tipos()
    df_vend  = get_vendedores()

    opts_tipos = {r["descp_tipo"]: int(r["id_tipo"]) for _, r in df_tipos.iterrows()}
    opts_vend  = {r["descp_vendedor"]: int(r["id_vendedor"]) for _, r in df_vend.iterrows()}

    col_tipo, col_vend = st.columns(2)
    sel_tipo = col_tipo.selectbox("División", list(opts_tipos.keys()), key="pv_tipo")
    sel_vend = col_vend.selectbox("Vendedor", list(opts_vend.keys()), key="pv_vend")

    st.markdown("**Cliente**")
    cod_cli = st.number_input("Código de cliente", min_value=1, step=1,
                               value=276, key="pv_cod_cli",
                               label_visibility="collapsed")
    nombre_cli = buscar_cliente(int(cod_cli))
    if nombre_cli:
        st.success(f"✔ {cod_cli} — {nombre_cli}")
    else:
        st.error(f"✗ Código {cod_cli} no encontrado.")

    eta = st.date_input("ETA (fecha llegada)", value=None, key="pv_eta")
    nota = st.text_input("Nota", value="", key="pv_nota",
                          placeholder="Ej: Preventa CP-6421 / email 30-04")

    if st.button("🔒 CREAR INTENCIÓN DE COMPRA", type="primary",
                 key="pv_confirmar", use_container_width=True):
        if not nombre_cli:
            st.error("Código de cliente inválido.")
            return
        if not eta:
            st.warning("La ETA es obligatoria.")
            return

        ok, resultado = crear_ic_preventa(
            carrito=carrito,
            id_cliente=int(cod_cli),
            id_vendedor=opts_vend[sel_vend],
            tipo_id=opts_tipos[sel_tipo],
            fecha_eta=eta,
            nota=nota,
        )
        if ok:
            n = len(resultado)
            st.success(
                f"✓ {n} IC{'s' if n > 1 else ''} creada{'s' if n > 1 else ''}: "
                + ", ".join(f"**{r}**" for r in resultado)
                + " — aparece en Pendientes para autorización."
            )
            st.session_state["carrito_preventa"] = {}
            st.rerun()
        else:
            st.error(f"Error al crear IC: {resultado[0]}")


def _render_modulo_preventa() -> None:
    df_pps = get_pps_para_preventa()

    if df_pps is None or df_pps.empty:
        st.info("No hay Pedidos Proveedor abiertos para preventa.")
        return

    # Selector de PP
    opts_pp: dict[str, int] = {}
    for _, row in df_pps.iterrows():
        eta_str = str(row.get("eta") or "")[:10]
        lbl = (
            f"{row['numero_registro']}  ·  "
            f"{row.get('marcas','—')}  ·  "
            f"{int(row['pares_total']):,} pares"
            + (f"  ·  ETA {eta_str}" if eta_str else "")
        )
        opts_pp[lbl] = int(row["id"])

    sel_lbl = st.selectbox(
        "Pedido Proveedor", list(opts_pp.keys()), key="pv_pp_sel"
    )
    pp_id = opts_pp[sel_lbl]

    st.divider()

    # Columna catálogo | columna carrito
    col_cat, col_cart = st.columns([2.5, 1.5])

    with col_cat:
        _render_catalogo_preventa(pp_id)

    with col_cart:
        st.subheader("🛒 Carrito")
        _render_carrito_preventa()


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def render_intencion_compra():
    st.markdown(
        "<h2 style='color:#D4AF37;margin-bottom:4px;'>📋 Intención de Compra</h2>"
        "<p style='color:#94A3B8;margin-top:0;'>Alta gerencia — Compromiso financiero "
        "por marca. Sin datos de producto.</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    tab_ic, tab_prev = st.tabs(["📋 Intención de Compra", "🛒 Preventa"])

    with tab_ic:
        vista = st.session_state.get("ic_vista", VISTA_DASHBOARD)

        if vista == VISTA_DASHBOARD:
            _render_dashboard()
        elif vista == VISTA_PASO_A:
            _render_paso_a()
        elif vista == VISTA_FORM:
            _render_form()
        else:
            st.session_state["ic_vista"] = VISTA_DASHBOARD
            st.rerun()

    with tab_prev:
        _render_modulo_preventa()
