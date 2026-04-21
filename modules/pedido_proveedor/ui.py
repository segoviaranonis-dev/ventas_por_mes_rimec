# =============================================================================
# MÓDULO: Pedido Proveedor
# ARCHIVO: modules/pedido_proveedor/ui.py
# DESCRIPCIÓN: Interfaz master-detail del módulo.
#
#  Arquitectura de pantallas (routing por session_state):
#    LISTA   → tabla de 15 PPs con selector para abrir detalle
#    DETALLE → cabecera (Padre) + Ala Norte (artículos F9) + Ala Sur (ventas)
#    FORM    → formulario creación de nuevo PP (desde sidebar "Nuevo Pedido")
# =============================================================================

import streamlit as st
import pandas as pd

from core.constants import MES_NOMBRES
from core.tabla_articulos import render_tabla_5pilares
from modules.pedido_proveedor.logic import (
    get_intenciones_con_saldo,
    get_ic_saldo,
    parse_f9,
    save_pp,
    get_pedidos_proveedor,
    get_pp_header,
    get_pp_ala_norte,
    get_ala_sur_facturas,
    get_plazos,
    buscar_cliente_pp,
    get_vendedores_pp,
    get_marcas_de_pp,
    get_skus_por_marcas,
    save_factura_manual,
)
from modules.pedido_proveedor.showroom import render_showroom


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_date(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    try:
        return str(val)[:10]
    except Exception:
        return "—"


_ESTADO_COLOR = {
    "ABIERTO":  "#22C55E",
    "ENVIADO":  "#EF4444",   # bloqueado en COMPRA
    "CERRADO":  "#94A3B8",
    "ANULADO":  "#EF4444",
}


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA — router
# ─────────────────────────────────────────────────────────────────────────────

def render_pedido_proveedor():
    id_sel        = st.session_state.get("pp_selected_id")
    show_form     = st.session_state.get("pp_mostrar_form", False)
    show_showroom = st.session_state.get("pp_vista_showroom", False)

    if id_sel:
        _render_detalle_pp(int(id_sel))
    elif show_form:
        _render_form()
    elif show_showroom:
        render_showroom()
    else:
        _render_cabecera_modulo()
        _render_lista_pp()


def _render_cabecera_modulo():
    st.markdown(
        "<h2 style='color:#D4AF37;margin-bottom:4px;'>📦 Pedido Proveedor</h2>"
        "<p style='color:#94A3B8;margin-top:0;'>"
        "Pedidos de importación — Ala Norte: artículos del F9 &nbsp;·&nbsp; "
        "Ala Sur: ventas en tránsito</p>",
        unsafe_allow_html=True,
    )
    st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# VISTA LISTA
# ─────────────────────────────────────────────────────────────────────────────

def _quincena_label(fecha) -> str:
    """Devuelve '1ª Quincena de Mayo 2026' a partir de una fecha."""
    if fecha is None or (isinstance(fecha, float) and pd.isna(fecha)):
        return "Sin fecha"
    try:
        dt  = pd.to_datetime(fecha)
        q   = "1ª" if dt.day <= 15 else "2ª"
        mes = MES_NOMBRES.get(dt.month, str(dt.month))
        return f"{q} Quincena de {mes} {dt.year}"
    except Exception:
        return "Sin fecha"


def _render_lista_pp():
    filtros = st.session_state.get("pp_filtros", {})
    df      = get_pedidos_proveedor(filtros)

    if df.empty:
        st.info("No hay pedidos que coincidan con los filtros.")
        return

    # ── Calcular saldo y quincena ─────────────────────────────────────────────
    df["saldo"] = (
        df["pares_comprometidos"].fillna(0).astype(int)
        - df["total_vendido"].fillna(0).astype(int)
    )
    # Ordenar cronológicamente ASC por fecha de arribo estimada
    df["_fecha_eta_dt"] = pd.to_datetime(df["fecha_eta"], errors="coerce")
    df = df.sort_values("_fecha_eta_dt", ascending=True, na_position="last")

    df["quincena_label"] = df["fecha_eta"].apply(_quincena_label)

    # Quincenas en el orden ya establecido por el sort
    quincenas = list(dict.fromkeys(df["quincena_label"].tolist()))

    for quincena in quincenas:
        df_q   = df[df["quincena_label"] == quincena]
        total_ini  = int(df_q["pares_comprometidos"].sum())
        total_vend = int(df_q["total_vendido"].sum())
        pct_q  = round(total_vend / total_ini * 100, 1) if total_ini > 0 else 0.0
        n_pps  = len(df_q)

        exp_label = (
            f"📅  {quincena}"
            f"  —  {n_pps} preventa{'s' if n_pps != 1 else ''}"
            f"  ·  {total_ini:,} pares"
            f"  ·  {pct_q} % ejecutado"
        )

        # Mantener expandido si hay un formulario de "Enviar a Compra" abierto
        any_ec_open = any(
            st.session_state.get(f"_pp_enviar_open_{int(r['id'])}")
            for _, r in df_q.iterrows()
        )
        with st.expander(exp_label, expanded=any_ec_open):
            # ── Botones de preventa (2 columnas) ──────────────────────────────
            n_cols = 2
            rows   = [df_q.iloc[i : i + n_cols] for i in range(0, len(df_q), n_cols)]

            for row_df in rows:
                cols = st.columns(n_cols)
                for col, (_, pp) in zip(cols, row_df.iterrows()):
                    ini     = int(pp["pares_comprometidos"] or 0)
                    vend    = int(pp["total_vendido"] or 0)
                    saldo   = int(pp["saldo"])
                    pct     = round(vend / ini * 100, 1) if ini > 0 else 0.0
                    bar_w   = min(int(pct), 100)

                    if pct >= 80:
                        bar_color = "#22C55E"; pct_color = "#22C55E"
                    elif pct >= 40:
                        bar_color = "#F59E0B"; pct_color = "#F59E0B"
                    else:
                        bar_color = "#3B82F6"; pct_color = "#3B82F6"

                    estado_color = _ESTADO_COLOR.get(str(pp["estado"]), "#94A3B8")

                    with col:
                        st.markdown(
                            f"""
                            <div style="background:linear-gradient(135deg,#1C2E3F,#0F1E2F);
                                        border:1px solid #334155;border-radius:14px;
                                        padding:20px 24px;margin-bottom:4px;">
                              <div style="display:flex;justify-content:space-between;
                                          align-items:flex-start;margin-bottom:12px;">
                                <div>
                                  <div style="font-size:.72rem;color:#64748B;
                                              letter-spacing:.06em;text-transform:uppercase;">
                                    Preventa</div>
                                  <div style="font-size:1.1rem;font-weight:700;
                                              color:#F1F5F9;margin-top:2px;">
                                    {pp['numero_registro']}</div>
                                  <div style="font-size:.82rem;color:#94A3B8;margin-top:2px;">
                                    {pp['marcas']} &nbsp;·&nbsp; Proforma {pp['numero_proforma']}</div>
                                </div>
                                <span style="background:{estado_color}22;color:{estado_color};
                                             font-size:.68rem;font-weight:600;padding:3px 8px;
                                             border-radius:4px;letter-spacing:.04em;">
                                  {pp['estado']}
                                </span>
                              </div>
                              <div style="display:flex;gap:24px;margin-bottom:14px;">
                                <div>
                                  <div style="color:#64748B;font-size:.66rem;
                                              letter-spacing:.05em;text-transform:uppercase;">
                                    Compra Inicial</div>
                                  <div style="color:#F1F5F9;font-size:1.05rem;font-weight:700;">
                                    {ini:,} pares</div>
                                </div>
                                <div>
                                  <div style="color:#64748B;font-size:.66rem;
                                              letter-spacing:.05em;text-transform:uppercase;">
                                    Venta Tránsito</div>
                                  <div style="color:#D4AF37;font-size:1.05rem;font-weight:700;">
                                    {vend:,} pares</div>
                                </div>
                                <div>
                                  <div style="color:#64748B;font-size:.66rem;
                                              letter-spacing:.05em;text-transform:uppercase;">
                                    Saldo Real</div>
                                  <div style="color:#22C55E;font-size:1.05rem;font-weight:700;">
                                    {saldo:,}</div>
                                </div>
                              </div>
                              <div style="display:flex;align-items:center;gap:10px;">
                                <div style="flex:1;background:#0F1E2F;
                                            border-radius:4px;height:8px;">
                                  <div style="background:{bar_color};width:{bar_w}%;
                                              height:8px;border-radius:4px;"></div>
                                </div>
                                <span style="color:{pct_color};font-size:.82rem;
                                             font-weight:700;min-width:44px;text-align:right;">
                                  {pct} %</span>
                              </div>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "📋 Abrir detalle",
                            key=f"pp_open_{pp['id']}",
                            use_container_width=True,
                            type="primary",
                        ):
                            st.session_state["pp_selected_id"] = int(pp["id"])
                            st.rerun()
                        if str(pp["estado"]) == "ENVIADO":
                            st.markdown(
                                "<div style='background:#EF444422;border:1px solid #EF4444;"
                                "border-radius:8px;padding:7px 14px;text-align:center;"
                                "color:#EF4444;font-size:.8rem;font-weight:600;'>"
                                "🔒 Transferido a Compra</div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            if st.button(
                                "📦 Enviar a Compra",
                                key=f"pp_ec_{pp['id']}",
                                use_container_width=True,
                            ):
                                st.session_state[f"_pp_enviar_open_{int(pp['id'])}"] = True
                                st.rerun()

            # ── Formulario inline Enviar a Compra ─────────────────────────
            for _, pp in df_q.iterrows():
                if st.session_state.get(f"_pp_enviar_open_{int(pp['id'])}"):
                    st.divider()
                    _render_enviar_a_compra(int(pp["id"]), str(pp["numero_proforma"]))
                    break


# ─────────────────────────────────────────────────────────────────────────────
# VISTA DETALLE — Padre + Ala Norte + Ala Sur
# ─────────────────────────────────────────────────────────────────────────────

def _render_detalle_pp(id_pp: int):
    header = get_pp_header(id_pp)
    if not header:
        st.error(f"Pedido Proveedor ID {id_pp} no encontrado.")
        return

    estado       = header["estado"]
    estado_color = _ESTADO_COLOR.get(estado, "#F1F5F9")

    # ── Título ────────────────────────────────────────────────────────────────
    st.markdown(
        f"<h2 style='color:#D4AF37;margin-bottom:2px;'>📦 {header['numero_registro']}</h2>"
        f"<p style='color:#94A3B8;margin:0 0 4px 0;'>"
        f"Proforma: <b style='color:#F1F5F9;'>{header['numero_proforma']}</b>"
        f"&nbsp;·&nbsp;"
        f"Proveedor: <b style='color:#F1F5F9;'>{header['proveedor']}</b>"
        f"&nbsp;·&nbsp;"
        f"Estado: <b style='color:{estado_color};'>{estado}</b>"
        f"</p>",
        unsafe_allow_html=True,
    )

    # ── Métricas de resumen ───────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Artículos F9",   header["total_articulos"])
    c2.metric("Pares Iniciales", f"{header['total_pares']:,}")
    c3.metric("Vendido",         f"{header['total_vendido']:,}")
    c4.metric("Saldo disponible", f"{header['saldo']:,}",
              delta=f"{header['saldo']:,}" if header['saldo'] > 0 else None,
              delta_color="normal")

    # ── Datos complementarios ─────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)
    col_a.markdown(f"**Marcas:** {header['marcas']}")
    col_b.markdown(f"**IC Vinculada:** {header['ic_nro']}")
    col_c.markdown(f"**Fecha Promesa:** {_fmt_date(header.get('fecha_promesa'))}")

    if header.get("notas"):
        st.caption(f"📝 {header['notas']}")

    # ── Botón ENVIAR A COMPRA ─────────────────────────────────────────────────
    _render_enviar_a_compra(id_pp, header["numero_proforma"])

    st.divider()

    # ── Ala Norte — Drill-Up ─────────────────────────────────────────────────
    with st.expander(
        f"📦  Detalle de Importación (Stock Teórico)  —  {header['total_articulos']} artículos · {header['total_pares']:,} pares",
        expanded=False,
    ):
        st.caption("Catálogo de lo que está en camino. Snapshot fijo del F9 (compra_inicial).")
        _render_ala_norte(id_pp)

    # ── Ala Sur — Drill-Down ─────────────────────────────────────────────────
    with st.expander(
        f"🛒  Facturas Internas (Ventas Registradas)  —  {header['total_vendido']:,} pares · {round(header['total_vendido']/header['total_pares']*100,1) if header['total_pares'] else 0} % ejecutado",
        expanded=False,
    ):
        st.caption("Ventas en tránsito: consumo del stock antes del arribo.")
        _render_ala_sur(id_pp, estado)


def _render_enviar_a_compra(id_pp: int, numero_proforma: str):
    """
    Botón '📦 ENVIAR A COMPRA' en la cabecera del PP.
    Permite crear una Compra Legal nueva o agregar el PP a una existente
    (agrupando por número de Proforma).
    """
    from modules.compra_legal.logic import (
        pp_ya_en_compra, get_compras_por_proforma,
        create_compra_legal, add_pp_to_compra,
    )

    ya_en_compra = pp_ya_en_compra(id_pp)

    if ya_en_compra:
        st.markdown(
            f"<div style='background:#22C55E22;border:1px solid #22C55E;border-radius:8px;"
            f"padding:8px 16px;display:inline-block;color:#22C55E;font-size:.82rem;'>"
            f"📦 Este PP ya está en Compra Legal</div>",
            unsafe_allow_html=True,
        )
        return

    key_open = f"_pp_enviar_open_{id_pp}"

    if not st.session_state.get(key_open):
        if st.button(
            "📦  ENVIAR A COMPRA",
            key=f"pp_enviar_btn_{id_pp}",
            type="primary",
        ):
            st.session_state[key_open] = True
            st.rerun()
        return

    # ── Formulario de asignación ──────────────────────────────────────────────
    st.markdown(
        "<div style='background:#1C2E3F;border:1px solid #334155;"
        "border-radius:10px;padding:16px 20px;margin:8px 0;'>"
        "<b style='color:#D4AF37;'>📦 Enviar a Compra Legal</b></div>",
        unsafe_allow_html=True,
    )

    df_existentes = get_compras_por_proforma(numero_proforma)
    opts = ["🆕 Nueva Compra"]
    if not df_existentes.empty:
        for _, row in df_existentes.iterrows():
            opts.append(f"➕ {row['numero_registro']} ({row['pps_vinculados']}) [{row['estado']}]")

    sel = st.radio("Opción", opts, key=f"_pp_cl_opt_{id_pp}", label_visibility="collapsed")

    col_cancel, col_confirm = st.columns(2)
    if col_cancel.button("Cancelar", key=f"_pp_cl_cancel_{id_pp}", use_container_width=True):
        st.session_state.pop(key_open, None)
        st.rerun()

    if col_confirm.button("✔ Confirmar", key=f"_pp_cl_confirm_{id_pp}",
                          use_container_width=True, type="primary"):
        if sel == "🆕 Nueva Compra":
            ok, result = create_compra_legal(id_pp, numero_proforma)
        else:
            # Extraer el id de la fila correspondiente al label
            idx = opts.index(sel) - 1
            cl_id = int(df_existentes.iloc[idx]["id"])
            ok, result = add_pp_to_compra(cl_id, id_pp)

        if ok:
            st.success(f"✓ {result}")
            st.session_state.pop(key_open, None)
            st.rerun()
        else:
            st.error(result)


def _render_ala_norte(id_pp: int):
    df = get_pp_ala_norte(id_pp)

    if df.empty:
        st.info("Sin artículos registrados para este pedido.")
        return

    total_inicial = int(df["cantidad_inicial"].sum())
    total_vendido = int(df["vendido"].sum())
    total_saldo   = int(df["saldo"].sum())
    st.caption(
        f"{len(df)} artículos &nbsp;·&nbsp; "
        f"{total_inicial:,} pares iniciales &nbsp;·&nbsp; "
        f"{total_vendido:,} vendidos &nbsp;·&nbsp; "
        f"**{total_saldo:,} disponibles**"
    )

    # Resumen por marca
    if "marca" in df.columns and df["marca"].nunique() > 1:
        with st.expander("Ver resumen por marca", expanded=False):
            resumen = (
                df.groupby("marca")[["cantidad_inicial", "vendido", "saldo"]]
                  .sum()
                  .reset_index()
                  .rename(columns={
                      "marca": "Marca",
                      "cantidad_inicial": "Inicial",
                      "vendido": "Vendido",
                      "saldo": "Saldo",
                  })
            )
            st.dataframe(resumen, hide_index=True, use_container_width=False)

    # Tabla completa SKU
    display_cols = [
        "marca", "linea", "referencia", "material", "color", "grada",
        "t33", "t34", "t35", "t36", "t37", "t38", "t39", "t40",
        "cantidad_inicial", "vendido", "saldo",
    ]
    rename_map = {
        "marca": "Marca", "linea": "Línea", "referencia": "Ref.",
        "material": "Material", "color": "Color", "grada": "Grada",
        "t33": "33", "t34": "34", "t35": "35", "t36": "36",
        "t37": "37", "t38": "38", "t39": "39", "t40": "40",
        "cantidad_inicial": "Inicial", "vendido": "Vendido", "saldo": "Saldo",
    }
    cols_present = [c for c in display_cols if c in df.columns]

    st.dataframe(
        df[cols_present].rename(columns=rename_map),
        column_config={
            "Marca":    st.column_config.TextColumn(width=100),
            "Línea":    st.column_config.TextColumn(width=80),
            "Ref.":     st.column_config.TextColumn(width=90),
            "Material": st.column_config.TextColumn(width=120),
            "Color":    st.column_config.TextColumn(width=120),
            "Grada":    st.column_config.TextColumn(width=65),
            "33": st.column_config.NumberColumn(format="%d", width=48),
            "34": st.column_config.NumberColumn(format="%d", width=48),
            "35": st.column_config.NumberColumn(format="%d", width=48),
            "36": st.column_config.NumberColumn(format="%d", width=48),
            "37": st.column_config.NumberColumn(format="%d", width=48),
            "38": st.column_config.NumberColumn(format="%d", width=48),
            "39": st.column_config.NumberColumn(format="%d", width=48),
            "40": st.column_config.NumberColumn(format="%d", width=48),
            "Inicial": st.column_config.NumberColumn(format="%d", width=80),
            "Vendido": st.column_config.NumberColumn(format="%d", width=80),
            "Saldo":   st.column_config.NumberColumn(format="%d", width=80),
        },
        hide_index=True,
        use_container_width=True,
    )


def _render_ala_sur(id_pp: int, estado: str = "ABIERTO"):
    """
    Ala Sur — Auditoría de Facturas Internas + botón '➕ Nueva Factura'.
    Cuando estado == 'ENVIADO' la vista es solo lectura (bloqueada en COMPRA).
    Flujo de 2 fases:
      Fase A → Cliente, Plazo, Marca(s), Vendedor (opcional)
      Fase B → Grid de SKUs con cantidad de cajas (step = 1 caja)
    """
    df = get_ala_sur_facturas(id_pp)
    bloqueado = (estado == "ENVIADO")

    # ── Banner de bloqueo ─────────────────────────────────────────────────────
    if bloqueado:
        st.markdown(
            "<div style='background:#EF444422;border:1px solid #EF4444;"
            "border-radius:8px;padding:10px 16px;color:#EF4444;font-weight:600;"
            "margin-bottom:8px;'>"
            "🔒 Preventa transferida a Compra — solo lectura. "
            "Para editar, el encargado de Compra debe rechazar este PP.</div>",
            unsafe_allow_html=True,
        )

    # ── KPIs + botón "+" ─────────────────────────────────────────────────────
    if not df.empty:
        n_facturas = df["factura"].nunique()
        facturado  = int(df["pares"].sum())
        if bloqueado:
            col_f, col_n = st.columns(2)
        else:
            col_f, col_n, col_add = st.columns([3, 3, 2])
        col_f.metric("Pares Facturados",  f"{facturado:,}")
        col_n.metric("Facturas Internas", n_facturas)
    else:
        if not bloqueado:
            col_add = st.columns([1])[0]
        st.markdown(
            "<div style='color:#475569;font-size:.84rem;padding:4px 0 8px 0;'>"
            "Sin facturas internas registradas para este pedido.</div>",
            unsafe_allow_html=True,
        )

    if not bloqueado:
        if col_add.button("➕ Nueva Factura", key=f"_pp_fac_abrir_{id_pp}",
                          use_container_width=True, type="primary"):
            st.session_state[f"_pp_fac_open_{id_pp}"] = True
            st.session_state[f"_pp_fac_fase_{id_pp}"] = "A"
            st.rerun()

        # ── Formulario de creación (fases A / B) ─────────────────────────────
        if st.session_state.get(f"_pp_fac_open_{id_pp}"):
            st.divider()
            if st.session_state.get(f"_pp_fac_fase_{id_pp}") == "B":
                _render_fac_fase_b(id_pp)
            else:
                _render_fac_fase_a(id_pp)

    if df.empty:
        return

    # ── Acordeones de facturas existentes ────────────────────────────────────
    st.divider()
    grupos = df[["factura", "marca"]].drop_duplicates().values.tolist()

    for fac, marca in grupos:
        df_f     = df[(df["factura"] == fac) & (df["marca"] == marca)]
        fecha    = str(df_f["fecha"].iloc[0])[:10]
        cliente  = str(df_f["cliente"].iloc[0])
        vendedor = str(df_f["vendedor"].iloc[0])
        total_f  = int(df_f["pares"].sum())

        resumen = (
            f"🧾  {fac}"
            f"  |  {marca}"
            f"  |  Cliente: {cliente}"
            f"  |  Vendedor: {vendedor}"
            f"  |  {total_f:,} pares"
        )

        with st.expander(resumen, expanded=False):
            st.caption(f"Fecha: {fecha}")
            render_tabla_5pilares(df_f)


# ─────────────────────────────────────────────────────────────────────────────
# FASE A — Cabecera: Cliente · Plazo · Marca(s) · Vendedor (opcional)
# ─────────────────────────────────────────────────────────────────────────────

def _render_fac_fase_a(id_pp: int):
    st.markdown(
        "<div style='background:#1C2E3F;border:1px solid #334155;"
        "border-radius:10px;padding:18px 22px;margin-bottom:8px;'>"
        "<span style='color:#D4AF37;font-size:.95rem;font-weight:700;'>"
        "NUEVA FACTURA INTERNA — Cabecera</span></div>",
        unsafe_allow_html=True,
    )

    # ── Cliente ───────────────────────────────────────────────────────────────
    cod_raw = st.text_input(
        "Código de Cliente",
        key=f"_pp_cod_{id_pp}",
        placeholder="Ej: 1234",
        help="Ingresá el código numérico del cliente.",
    )
    nombre_cliente = None
    cod_valido     = False
    if cod_raw.strip():
        if cod_raw.strip().isdigit():
            nombre_cliente = buscar_cliente_pp(int(cod_raw.strip()))
            if nombre_cliente:
                st.success(f"✓  {nombre_cliente}")
                cod_valido = True
            else:
                st.warning("Cliente no encontrado en la base de datos.")
        else:
            st.warning("El código debe ser numérico.")

    # ── Plazo ─────────────────────────────────────────────────────────────────
    df_plazos   = get_plazos()
    opts_plazo  = dict(zip(df_plazos["descp_plazo"], df_plazos["id_plazo"]))
    sel_plazo   = st.selectbox("Plazo", list(opts_plazo.keys()), key=f"_pp_plazo_{id_pp}")
    id_plazo    = int(opts_plazo[sel_plazo])

    # ── Marca(s) del PP ───────────────────────────────────────────────────────
    df_marcas  = get_marcas_de_pp(id_pp)
    marca_opts = dict(zip(df_marcas["descp_marca"], df_marcas["id_marca"]))
    sel_marcas = st.multiselect(
        "Marca(s)",
        list(marca_opts.keys()),
        key=f"_pp_marcas_{id_pp}",
        help="Solo se muestran las marcas del PP abierto.",
    )
    id_marcas = [int(marca_opts[m]) for m in sel_marcas]

    # ── Vendedor (opcional) ───────────────────────────────────────────────────
    df_vend     = get_vendedores_pp()
    vend_opts   = {"(Sin asignar)": None}
    for _, v in df_vend.iterrows():
        vend_opts[str(v["descp_vendedor"])] = int(v["id_vendedor"])
    sel_vend    = st.selectbox("Vendedor", list(vend_opts.keys()), key=f"_pp_vend_{id_pp}")
    id_vendedor = vend_opts[sel_vend]

    st.divider()

    col_cancelar, col_siguiente = st.columns(2)
    if col_cancelar.button("Cancelar", key=f"_pp_fac_cancel_{id_pp}", use_container_width=True):
        for k in (f"_pp_fac_open_{id_pp}", f"_pp_fac_fase_{id_pp}",
                  f"_pp_fac_data_{id_pp}", f"_pp_fac_skus_{id_pp}"):
            st.session_state.pop(k, None)
        st.rerun()

    if col_siguiente.button("Siguiente →", key=f"_pp_fac_sig_{id_pp}",
                             use_container_width=True, type="primary"):
        if not cod_valido:
            st.error("Ingresá un código de cliente válido antes de continuar.")
        elif not id_marcas:
            st.error("Seleccioná al menos una marca.")
        else:
            df_skus = get_skus_por_marcas(id_pp, id_marcas)
            df_skus = df_skus[df_skus["saldo"] > 0]
            if df_skus.empty:
                st.error("No hay artículos con saldo disponible para las marcas seleccionadas.")
            else:
                st.session_state[f"_pp_fac_data_{id_pp}"] = {
                    "cod_cliente":    cod_raw.strip(),
                    "nombre_cliente": nombre_cliente,
                    "id_plazo":       id_plazo,
                    "plazo_label":    sel_plazo,
                    "id_marcas":      id_marcas,
                    "id_vendedor":    id_vendedor,
                    "vendedor_label": sel_vend,
                }
                st.session_state[f"_pp_fac_skus_{id_pp}"] = df_skus.to_dict("records")
                st.session_state[f"_pp_fac_fase_{id_pp}"] = "B"
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# FASE B — Selección de artículos (grid de cajas por SKU)
# ─────────────────────────────────────────────────────────────────────────────

def _render_fac_fase_b(id_pp: int):
    data = st.session_state.get(f"_pp_fac_data_{id_pp}", {})
    skus = st.session_state.get(f"_pp_fac_skus_{id_pp}", [])

    # ── Resumen de cabecera ───────────────────────────────────────────────────
    st.markdown(
        f"<div style='background:#1C2E3F;border:1px solid #334155;"
        f"border-radius:10px;padding:16px 22px;margin-bottom:8px;'>"
        f"<span style='color:#D4AF37;font-size:.95rem;font-weight:700;'>"
        f"NUEVA FACTURA INTERNA — Artículos</span>"
        f"<div style='color:#94A3B8;font-size:.82rem;margin-top:6px;'>"
        f"Cliente: <b style='color:#F1F5F9;'>{data.get('nombre_cliente')} "
        f"({data.get('cod_cliente')})</b>"
        f"&nbsp;·&nbsp;Plazo: <b style='color:#F1F5F9;'>{data.get('plazo_label')}</b>"
        f"&nbsp;·&nbsp;Vendedor: <b style='color:#F1F5F9;'>{data.get('vendedor_label')}</b>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    # Agrupar SKUs por marca para mostrar subencabezados
    marcas_en_skus = list(dict.fromkeys(s["marca"] for s in skus))

    with st.form(f"_pp_form_b_{id_pp}"):
        for marca in marcas_en_skus:
            st.markdown(f"**{marca}**")

            # Encabezado de columnas
            h = st.columns([1, 2, 2, 1, 1, 2])
            for col, lbl in zip(h, ["Línea", "Ref / Material", "Color", "Saldo", "p/Caja", "Pares"]):
                col.markdown(f"<span style='color:#64748B;font-size:.75rem;'>{lbl}</span>",
                             unsafe_allow_html=True)

            skus_m = [s for s in skus if s["marca"] == marca]
            for sku in skus_m:
                det_id       = int(sku["id"])
                # cantidad_cajas = Column U = pares por caja (directo del F9)
                pares_x_caja = max(int(sku.get("cantidad_cajas") or 1), 1)
                saldo        = int(sku.get("saldo", 0) or 0)

                c = st.columns([1, 2, 2, 1, 1, 2])
                c[0].caption(str(sku.get("linea", "—")))
                c[1].caption(f"{sku.get('referencia','—')} {sku.get('material','')}")
                c[2].caption(str(sku.get("color", "—")))
                c[3].caption(f"{saldo:,}")
                c[4].caption(f"{pares_x_caja}")
                c[5].number_input(
                    "Pares",
                    min_value=0,
                    max_value=saldo,
                    step=pares_x_caja,
                    value=0,
                    key=f"_pp_cajas_{id_pp}_{det_id}",
                    label_visibility="collapsed",
                )

            st.divider()

        col_back, _, col_save = st.columns([2, 3, 2])
        volver    = col_back.form_submit_button("← Volver",     use_container_width=True)
        submitted = col_save.form_submit_button("💾 Guardar",   use_container_width=True,
                                                type="primary")

    if volver:
        st.session_state[f"_pp_fac_fase_{id_pp}"] = "A"
        st.rerun()

    if submitted:
        # Recolectar items por marca; el widget ahora almacena pares
        marca_items: dict[int, list[dict]] = {}
        errores_validacion: list[str] = []

        for sku in skus:
            det_id       = int(sku["id"])
            id_marca     = int(sku["id_marca"])
            n_pares      = int(st.session_state.get(f"_pp_cajas_{id_pp}_{det_id}", 0))
            if n_pares <= 0:
                continue

            # cantidad_cajas = Column U = pares por caja (directo del F9)
            pares_x_caja = max(int(sku.get("cantidad_cajas") or 1), 1)

            # Forzar múltiplo de pares_x_caja (Columna U)
            if n_pares % pares_x_caja != 0:
                n_pares = ((n_pares // pares_x_caja) + 1) * pares_x_caja
                errores_validacion.append(
                    f"Línea {sku.get('linea','?')}: cantidad ajustada al múltiplo "
                    f"de {pares_x_caja} → {n_pares} pares."
                )

            n_cajas = n_pares // pares_x_caja
            marca_items.setdefault(id_marca, []).append(
                {"det_id": det_id, "n_cajas": n_cajas, "sku": sku}
            )

        for msg in errores_validacion:
            st.info(f"⚠ {msg}")

        if not marca_items:
            st.warning("Ingresá al menos 1 pack de pares en algún artículo.")
        else:
            errores  = []
            creadas  = []
            for id_marca, items in marca_items.items():
                ok, result = save_factura_manual(
                    id_pp       = id_pp,
                    id_marca    = id_marca,
                    cod_cliente = data["cod_cliente"],
                    id_plazo    = data["id_plazo"],
                    id_vendedor = data.get("id_vendedor"),
                    items       = items,
                )
                if ok:
                    creadas.append(result)
                else:
                    errores.append(result)

            for e in errores:
                st.error(e)

            if creadas:
                st.success(f"✓ {len(creadas)} factura(s) creada(s): {', '.join(creadas)}")
                for k in (f"_pp_fac_open_{id_pp}", f"_pp_fac_fase_{id_pp}",
                          f"_pp_fac_data_{id_pp}", f"_pp_fac_skus_{id_pp}"):
                    st.session_state.pop(k, None)
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# FORMULARIO — crear nuevo PP
# ─────────────────────────────────────────────────────────────────────────────

def _render_ic_card(saldo: dict):
    aprobados     = saldo.get("aprobados", 0)
    comprometidos = saldo.get("comprometidos", 0)
    disponible    = saldo.get("saldo", 0)
    pct           = int(comprometidos / aprobados * 100) if aprobados > 0 else 0
    eta_str       = _fmt_date(saldo.get("fecha_eta"))

    st.markdown(
        f"""<div style="background:#1C1F2E;border:1px solid #334155;
                border-radius:6px;padding:12px 16px;margin:6px 0 12px 0;">
            <span style="color:#94A3B8;font-size:0.75rem;">
                {saldo.get('numero_registro','—')} &nbsp;·&nbsp;
                {saldo.get('marca','—')} &nbsp;·&nbsp;
                Proveedor: {saldo.get('proveedor','—')} &nbsp;·&nbsp;
                ETA: {eta_str}
            </span>
            <div style="display:flex;gap:28px;margin-top:10px;flex-wrap:wrap;">
                <div>
                    <div style="color:#94A3B8;font-size:0.68rem;letter-spacing:.05em;">
                        PARES APROBADOS</div>
                    <div style="color:#F1F5F9;font-size:1.15rem;font-weight:700;">
                        {aprobados:,}</div>
                </div>
                <div>
                    <div style="color:#94A3B8;font-size:0.68rem;letter-spacing:.05em;">
                        COMPROMETIDOS</div>
                    <div style="color:#F59E0B;font-size:1.15rem;font-weight:700;">
                        {comprometidos:,}</div>
                </div>
                <div>
                    <div style="color:#94A3B8;font-size:0.68rem;letter-spacing:.05em;">
                        SALDO DISPONIBLE</div>
                    <div style="color:#22C55E;font-size:1.15rem;font-weight:700;">
                        {disponible:,}</div>
                </div>
                <div>
                    <div style="color:#94A3B8;font-size:0.68rem;letter-spacing:.05em;">
                        UTILIZADO</div>
                    <div style="color:#F1F5F9;font-size:1.15rem;font-weight:700;">
                        {pct}%</div>
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def _render_form():
    from datetime import date as _date

    st.markdown(
        "<h2 style='color:#D4AF37;margin-bottom:4px;'>📦 Nuevo Pedido Proveedor</h2>"
        "<p style='color:#94A3B8;margin-top:0;'>El número PP-YYYY-XXXX "
        "se asigna automáticamente al guardar.</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Paso 1: IC ────────────────────────────────────────────────────────────
    df_ics = get_intenciones_con_saldo()
    if df_ics.empty:
        st.info("No hay Intenciones de Compra con saldo disponible.")
        return

    opts_ic: dict[str, int] = {}
    for _, r in df_ics.iterrows():
        eta   = _fmt_date(r.get("fecha_eta"))
        label = (
            f"{r['numero_registro']}  |  {r['marca']}"
            f"  |  {int(r['saldo']):,} pares disp.  |  ETA: {eta}"
        )
        opts_ic[label] = int(r["id"])

    sel_ic_label = st.selectbox(
        "Intención de Compra",
        list(opts_ic.keys()),
        key="pp_ic_sel",
        help="Solo ICs con saldo disponible.",
    )
    id_ic = opts_ic[sel_ic_label]

    if st.session_state.get("_pp_last_ic") != id_ic:
        st.session_state["_pp_last_ic"] = id_ic
        for k in ("pp_parsed_df", "pp_parsed_total", "pp_parsed_error"):
            st.session_state.pop(k, None)

    saldo_info = get_ic_saldo(id_ic)
    if not saldo_info:
        st.error("No se pudo obtener el balance de la IC.")
        return

    _render_ic_card(saldo_info)

    # ── Paso 2: Datos del pedido ──────────────────────────────────────────────
    c1, c2, c3 = st.columns([2, 1, 1])
    numero_proforma = c1.text_input(
        "Número de Proforma",
        key="pp_proforma",
        placeholder="Ej: 45  |  3130  |  INV-2026-001",
    )
    fecha_pedido = c2.date_input("Fecha del Pedido", value=_date.today(), key="pp_fecha_ped")
    eta_ic       = saldo_info.get("fecha_eta")
    fecha_eta    = c3.date_input(
        "Fecha Promesa al cliente",
        value=eta_ic if eta_ic else None,
        key="pp_fecha_eta",
    )
    observaciones = st.text_input("Observaciones", key="pp_obs")

    st.divider()

    # ── Paso 3: F9 ───────────────────────────────────────────────────────────
    st.markdown("**Cargar F9 — extrae materiales, colores y gradaciones**")
    st.caption(
        f"Filtrará filas con Proforma = **{numero_proforma or '(ingresar)'}**"
        f" y Marca = **{saldo_info['id_marca']} — {saldo_info['marca']}**"
    )

    uploaded = st.file_uploader("Archivo F9 (.xlsx)", type=["xlsx"], key="pp_f9_upload")

    col_btn, _ = st.columns([1, 3])
    if col_btn.button(
        "🔍 Procesar F9",
        key="pp_procesar",
        disabled=(not uploaded or not numero_proforma),
    ):
        with st.spinner("Procesando F9..."):
            df_p, total_p, err_p = parse_f9(
                uploaded.getvalue(),
                numero_proforma.strip(),
                saldo_info["id_marca"],
            )
        st.session_state["pp_parsed_df"]    = df_p
        st.session_state["pp_parsed_total"] = total_p
        st.session_state["pp_parsed_error"] = err_p

    df_p    = st.session_state.get("pp_parsed_df")
    total_p = st.session_state.get("pp_parsed_total", 0)
    err_p   = st.session_state.get("pp_parsed_error")

    if err_p:
        st.error(err_p)
        return
    if df_p is None:
        return
    if df_p.empty:
        st.warning("El F9 procesado no devolvió filas.")
        return

    saldo_disp = saldo_info["saldo"]

    if total_p > saldo_disp:
        st.error(
            f"🚨 El F9 carga **{total_p:,} pares** pero el saldo de la IC es "
            f"**{saldo_disp:,}**. Excede en **{total_p - saldo_disp:,} pares**."
        )
        puede_registrar = False
    else:
        st.success(
            f"✅ **{total_p:,} pares** dentro del límite. "
            f"Saldo restante tras guardar: **{saldo_disp - total_p:,} pares**."
        )
        puede_registrar = True

    cols_preview = [c for c in [
        "linea", "referencia", "descp_material", "descp_color",
        "grada", "cantidad_cajas", "cantidad_pares",
    ] if c in df_p.columns]

    st.dataframe(
        df_p[cols_preview].rename(columns={
            "linea": "Línea", "referencia": "Referencia",
            "descp_material": "Material", "descp_color": "Color",
            "grada": "Grada", "cantidad_cajas": "Cajas", "cantidad_pares": "Pares",
        }),
        hide_index=True, use_container_width=True,
    )
    st.caption(
        f"{len(df_p)} artículos  |  {total_p:,} pares  "
        f"|  Proforma: {numero_proforma}  |  Marca: {saldo_info['marca']}"
    )

    if not puede_registrar or not numero_proforma:
        return

    _, col_reg = st.columns([3, 1])
    if col_reg.button(
        "🔒 REGISTRAR PP",
        type="primary",
        use_container_width=True,
        key="pp_submit",
    ):
        ok, resultado = save_pp(
            header={
                "id_intencion_compra":   id_ic,
                "id_proveedor":          saldo_info["id_proveedor"],
                "numero_proforma":       numero_proforma,
                "fecha_pedido":          fecha_pedido,
                "fecha_arribo_estimada": fecha_eta,
                "observaciones":         observaciones,
            },
            detalle_rows=df_p.to_dict("records"),
        )
        if ok:
            st.success(
                f"✅ **{resultado}** registrado — "
                f"{total_p:,} pares | {saldo_info['numero_registro']} | "
                f"Proforma {numero_proforma}"
            )
            for k in ("pp_parsed_df", "pp_parsed_total", "pp_parsed_error", "_pp_last_ic"):
                st.session_state.pop(k, None)
            st.session_state["pp_mostrar_form"] = False
            st.rerun()
        else:
            st.error(resultado)
