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
    get_datos_ics_de_pp,
    get_evento_precio_pp,
    get_precios_stock_pp,
    actualizar_eta_pp,
    desasignar_ic_de_pp,
    get_todos_eventos_precio,
    get_lista_precios_completa,
    parse_proforma,
    populate_pp_from_proforma,
    guardar_configuracion_pp,
    get_facturas_interna_de_pp,
    get_fi_detalles_canonico,
    get_skus_con_precio_para_fi,
    crear_factura_interna,
    registrar_arribo,
)
from core.fi_card import render_fi_card
from modules.pedido_proveedor.showroom import render_showroom
from modules.rimec_engine.hiedra import extraer_valor_numerico_talla


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_date(val) -> str:
    if val is None:
        return "—"
    try:
        if pd.isnull(val):
            return "—"
    except Exception:
        pass
    s = str(val).strip()
    if s in ("", "None", "NaT", "nan", "NaN", "NULL"):
        return "—"
    try:
        return s[:10]
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
    if fecha is None:
        return "Sin fecha"
    try:
        if pd.isnull(fecha):          # atrapa NaT, NaN y None
            return "Sin fecha"
    except Exception:
        pass
    s = str(fecha).strip()
    if s in ("", "None", "NaT", "nan", "NaN", "NULL"):
        return "Sin fecha"
    try:
        dt  = pd.to_datetime(fecha, errors="coerce")
        if pd.isnull(dt):
            return "Sin fecha"
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

    def _si(v):
        try:
            if v is None or (isinstance(v, float) and pd.isna(v)): return 0
            s = str(v).strip()
            return 0 if s in ("", "None", "nan") else int(float(s))
        except Exception: return 0

    df["_fecha_eta_dt"] = pd.to_datetime(df["fecha_eta"], errors="coerce")
    df = df.sort_values("_fecha_eta_dt", ascending=True, na_position="last")
    df["quincena_label"] = df["fecha_eta"].apply(_quincena_label)
    quincenas = list(dict.fromkeys(df["quincena_label"].tolist()))

    for quincena in quincenas:
        df_q       = df[df["quincena_label"] == quincena]
        total_ini  = int(df_q["pares_comprometidos"].fillna(0).apply(_si).sum())
        total_vend = int(df_q["total_vendido"].fillna(0).apply(_si).sum())
        pct_q      = round(total_vend / total_ini * 100, 1) if total_ini > 0 else 0.0
        n_pps      = len(df_q)

        exp_label = (
            f"📅  {quincena}"
            f"  —  {n_pps} preventa{'s' if n_pps != 1 else ''}"
            f"  ·  {total_ini:,} pares"
            f"  ·  {pct_q} % ejecutado"
        )

        with st.expander(exp_label, expanded=False):
            # Encabezado de columnas
            h = st.columns([3, 2, 1.5, 1.5, 2.2])
            for col, lbl in zip(h, ["Pedido / Marcas", "ETA · Cliente", "Pares", "Estado", "Acceso rápido"]):
                col.markdown(
                    f"<span style='color:#64748B;font-size:.72rem;"
                    f"letter-spacing:.06em;text-transform:uppercase;'>{lbl}</span>",
                    unsafe_allow_html=True,
                )
            st.divider()

            for _, pp in df_q.iterrows():
                ini    = _si(pp["pares_comprometidos"])
                vend   = _si(pp["total_vendido"])
                estado = str(pp["estado"])
                estado_color = _ESTADO_COLOR.get(estado, "#94A3B8")

                marcas_val   = str(pp.get("marcas", "—") or "—")
                proforma_val = str(pp.get("numero_proforma") or "—")
                cliente_val  = str(pp.get("cliente",  "—") or "—")
                vendedor_val = str(pp.get("vendedor", "—") or "—")
                eta_val      = _fmt_date(pp.get("fecha_eta"))

                col_info, col_eta, col_pares, col_estado, col_btn = st.columns([3, 2, 1.5, 1.5, 2.2])

                with col_info:
                    st.markdown(
                        f"<div style='line-height:1.4;'>"
                        f"<span style='font-weight:700;color:#F1F5F9;font-size:.9rem;'>"
                        f"{pp['numero_registro']}</span>"
                        f"<span style='color:#64748B;font-size:.78rem;'> · {marcas_val}</span><br>"
                        f"<span style='color:#D4AF37;font-size:.75rem;'>{cliente_val}</span>"
                        f"<span style='color:#475569;font-size:.72rem;'> · {vendedor_val}</span><br>"
                        f"<span style='color:#475569;font-size:.68rem;'>Proforma {proforma_val}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                with col_eta:
                    # ETA — semáforo por urgencia
                    from datetime import date as _d_hoy
                    _eta_color = "#64748B"
                    dias: int | None = None
                    _raw_eta = pp.get("fecha_eta")
                    _eta_es_valida = (
                        _raw_eta is not None
                        and str(_raw_eta).strip() not in ("", "None", "NaT", "nan", "NaN", "NULL")
                    )
                    if _eta_es_valida:
                        try:
                            _dt = pd.to_datetime(_raw_eta, errors="coerce")
                            if _dt is not pd.NaT and not pd.isnull(_dt):
                                dias = (_dt.date() - _d_hoy.today()).days
                                if dias < 0:
                                    _eta_color = "#EF4444"
                                elif dias <= 15:
                                    _eta_color = "#F59E0B"
                                else:
                                    _eta_color = "#22C55E"
                        except Exception:
                            dias = None

                    dias_str = f"<br><span style='color:#94A3B8;font-size:.7rem;'>{dias} días</span>" if dias is not None else ""
                    st.markdown(
                        f"<div style='line-height:1.5;'>"
                        f"<span style='color:{_eta_color};font-size:.88rem;font-weight:700;'>"
                        f"📅 {eta_val}</span>{dias_str}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    # Botón para editar ETA inline
                    key_edit = f"_eta_edit_{int(pp['id'])}"
                    if st.button("✏ ETA", key=f"_eta_btn_{int(pp['id'])}", help="Editar fecha ETA"):
                        st.session_state[key_edit] = True
                    if st.session_state.get(key_edit):
                        _val_default = _d_hoy.today()
                        if _eta_es_valida:
                            try:
                                _dt2 = pd.to_datetime(_raw_eta, errors="coerce")
                                if _dt2 is not pd.NaT and not pd.isnull(_dt2):
                                    _val_default = _dt2.date()
                            except Exception:
                                pass
                        nueva_eta = st.date_input(
                            "Nueva ETA", value=_val_default,
                            key=f"_eta_val_{int(pp['id'])}",
                            label_visibility="collapsed",
                        )
                        c_ok, c_no = st.columns(2)
                        if c_ok.button("✓", key=f"_eta_ok_{int(pp['id'])}", type="primary"):
                            if actualizar_eta_pp(int(pp["id"]), nueva_eta):
                                st.session_state.pop(key_edit, None)
                                st.rerun()
                        if c_no.button("✗", key=f"_eta_no_{int(pp['id'])}"):
                            st.session_state.pop(key_edit, None)
                            st.rerun()

                with col_pares:
                    st.markdown(
                        f"<div style='text-align:center;'>"
                        f"<div style='color:#F1F5F9;font-size:1rem;font-weight:700;'>{ini:,}</div>"
                        f"<div style='color:#64748B;font-size:.68rem;'>{vend:,} vend.</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                with col_estado:
                    st.markdown(
                        f"<span style='background:{estado_color}22;color:{estado_color};"
                        f"font-size:.72rem;font-weight:600;padding:3px 8px;"
                        f"border-radius:4px;'>{estado}</span>",
                        unsafe_allow_html=True,
                    )

                with col_btn:
                    # Fila 1: Botón principal Abrir
                    if st.button("Abrir →", key=f"pp_open_{pp['id']}",
                                 use_container_width=True, type="primary"):
                        st.session_state["pp_selected_id"] = int(pp["id"])
                        st.session_state.pop("tab_activa", None)
                        st.rerun()
                    # Fila 2: Accesos directos a pestañas
                    _b1, _b2, _b3 = st.columns(3)
                    if _b1.button("📋", key=f"pp_tab_ic_{pp['id']}",
                                  help="ICs Asignadas", use_container_width=True):
                        st.session_state["pp_selected_id"] = int(pp["id"])
                        st.session_state["tab_activa"] = "hijo_adoptado"
                        st.rerun()
                    if _b2.button("📦", key=f"pp_tab_stock_{pp['id']}",
                                  help="Importación / Stock", use_container_width=True):
                        st.session_state["pp_selected_id"] = int(pp["id"])
                        st.session_state["tab_activa"] = "hijo_mayor"
                        st.rerun()
                    if _b3.button("🧾", key=f"pp_tab_fi_{pp['id']}",
                                  help="Facturas Internas", use_container_width=True):
                        st.session_state["pp_selected_id"] = int(pp["id"])
                        st.session_state["tab_activa"] = "hijo_menor"
                        st.rerun()

                st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# CARGAR PROFORMA — reemplaza F9 para PPs creados por Digitación
# ─────────────────────────────────────────────────────────────────────────────

def _mostrar_exito_importacion(resultado: dict, pp_id: int) -> None:
    """Pantalla de éxito post-importación — imposible de ignorar."""
    st.balloons()
    st.success("✅ ¡Importación completada con éxito!")

    col1, col2, col3 = st.columns(3)
    col1.metric("Artículos importados", resultado["total_articulos"])
    col2.metric("Pares en tránsito",    f"{resultado['total_pares']:,}")
    col3.metric("FOB total (USD)",      f"{resultado['total_fob']:,.2f}")

    st.info(
        f"📦 **{resultado['total_pares']:,} pares** ya forman parte "
        f"de tu stock en tránsito bajo el **{resultado['pp_nro']}**.\n\n"
        "Podés verlos ahora en la pestaña **Importación / Stock** "
        "y comenzar a crear facturas internas."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📋 Ver stock importado", type="primary",
                     key=f"_exito_stock_{pp_id}", use_container_width=True):
            st.session_state[f"_pf_exito_{pp_id}"] = None
            st.session_state["tab_activa"] = "hijo_mayor"
            st.rerun()
    with col_b:
        if st.button("🧾 Crear primera factura interna",
                     key=f"_exito_fac_{pp_id}", use_container_width=True):
            st.session_state[f"_pf_exito_{pp_id}"] = None
            st.session_state["tab_activa"] = "hijo_menor"
            st.rerun()


def _render_importar_proforma(pp_id: int):
    """
    Carga la Fatura Proforma del proveedor en un PP vacío (creado por Digitación).
    Captura: proforma, nro pedido externo, descuentos comerciales escalados, ETA.
    Los precios FOB se almacenan como referencia; el precio de venta viene
    del evento de precio (rimec_engine). La comparación con la invoice se
    hace en el módulo Compra.
    """
    # ── Pantalla de éxito post-importación ───────────────────────────────────
    exito = st.session_state.get(f"_pf_exito_{pp_id}")
    if exito is not None:
        _mostrar_exito_importacion(exito, pp_id)
        return

    df_ics = get_datos_ics_de_pp(pp_id)

    st.markdown(
        "<div style='background:#1C2E3F;border:1px solid #D4AF37;"
        "border-radius:10px;padding:16px 22px;margin:8px 0 16px 0;'>"
        "<span style='color:#D4AF37;font-size:.95rem;font-weight:700;'>"
        "📤 Cargar Proforma — este PP aún no tiene artículos registrados</span><br>"
        "<span style='color:#94A3B8;font-size:.82rem;'>"
        "Cargá la Fatura Proforma del proveedor (.xls/.xlsx). "
        "Los precios FOB son referencia contable; el precio de venta "
        "lo define la lista de precios asignada.</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    if df_ics.empty:
        st.warning("Este PP no tiene ICs asignadas. Contactá a Digitación.")
        return

    # ── ICs vinculadas ────────────────────────────────────────────────────────
    pares_limite = int(df_ics["pares"].fillna(0).sum())
    ic_ref       = df_ics.iloc[0]
    categoria_id = int(ic_ref["categoria_id"]) if ic_ref.get("categoria_id") is not None else None

    with st.expander("📋 ICs vinculadas a este PP", expanded=False):
        for _, ic in df_ics.iterrows():
            st.markdown(
                f"**{ic['nro_ic']}** · {ic['marca']} · "
                f"{int(ic['pares']):,} pares aprobados · "
                f"Fábrica: `{ic.get('nro_pedido_fabrica','—')}`"
            )
    st.caption(f"Límite total autorizado: **{pares_limite:,} pares**")

    st.divider()

    # ── BLOQUE 1: Cabecera comercial ─────────────────────────────────────────
    st.markdown("#### 1 · Cabecera comercial")

    col_pf, col_ext, col_eta = st.columns(3)
    proforma = col_pf.text_input(
        "Nro Proforma *",
        key=f"_pf_pf_{pp_id}",
        placeholder="Ej: 6421",
        help="Campo obligatorio. Sin este número el sistema no puede guardar la proforma.",
    )
    nro_externo = col_ext.text_input(
        "Nro PP externo (sistema legado)",
        key=f"_pf_ext_{pp_id}",
        placeholder="Ej: PP-654-2026-001",
        help="Número en el sistema RIMEC actual. Solo referencia.",
    )
    from datetime import date as _date
    fecha_eta = col_eta.date_input(
        "Fecha ETA",
        value=None,
        key=f"_pf_eta_{pp_id}",
    )

    st.divider()

    # ── BLOQUE 2: Descuentos comerciales escalados ────────────────────────────
    st.markdown("#### 2 · Descuentos comerciales escalados")
    st.caption(
        "Se aplican en cascada sobre el precio FOB unitario. "
        "Ej: D1=18% + D2=6% → precio × (1−0.18) × (1−0.06). "
        "Solo se almacenan y muestran aquí; no afectan el precio de venta."
    )

    dc1, dc2, dc3, dc4 = st.columns(4)
    d1 = dc1.number_input("Descuento 1 (%)", min_value=0.0, max_value=100.0,
                          value=0.0, step=0.5, format="%.2f",
                          key=f"_pf_d1_{pp_id}") / 100
    d2 = dc2.number_input("Descuento 2 (%)", min_value=0.0, max_value=100.0,
                          value=0.0, step=0.5, format="%.2f",
                          key=f"_pf_d2_{pp_id}") / 100
    d3 = dc3.number_input("Descuento 3 (%)", min_value=0.0, max_value=100.0,
                          value=0.0, step=0.5, format="%.2f",
                          key=f"_pf_d3_{pp_id}") / 100
    d4 = dc4.number_input("Descuento 4 (%)", min_value=0.0, max_value=100.0,
                          value=0.0, step=0.5, format="%.2f",
                          key=f"_pf_d4_{pp_id}") / 100

    # Preview del efecto de descuentos
    if any(x > 0 for x in (d1, d2, d3, d4)):
        factor = 1.0
        pasos  = []
        for i, d in enumerate((d1, d2, d3, d4), 1):
            if d > 0:
                factor *= (1 - d)
                pasos.append(f"×(1−{d*100:.1f}%)")
        st.markdown(
            f"<div style='background:#0F1E2F;border-radius:6px;padding:8px 14px;"
            f"color:#D4AF37;font-size:.85rem;'>"
            f"Factor neto: {' '.join(pasos)} = <b>{factor:.6f}</b> "
            f"→ sobre USD 100 = <b>USD {100*factor:.2f}</b></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── BLOQUE 3: Archivo proforma ────────────────────────────────────────────
    st.markdown("#### 3 · Fatura Proforma del proveedor")
    uploaded = st.file_uploader(
        "Archivo proforma (.xls o .xlsx)",
        type=["xls", "xlsx"],
        key=f"_pf_file_{pp_id}",
    )

    col_proc, _ = st.columns([1, 3])
    if col_proc.button(
        "🔍 Procesar Proforma",
        key=f"_pf_proc_{pp_id}",
        disabled=not uploaded,
    ):
        with st.spinner("Analizando proforma..."):
            df_p, total_p, err_p = parse_proforma(uploaded.getvalue())
        st.session_state[f"_pf_df_{pp_id}"]  = df_p
        st.session_state[f"_pf_tot_{pp_id}"] = total_p
        st.session_state[f"_pf_err_{pp_id}"] = err_p

    df_p    = st.session_state.get(f"_pf_df_{pp_id}")
    total_p = st.session_state.get(f"_pf_tot_{pp_id}", 0)
    err_p   = st.session_state.get(f"_pf_err_{pp_id}")

    if err_p:
        st.error(err_p)
        return
    if df_p is None:
        return
    if df_p.empty:
        st.warning("La proforma no devolvió artículos. Verificá el archivo.")
        return

    # ── Preview ───────────────────────────────────────────────────────────────
    if total_p > pares_limite:
        st.error(
            f"🚨 La proforma tiene **{total_p:,} pares** pero el límite autorizado "
            f"es **{pares_limite:,}** — excede en **{total_p - pares_limite:,} pares**."
        )
        puede_guardar = False
    else:
        st.success(f"✅ **{total_p:,} pares** dentro del límite de {pares_limite:,}.")
        puede_guardar = True

    # Preview — 5 pilares + datos comerciales
    def _fob_aj(fob):
        r = float(fob)
        for d in (d1, d2, d3, d4):
            if d > 0: r *= (1 - d)
        return round(r, 4)

    df_prev = df_p[["brand", "linea_cod", "ref_cod", "name",
                    "material_code", "material", "color_code", "color",
                    "boxes", "pairs", "unit_fob", "grade_range"]].copy()
    df_prev["fob_ajustado"] = df_prev["unit_fob"].apply(_fob_aj)
    df_prev = df_prev.rename(columns={
        "brand":        "Marca",
        "linea_cod":    "Línea",
        "ref_cod":      "Ref.",
        "name":         "Descripción",
        "material_code":"Cód.Mat",
        "material":     "Material",
        "color_code":   "Cód.Col",
        "color":        "Color",
        "boxes":        "Cajas",
        "pairs":        "Pares",
        "unit_fob":     "FOB USD",
        "fob_ajustado": "FOB Ajustado",
        "grade_range":  "Tallas",
    })

    st.dataframe(
        df_prev,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Marca":        st.column_config.TextColumn(width=80),
            "Línea":        st.column_config.TextColumn(width=55),
            "Ref.":         st.column_config.TextColumn(width=45),
            "Descripción":  st.column_config.TextColumn(width=160),
            "Cód.Mat":      st.column_config.TextColumn(width=60),
            "Material":     st.column_config.TextColumn(width=170),
            "Cód.Col":      st.column_config.TextColumn(width=60),
            "Color":        st.column_config.TextColumn(width=130),
            "Cajas":        st.column_config.NumberColumn(format="%d", width=55),
            "Pares":        st.column_config.NumberColumn(format="%d", width=55),
            "FOB USD":      st.column_config.NumberColumn(format="$%.4f", width=80),
            "FOB Ajustado": st.column_config.NumberColumn(format="$%.4f", width=85),
            "Tallas":       st.column_config.TextColumn(width=60),
        },
    )
    st.caption(
        f"{len(df_p)} SKUs · {total_p:,} pares · "
        f"Marcas: {', '.join(sorted(df_p['brand'].unique()))}"
    )

    # ── Checklist visible: que se vea SIEMPRE qué falta para habilitar guardar
    st.divider()
    st.markdown("#### 4 · Confirmar carga")

    faltantes: list[str] = []
    if not proforma:
        faltantes.append("**Nro Proforma** (bloque 1)")
    if not puede_guardar:
        faltantes.append("**Reducir pares** al límite autorizado")

    col_info, col_ok = st.columns([3, 1])
    with col_info:
        if faltantes:
            st.warning(
                "⚠ No se puede cargar la proforma todavía. Falta completar:\n\n- "
                + "\n- ".join(faltantes)
            )
        else:
            st.success(
                f"✅ Todo listo para guardar **{total_p:,} pares** "
                f"({len(df_p)} SKUs) en `pedido_proveedor_detalle`."
            )

    if col_ok.button(
        "🔒 CARGAR PROFORMA",
        type="primary",
        use_container_width=True,
        disabled=bool(faltantes),
        key=f"_pf_ok_{pp_id}",
    ):
        articulos  = df_p.to_dict("records")
        total_arts = len(articulos)
        total_fob  = round(sum(float(r.get("amount_fob", 0)) for r in articulos), 2)

        # ── Barra de progreso visual ──────────────────────────────────────
        barra = st.progress(0, text="Iniciando importación...")
        for i, art in enumerate(articulos):
            pct = int((i + 1) / total_arts * 100)
            barra.progress(
                pct,
                text=f"Preparando artículo {i+1} de {total_arts} — "
                     f"L{art.get('linea_cod','')}.{art.get('ref_cod','')}",
            )
        barra.empty()

        # ── Insert real ───────────────────────────────────────────────────
        with st.spinner(f"Guardando {total_arts} artículos en la base de datos..."):
            ok, msg = populate_pp_from_proforma(
                pp_id        = pp_id,
                proforma     = proforma,
                nro_externo  = nro_externo,
                descuento_1  = d1,
                descuento_2  = d2,
                descuento_3  = d3,
                descuento_4  = d4,
                fecha_eta    = fecha_eta,
                categoria_id = categoria_id,
                detalle_rows = articulos,
            )

        if ok:
            for k in (f"_pf_df_{pp_id}", f"_pf_tot_{pp_id}", f"_pf_err_{pp_id}"):
                st.session_state.pop(k, None)
            header_pp = get_pp_header(pp_id)
            st.session_state[f"_pf_exito_{pp_id}"] = {
                "total_articulos": total_arts,
                "total_pares":     total_p,
                "total_fob":       total_fob,
                "pp_id":           pp_id,
                "pp_nro":          header_pp.get("numero_registro", f"PP-{pp_id}") if header_pp else f"PP-{pp_id}",
            }
            st.rerun()
        else:
            st.error(msg)


# ─────────────────────────────────────────────────────────────────────────────
# VISTA DETALLE — Contenedor con 3 Hijos
# ─────────────────────────────────────────────────────────────────────────────

def _render_detalle_pp(id_pp: int):
    header = get_pp_header(id_pp)
    if not header:
        st.error(f"Pedido Proveedor ID {id_pp} no encontrado.")
        return

    estado       = header["estado"]
    estado_color = _ESTADO_COLOR.get(estado, "#F1F5F9")

    # ── Botón volver ─────────────────────────────────────────────────────────
    if st.button("← Volver a la lista", key="pp_volver"):
        st.session_state.pop("pp_selected_id", None)
        st.session_state.pop(f"_pp_tab_{id_pp}", None)
        st.rerun()

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

    # ── Cabecera: Cliente · Vendedor · ETA · Estado digitación ───────────────
    st.markdown(
        f"<div style='background:#0F1E2F;border:1px solid #334155;border-radius:8px;"
        f"padding:8px 16px;margin-bottom:12px;display:flex;gap:24px;flex-wrap:wrap;'>"
        f"<div><span style='color:#64748B;font-size:.68rem;text-transform:uppercase;'>"
        f"Cliente</span><br>"
        f"<span style='color:#D4AF37;font-weight:600;'>{header.get('cliente','—')}</span></div>"
        f"<div><span style='color:#64748B;font-size:.68rem;text-transform:uppercase;'>"
        f"Vendedor</span><br>"
        f"<span style='color:#D4AF37;font-weight:600;'>{header.get('vendedor','—')}</span></div>"
        f"<div><span style='color:#64748B;font-size:.68rem;text-transform:uppercase;'>"
        f"ETA</span><br>"
        f"<span style='color:#F1F5F9;'>{_fmt_date(header.get('fecha_promesa'))}</span></div>"
        f"<div><span style='color:#64748B;font-size:.68rem;text-transform:uppercase;'>"
        f"Marcas</span><br>"
        f"<span style='color:#F1F5F9;'>{header.get('marcas','—')}</span></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Métricas de resumen ───────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Artículos F9",    header["total_articulos"])
    c2.metric("Pares Iniciales", f"{header['total_pares']:,}")
    c3.metric("Vendido",         f"{header['total_vendido']:,}")
    c4.metric("Saldo disponible", f"{header['saldo']:,}",
              delta=f"{header['saldo']:,}" if header['saldo'] > 0 else None,
              delta_color="normal")

    st.divider()

    # ── 3 HIJOS — tabs manuales controlados por session_state ────────────────
    tiene_stock = header["total_articulos"] > 0
    label_menor = "🧾 Facturas Internas" if tiene_stock else "🔒 Facturas Internas"

    # Clave de pestaña activa para este PP específico
    _key_tab = f"_pp_tab_{id_pp}"

    # Si viene un acceso directo desde la lista, lo aplicamos y limpiamos
    _nav = st.session_state.pop("tab_activa", None)
    if _nav is not None:
        st.session_state[_key_tab] = _nav

    # Valor actual (default: hijo_adoptado)
    _activa = st.session_state.get(_key_tab, "hijo_adoptado")

    # ── Barra de pestañas manual ──────────────────────────────────────────────
    _TABS = [
        ("hijo_adoptado", "📋 ICs Asignadas"),
        ("hijo_mayor",    "📦 Importación / Stock"),
        ("hijo_menor",    label_menor),
    ]

    _tab_cols = st.columns(len(_TABS))
    for _col, (_key, _label) in zip(_tab_cols, _TABS):
        _es_activa = (_activa == _key)
        if _es_activa:
            # Tab activa: HTML estilizado, no es un botón (ya estás aquí)
            _col.markdown(
                f"<div style='"
                f"background:#1E3A5F;"
                f"color:#D4AF37;"
                f"border:1px solid #D4AF37;"
                f"border-radius:6px;"
                f"padding:6px 12px;"
                f"font-weight:700;"
                f"font-size:.88rem;"
                f"text-align:center;"
                f"cursor:default;"
                f"'>{_label}</div>",
                unsafe_allow_html=True,
            )
        else:
            # Tab inactiva: botón clickeable normal
            if _col.button(
                _label,
                key=f"_tab_btn_{id_pp}_{_key}",
                use_container_width=True,
            ):
                st.session_state[_key_tab] = _key
                st.rerun()

    st.markdown(
        "<div style='border-bottom:1px solid #334155;margin:4px 0 16px 0;'></div>",
        unsafe_allow_html=True,
    )


    # ── Contenido de la pestaña activa ────────────────────────────────────────
    if _activa == "hijo_adoptado":
        _render_hijo_adoptado(id_pp)
    elif _activa == "hijo_mayor":
        _render_hijo_mayor(id_pp, header)
    else:
        _render_hijo_menor(id_pp, tiene_stock, header)


# ─────────────────────────────────────────────────────────────────────────────
# HIJO ADOPTADO — ICs asignadas vía tabla puente
# ─────────────────────────────────────────────────────────────────────────────

def _render_hijo_adoptado(pp_id: int):
    st.subheader("Intenciones de Compra asignadas")
    st.caption("Las ICs se asignan desde el módulo de Digitación.")

    df_ics = get_datos_ics_de_pp(pp_id)

    if df_ics.empty:
        st.info("No hay ICs asignadas a este PP todavía.")
        return

    total_pares = int(df_ics["pares"].fillna(0).sum()) if "pares" in df_ics.columns else 0

    col1, col2 = st.columns(2)
    col1.metric("ICs asignadas", len(df_ics))
    col2.metric("Total pares", f"{total_pares:,}")

    st.divider()

    h = st.columns([2, 2, 1.5, 2.5, 1.5, 1])
    for col, lbl in zip(h, ["NRO IC", "Marca", "Pares", "Nro Fábrica", "ETA", ""]):
        col.markdown(
            f"<span style='color:#64748B;font-size:.72rem;text-transform:uppercase;'>{lbl}</span>",
            unsafe_allow_html=True,
        )

    for _, ic in df_ics.iterrows():
        pares_ic = int(ic["pares"]) if ic.get("pares") is not None else 0
        eta_ic   = str(ic.get("eta", "—") or "—")[:10]
        ic_id    = int(ic["ic_id"]) if "ic_id" in ic.index else None

        c = st.columns([2, 2, 1.5, 2.5, 1.5, 1])
        c[0].markdown(f"**{ic.get('nro_ic','—')}**")
        c[1].write(ic.get("marca", "—"))
        c[2].write(f"{pares_ic:,}")
        c[3].caption(str(ic.get("nro_pedido_fabrica", "—")))
        c[4].caption(eta_ic)

        # Botón desasignar — solo si tenemos el ic_id
        if ic_id:
            key_confirm = f"_desasig_confirm_{pp_id}_{ic_id}"
            if st.session_state.get(key_confirm):
                with c[5]:
                    st.markdown(
                        "<span style='color:#EF4444;font-size:.72rem;font-weight:600;'>"
                        "¿Confirmar?</span>",
                        unsafe_allow_html=True,
                    )
                col_si, col_no = st.columns(2)
                if col_si.button("Sí", key=f"_desasig_si_{pp_id}_{ic_id}", type="primary"):
                    if desasignar_ic_de_pp(ic_id, pp_id):
                        st.session_state.pop(key_confirm, None)
                        st.success(f"IC {ic.get('nro_ic')} devuelta al pool de Digitación.")
                        st.rerun()
                    else:
                        st.error("Error al desasignar. Revisar logs.")
                if col_no.button("No", key=f"_desasig_no_{pp_id}_{ic_id}"):
                    st.session_state.pop(key_confirm, None)
                    st.rerun()
            else:
                if c[5].button("⬆ Mover", key=f"_desasig_btn_{pp_id}_{ic_id}",
                               help="Quitar esta IC del PP y devolverla al pool de Digitación"):
                    st.session_state[key_confirm] = True
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# HIJO MAYOR — Importación / Stock + Precios LPN/LPC
# ─────────────────────────────────────────────────────────────────────────────

def _render_hijo_mayor(pp_id: int, header: dict):
    tiene_stock = header["total_articulos"] > 0

    if not tiene_stock:
        _render_importar_proforma(pp_id)
        _render_explorador_precios(pp_id)
        return

    # Detalle de importación existente
    st.subheader(
        f"Detalle de Importación — {header['total_articulos']} artículos · "
        f"{header['total_pares']:,} pares"
    )
    st.caption("Snapshot fijo del F9 (compra_inicial).")
    _render_ala_norte(pp_id)

    st.divider()

    # Precios LPN / LPC del evento vigente
    evento_id = get_evento_precio_pp(pp_id)

    def _fmt_p(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
        try: return f"{float(v):,.0f}"
        except: return "—"

    if evento_id:
        df_precios = get_precios_stock_pp(pp_id, evento_id)
        if not df_precios.empty:
            st.subheader("Precios de este stock")
            sin_precio = df_precios["lpn"].isna().sum()
            if sin_precio > 0:
                st.warning(
                    f"⚠ {sin_precio} artículos sin precio en el evento {evento_id}. "
                    "Verificar que el listado de precios incluye estas líneas/materiales."
                )
            st.caption(
                f"Evento de precio ID **{evento_id}** · heredado de las ICs asignadas. "
                f"Columna **Caso** = fórmula exacta aplicada."
            )

            headers = ["Línea", "Ref.", "Cód.Mat", "Material", "Disp.",
                       "LPN", "LPC02", "LPC03", "LPC04", "Caso aplicado", "Dólar", "Índice"]
            widths  = [0.7, 0.7, 0.8, 2.0, 0.7, 1.2, 1.2, 1.2, 1.2, 2.2, 1.0, 1.0]
            h = st.columns(widths)
            for col, lbl in zip(h, headers):
                col.markdown(
                    f"<span style='color:#64748B;font-size:.68rem;"
                    f"text-transform:uppercase;'>{lbl}</span>",
                    unsafe_allow_html=True,
                )

            for _, row in df_precios.iterrows():
                disp = int(row.get("saldo", 0) or 0)
                has_price = row.get("lpn") is not None
                c = st.columns(widths)
                c[0].write(str(row.get("linea_codigo", "—")))
                c[1].write(str(row.get("referencia_codigo", "—")))
                c[2].write(str(row.get("cod_material", "—")))
                c[3].write(str(row.get("material", "—")))
                c[4].write(f"{disp:,}")
                c[5].markdown(
                    f"<span style='color:{'#22C55E' if has_price else '#EF4444'};"
                    f"font-weight:700;'>{_fmt_p(row.get('lpn'))}</span>",
                    unsafe_allow_html=True,
                )
                c[6].write(_fmt_p(row.get("lpc02")))
                c[7].write(_fmt_p(row.get("lpc03")))
                c[8].write(_fmt_p(row.get("lpc04")))
                c[9].caption(str(row.get("caso_precio") or "—"))
                c[10].caption(_fmt_p(row.get("dolar_aplicado")))
                c[11].caption(_fmt_p(row.get("indice_aplicado")))

    st.divider()
    _render_explorador_precios(pp_id)


# ─────────────────────────────────────────────────────────────────────────────
# EXPLORADOR DE LISTAS DE PRECIOS — mapa forense de eventos y casos
# ─────────────────────────────────────────────────────────────────────────────

def _render_explorador_precios(pp_id: int):
    """
    Desplegable para explorar cualquier lista de precios del sistema.
    Muestra LPN / LPC02-04 + caso aplicado + índice + dólar para cada
    referencia/material, permitiendo trazabilidad forense completa.
    """
    with st.expander("📊 Explorador de Listas de Precios", expanded=False):
        df_eventos = get_todos_eventos_precio()
        if df_eventos is None or df_eventos.empty:
            st.info("No hay listas de precios registradas en el sistema.")
            return

        # Selector de evento
        opts = {}
        for _, ev in df_eventos.iterrows():
            n_p    = int(ev.get("n_precios", 0) or 0)
            estado = str(ev.get("estado", "")).upper()
            badge  = "🟢" if estado == "CERRADO" else "🔵"
            label  = (
                f"{badge} {ev['nombre_evento']}"
                f"  ·  {n_p:,} referencias"
                f"  ·  [{estado}]"
            )
            opts[label] = int(ev["id"])

        col_sel, col_vincular = st.columns([4, 1])
        sel_label = col_sel.selectbox(
            "Seleccionar evento de precio",
            list(opts.keys()),
            key=f"_explorador_evento_{pp_id}",
        )
        evento_sel_id = opts[sel_label]

        if col_vincular.button(
            "🔗 Vincular al PP",
            key=f"_vincular_ev_{pp_id}",
            type="primary",
            help="Asigna este evento de precios al PP y sus ICs",
        ):
            if guardar_configuracion_pp(pp_id, None, evento_sel_id, None):
                st.success("Evento vinculado. Los precios de venta quedan asignados a este PP.")
                st.rerun()
            else:
                st.error("Error al vincular el evento. Revisar logs.")

        df_lista = get_lista_precios_completa(evento_sel_id)
        if df_lista is None or df_lista.empty:
            st.info("Este evento no tiene precios cargados.")
            return

        st.caption(
            f"{len(df_lista):,} entradas · "
            f"**Caso** = regla de precio aplicada · "
            f"**Dólar** e **Índice** = valores del cálculo"
        )

        # Buscador rápido
        filtro = st.text_input(
            "Buscar referencia / material / caso",
            key=f"_explorador_filtro_{pp_id}",
            placeholder="ej: 1234 · CUERO · LPN_BASE",
        ).strip().upper()

        if filtro:
            mask = (
                df_lista["referencia"].astype(str).str.upper().str.contains(filtro, na=False)
                | df_lista["linea"].astype(str).str.upper().str.contains(filtro, na=False)
                | df_lista["material"].astype(str).str.upper().str.contains(filtro, na=False)
                | df_lista["caso"].astype(str).str.upper().str.contains(filtro, na=False)
            )
            df_lista = df_lista[mask]

        if df_lista.empty:
            st.warning("Sin coincidencias para ese filtro.")
            return

        display = df_lista[[
            "linea", "referencia", "material",
            "lpn", "lpc02", "lpc03", "lpc04",
            "caso", "dolar", "indice",
        ]].copy()

        display = display.rename(columns={
            "linea":      "Línea",
            "referencia": "Referencia",
            "material":   "Material",
            "lpn":               "LPN",
            "lpc02":             "LPC02",
            "lpc03":             "LPC03",
            "lpc04":             "LPC04",
            "caso":              "Caso aplicado",
            "dolar":             "Dólar",
            "indice":            "Índice",
        })

        st.dataframe(
            display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "LPN":   st.column_config.NumberColumn(format="%.0f", width=90),
                "LPC02": st.column_config.NumberColumn(format="%.0f", width=90),
                "LPC03": st.column_config.NumberColumn(format="%.0f", width=90),
                "LPC04": st.column_config.NumberColumn(format="%.0f", width=90),
                "Dólar": st.column_config.NumberColumn(format="%.4f", width=80),
                "Índice": st.column_config.NumberColumn(format="%.4f", width=80),
                "Caso aplicado": st.column_config.TextColumn(width=200),
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# HIJO MENOR — Facturas Internas (doble candado sin stock)
# ─────────────────────────────────────────────────────────────────────────────

def _render_hijo_menor(pp_id: int, tiene_stock: bool, header: dict):
    if not tiene_stock:
        st.warning(
            "🔒 Las facturas internas se habilitan cuando el stock haya sido "
            "importado en la pestaña anterior."
        )
        st.caption(
            "Completá la importación en 'Importación / Stock' para desbloquear esta sección."
        )
        return

    estado = header["estado"]
    es_programado = header.get("categoria_id") == 3

    # ── SECCIÓN ARRIBO ────────────────────────────────────────────────────────
    _render_arribo(pp_id, header)
    st.divider()

    # ── FACTURAS INTERNAS (nueva tabla) ───────────────────────────────────────
    st.subheader("Facturas Internas")
    if es_programado:
        st.caption("Intermediación directa — facturas al cliente sin stock en tránsito.")
    else:
        st.caption("Ventas en tránsito + stock físico post-arribo.")

    _render_facturas_internas(pp_id, header)
    st.divider()

    # ── ENVIAR A COMPRA LEGAL ─────────────────────────────────────────────────
    _render_enviar_a_compra(pp_id, header["numero_proforma"])
    st.divider()

    # ── VENTAS EN TRÁNSITO (sistema legado — showroom) ────────────────────────
    with st.expander("📋 Ventas en tránsito (showroom)", expanded=False):
        _render_ala_sur(pp_id, estado)

    with st.expander("🔬 Trazabilidad Forense", expanded=False):
        _render_auditoria_pp(pp_id, header.get("numero_registro", ""))


# ─────────────────────────────────────────────────────────────────────────────
# ARRIBO
# ─────────────────────────────────────────────────────────────────────────────

def _render_arribo(pp_id: int, header: dict):
    from datetime import date as _date

    estado_arribo = header.get("estado_arribo") or "EN_TRANSITO"
    fecha_arribo  = header.get("fecha_arribo")

    if estado_arribo == "ARRIBADO":
        st.markdown(
            f"<div style='background:#22C55E22;border:1px solid #22C55E;"
            f"border-radius:8px;padding:10px 18px;display:inline-block;"
            f"color:#22C55E;font-size:.88rem;font-weight:600;'>"
            f"✅ PP ARRIBADO — {str(fecha_arribo or '')[:10]}"
            f"&nbsp;&nbsp;<span style='color:#64748B;font-size:.75rem;font-weight:400;'>"
            f"Stock disponible en Bazar Web</span></div>",
            unsafe_allow_html=True,
        )
        return

    key_open = f"_arribo_open_{pp_id}"
    if not st.session_state.get(key_open):
        if st.button("🚢 Registrar Arribo", key=f"_arribo_btn_{pp_id}", type="primary"):
            st.session_state[key_open] = True
            st.rerun()
        return

    st.markdown(
        "<div style='background:#1C2E3F;border:1px solid #D4AF37;"
        "border-radius:10px;padding:16px 20px;margin:8px 0;'>"
        "<b style='color:#D4AF37;'>🚢 Registrar Arribo — esto genera stock en Bazar Web</b>"
        "</div>",
        unsafe_allow_html=True,
    )
    col_fecha, col_ok, col_cancel = st.columns([2, 1, 1])
    fecha = col_fecha.date_input(
        "Fecha de arribo", value=_date.today(),
        key=f"_arribo_fecha_{pp_id}",
        label_visibility="collapsed",
    )
    if col_ok.button("✔ Confirmar", key=f"_arribo_ok_{pp_id}", type="primary",
                     use_container_width=True):
        with st.spinner("Registrando arribo y generando stock_bazar..."):
            ok, msg = registrar_arribo(pp_id, fecha)
        if ok:
            st.success(f"✅ {msg}")
            st.session_state.pop(key_open, None)
            st.rerun()
        else:
            st.error(msg)
    if col_cancel.button("✕ Cancelar", key=f"_arribo_cancel_{pp_id}",
                         use_container_width=True):
        st.session_state.pop(key_open, None)
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# FACTURAS INTERNAS — lista + creación
# ─────────────────────────────────────────────────────────────────────────────

def _render_facturas_internas(pp_id: int, header: dict):
    df_fi = get_facturas_interna_de_pp(pp_id)

    # ── Botón nueva factura ───────────────────────────────────────────────────
    key_fi_open = f"_fi_open_{pp_id}"
    if not st.session_state.get(key_fi_open):
        if st.button("＋ Nueva Factura Interna", key=f"_fi_btn_{pp_id}", type="primary"):
            st.session_state[key_fi_open] = True
            st.session_state.pop(f"_fi_fase_{pp_id}", None)
            st.rerun()
    else:
        _render_nueva_fi(pp_id, header)
        return

    # ── Lista de FIs existentes (formato canónico — core/fi_card) ─────────────
    if df_fi is None or df_fi.empty:
        st.info("Sin facturas internas aún para este PP.")
        return

    total_pares = int(df_fi["total_pares"].sum())
    total_neto  = float(df_fi["total_neto"].sum())
    st.caption(f"{len(df_fi)} factura(s) · {total_pares:,} pares · ${total_neto:,.0f}")
    st.markdown("---")

    for _, fi in df_fi.iterrows():
        fi_dict = fi.to_dict()
        detalles = get_fi_detalles_canonico(int(fi_dict["id"]))
        render_fi_card(
            fi_dict,
            detalles=detalles,
            mostrar_detalle=True,
            detalle_colapsado=True,
            key_prefix=f"pp_{pp_id}_fi",
            mostrar_descuentos=True,
        )
        st.markdown("---")


def _render_nueva_fi(pp_id: int, header: dict):
    fase = st.session_state.get(f"_fi_fase_{pp_id}", "A")

    if st.button("← Volver a Facturas", key=f"_fi_back_{pp_id}"):
        for k in (f"_fi_open_{pp_id}", f"_fi_fase_{pp_id}",
                  f"_fi_cab_{pp_id}", f"_fi_items_{pp_id}"):
            st.session_state.pop(k, None)
        st.rerun()

    if fase == "A":
        _render_fi_fase_a(pp_id, header)
    else:
        _render_fi_fase_b(pp_id, header)


def _render_fi_fase_a(pp_id: int, header: dict):
    st.markdown(
        "<div style='background:#1C2E3F;border:1px solid #D4AF37;"
        "border-radius:10px;padding:14px 20px;margin-bottom:12px;'>"
        "<b style='color:#D4AF37;'>NUEVA FACTURA INTERNA — Cabecera</b></div>",
        unsafe_allow_html=True,
    )

    cod_raw = st.text_input("Código de Cliente", key=f"_fi_cod_{pp_id}",
                            placeholder="Ej: 1234")
    nombre_cliente, cod_valido, cliente_id = None, False, None
    if cod_raw.strip().isdigit():
        nombre_cliente = buscar_cliente_pp(int(cod_raw.strip()))
        if nombre_cliente:
            st.success(f"✓  {nombre_cliente}")
            cod_valido = True
            cliente_id = int(cod_raw.strip())
        else:
            st.warning("Cliente no encontrado.")

    df_vend   = get_vendedores_pp()
    vend_opts = {"(Sin asignar)": None}
    for _, v in df_vend.iterrows():
        vend_opts[str(v["descp_vendedor"])] = int(v["id_vendedor"])
    sel_vend    = st.selectbox("Vendedor", list(vend_opts.keys()), key=f"_fi_vend_{pp_id}")
    vendedor_id = vend_opts[sel_vend]

    evento_id = get_evento_precio_pp(pp_id)
    if not evento_id:
        st.error("Este PP no tiene evento de precio vinculado. Vinculá uno en 'Importación / Stock'.")
        return

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    d1 = col_d1.number_input("Desc. 1 (%)", 0.0, 100.0, 0.0, 0.5, key=f"_fi_d1_{pp_id}") / 100
    d2 = col_d2.number_input("Desc. 2 (%)", 0.0, 100.0, 0.0, 0.5, key=f"_fi_d2_{pp_id}") / 100
    d3 = col_d3.number_input("Desc. 3 (%)", 0.0, 100.0, 0.0, 0.5, key=f"_fi_d3_{pp_id}") / 100
    d4 = col_d4.number_input("Desc. 4 (%)", 0.0, 100.0, 0.0, 0.5, key=f"_fi_d4_{pp_id}") / 100

    if st.button("Siguiente →", key=f"_fi_sig_{pp_id}", type="primary"):
        if not cod_valido:
            st.error("Ingresá un código de cliente válido.")
            return
        df_skus = get_skus_con_precio_para_fi(pp_id, evento_id)
        if df_skus is None or df_skus.empty:
            st.error("No hay artículos con saldo y precio resolvible en este PP.")
            return
        st.session_state[f"_fi_cab_{pp_id}"] = {
            "cliente_id": cliente_id, "nombre_cliente": nombre_cliente,
            "vendedor_id": vendedor_id, "vendedor_label": sel_vend,
            "lista_precio_id": evento_id,
            "d1": d1, "d2": d2, "d3": d3, "d4": d4,
        }
        st.session_state[f"_fi_items_{pp_id}"] = df_skus.to_dict("records")
        st.session_state[f"_fi_fase_{pp_id}"] = "B"
        st.rerun()


def _render_fi_fase_b(pp_id: int, header: dict):
    cab   = st.session_state.get(f"_fi_cab_{pp_id}", {})
    items = st.session_state.get(f"_fi_items_{pp_id}", [])

    st.markdown(
        f"<div style='background:#1C2E3F;border:1px solid #334155;"
        f"border-radius:10px;padding:14px 20px;margin-bottom:12px;'>"
        f"<b style='color:#D4AF37;'>NUEVA FACTURA — Artículos</b>"
        f"<div style='color:#94A3B8;font-size:.82rem;margin-top:4px;'>"
        f"Cliente: <b style='color:#F1F5F9;'>{cab.get('nombre_cliente')}</b>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    d1, d2, d3, d4 = cab["d1"], cab["d2"], cab["d3"], cab["d4"]
    factor = (1-d1)*(1-d2)*(1-d3)*(1-d4)

    seleccion: list[dict] = []
    total_pares = 0
    total_neto  = 0.0

    cols_h = st.columns([2, 2, 2, 1.5, 1.5, 1.5, 1.5])
    for col, lbl in zip(cols_h, ["Línea", "Ref.", "Material", "Cajas disp.", "Cajas", "LPN", "Subtotal"]):
        col.markdown(f"<span style='color:#64748B;font-size:.7rem;text-transform:uppercase;'>{lbl}</span>",
                     unsafe_allow_html=True)

    for i, sku in enumerate(items):
        lpn_base = float(sku.get("lpn", 0) or 0)
        lpn_neto = round(lpn_base * factor)
        saldo    = int(sku.get("saldo", 0) or 0)
        cajas_max = int(sku.get("cantidad_cajas", 0) or 0) if saldo >= int(sku.get("pares_inicial", 1) or 1) else max(1, saldo)

        c = st.columns([2, 2, 2, 1.5, 1.5, 1.5, 1.5])
        c[0].caption(str(sku.get("linea_cod", "—")))
        c[1].caption(str(sku.get("ref_cod", "—")))
        c[2].caption(str(sku.get("material", "—"))[:30])
        c[3].write(str(saldo))
        n_cajas = c[4].number_input("", min_value=0, max_value=cajas_max,
                                     value=0, step=1, key=f"_fi_caj_{pp_id}_{i}",
                                     label_visibility="collapsed")
        pares_por_caja = max(int(sku.get("pares_inicial", 0) or 0) // max(int(sku.get("cantidad_cajas", 1) or 1), 1), 1)
        pares_item = n_cajas * pares_por_caja
        subtotal   = round(pares_item * lpn_neto)
        c[5].write(f"${lpn_neto:,.0f}" if lpn_neto else "—")
        c[6].write(f"${subtotal:,.0f}" if pares_item else "—")

        if n_cajas > 0 and sku.get("linea_id") and sku.get("referencia_id") and sku.get("material_id"):
            seleccion.append({
                "linea_id":     sku["linea_id"],
                "referencia_id": sku["referencia_id"],
                "material_id":  sku["material_id"],
                "color_id":     sku.get("color_id"),
                "cajas":        n_cajas,
                "pares":        pares_item,
                "precio_unit":  lpn_neto,
                "subtotal":     subtotal,
            })
            total_pares += pares_item
            total_neto  += subtotal

    st.divider()
    st.markdown(
        f"<div style='text-align:right;color:#D4AF37;font-size:1.1rem;font-weight:700;'>"
        f"Total: {total_pares:,} pares · ${total_neto:,.0f}</div>",
        unsafe_allow_html=True,
    )

    col_cancel, col_ok = st.columns(2)
    if col_cancel.button("← Volver a cabecera", key=f"_fi_b_back_{pp_id}", use_container_width=True):
        st.session_state[f"_fi_fase_{pp_id}"] = "A"
        st.rerun()

    if col_ok.button("✅ Confirmar Factura", key=f"_fi_confirm_{pp_id}",
                     type="primary", use_container_width=True):
        if not seleccion:
            st.error("Seleccioná al menos una caja.")
            return
        ok, result = crear_factura_interna(
            pp_id=pp_id,
            cliente_id=cab["cliente_id"],
            vendedor_id=cab.get("vendedor_id"),
            lista_precio_id=cab["lista_precio_id"],
            descuento_1=cab["d1"], descuento_2=cab["d2"],
            descuento_3=cab["d3"], descuento_4=cab["d4"],
            items=seleccion,
        )
        if ok:
            st.success(f"✅ Factura **{result}** creada — {total_pares:,} pares · ${total_neto:,.0f}")
            for k in (f"_fi_open_{pp_id}", f"_fi_fase_{pp_id}",
                      f"_fi_cab_{pp_id}", f"_fi_items_{pp_id}"):
                st.session_state.pop(k, None)
            st.rerun()
        else:
            st.error(f"Error: {result}")


def _render_auditoria_pp(id_pp: int, nro_pp: str):
    """
    Timeline forense del PP y de todas las ICs vinculadas.
    Muestra cada evento con su snapshot completo en orden cronológico.
    """
    from core.auditoria import get_historial_entidad, get_historial_nro
    import json

    _ACCION_LABEL = {
        "DIG_PP_CREADO":    ("🟡", "PP Creado por Digitación"),
        "DIG_IC_ASIGNADA":  ("🔗", "IC Asignada al PP"),
        "DIG_PP_CERRADO":   ("🔒", "PP Cerrado por Digitación"),
        "PP_F9_CARGADO":    ("📦", "F9 Cargado"),
        "PP_ENVIADO_COMPRA":("📤", "Enviado a Compra Legal"),
        "IC_CREADA":        ("✨", "IC Creada"),
        "IC_AUTORIZADA":    ("✅", "IC Autorizada"),
        "IC_ASIGNADA_PP":   ("🔗", "IC Asignada"),
        "IC_DEVUELTA_ADMIN":("↩️", "IC Devuelta a Admin"),
        "IC_REAUTORIZADA":  ("♻️", "IC Re-autorizada"),
        "IC_ANULADA":       ("❌", "IC Anulada"),
        "CL_CREADA":        ("📋", "Compra Legal Creada"),
        "CL_FINALIZADA":    ("🏁", "Compra Legal Finalizada"),
        "TRASPASO_ENVIADO": ("🚀", "Traspaso Enviado"),
        "TRASPASO_CONFIRMADO": ("✅", "Traspaso Confirmado"),
    }

    # Historial del PP
    eventos_pp = get_historial_entidad("PP", id_pp)

    # Historial de cada IC vinculada (via bridge)
    from modules.pedido_proveedor.logic import get_datos_ics_de_pp
    df_ics = get_datos_ics_de_pp(id_pp)
    eventos_ic = []
    for _, ic_row in df_ics.iterrows():
        nro_ic = str(ic_row["nro_ic"])
        for ev in get_historial_nro(nro_ic):
            ev["_origen"] = nro_ic
            eventos_ic.append(ev)

    # Unir y ordenar cronológicamente
    todos = []
    for ev in eventos_pp:
        ev["_origen"] = nro_pp
        todos.append(ev)
    todos.extend(eventos_ic)
    todos.sort(key=lambda e: str(e.get("created_at", "")))

    if not todos:
        st.caption("Sin eventos registrados aún para este expediente.")
        return

    st.caption(
        f"Registro inmutable · {len(todos)} evento(s) · "
        f"Cadena IC→Digitación→PP→Compra Legal"
    )
    st.divider()

    for ev in todos:
        accion   = str(ev.get("accion", ""))
        icon, label = _ACCION_LABEL.get(accion, ("📌", accion))
        ts       = str(ev.get("created_at", ""))[:16].replace("T", " ")
        origen   = str(ev.get("_origen", ""))
        ea       = ev.get("estado_antes")  or ""
        ed       = ev.get("estado_despues") or ""
        snap     = ev.get("snap") or {}
        if isinstance(snap, str):
            try:
                snap = json.loads(snap)
            except Exception:
                snap = {}

        estado_txt = ""
        if ea and ed:
            estado_txt = f"<span style='color:#64748B;'>{ea}</span> → <span style='color:#D4AF37;'>{ed}</span>"
        elif ed:
            estado_txt = f"→ <span style='color:#D4AF37;'>{ed}</span>"

        # Filas clave del snapshot para mostrar inline
        snap_items = []
        for k in ("marca", "proveedor", "cliente", "vendedor", "pares",
                   "pares_heredados", "total_pares", "n_articulos",
                   "nro_pedido_fabrica", "proforma", "nro_factura_importacion",
                   "motivo", "evento_precio"):
            v = snap.get(k)
            if v is not None and str(v) not in ("", "None", "null"):
                snap_items.append(f"<b>{k}:</b> {v}")

        snap_inline = "  ·  ".join(snap_items[:6]) if snap_items else ""

        st.markdown(
            f"<div style='border-left:3px solid #334155;padding:6px 0 6px 14px;"
            f"margin-bottom:6px;'>"
            f"<div style='display:flex;gap:10px;align-items:center;'>"
            f"<span style='font-size:1rem;'>{icon}</span>"
            f"<span style='color:#F1F5F9;font-weight:600;font-size:.88rem;'>{label}</span>"
            f"<span style='color:#475569;font-size:.75rem;margin-left:auto;'>{ts}</span>"
            f"<span style='color:#64748B;font-size:.72rem;'>[{origen}]</span>"
            f"</div>"
            f"{'<div style=margin-top:2px;font-size:.78rem;>' + estado_txt + '</div>' if estado_txt else ''}"
            f"{'<div style=color:#94A3B8;font-size:.76rem;margin-top:3px;>' + snap_inline + '</div>' if snap_inline else ''}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Expander con snap completo
        with st.expander(f"Ver snapshot completo — {label} {ts}", expanded=False):
            st.json(snap)


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
    import json as _json

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
                  .sum().reset_index()
                  .rename(columns={"marca": "Marca",
                                   "cantidad_inicial": "Inicial",
                                   "vendido": "Vendido", "saldo": "Saldo"})
            )
            st.dataframe(resumen, hide_index=True, use_container_width=False)

    # ── Construir distribución de tallas desde grades_json ─────────────────
    def _fmt_grades(raw) -> str:
        """grades_json → '17:1·18:1·19:1·20:2...' o '' si vacío."""
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return ""
        try:
            g = _json.loads(raw) if isinstance(raw, str) else raw
            if not g:
                return ""
            # Ordenar numéricamente por talla
            items = sorted(g.items(), key=lambda kv: float(kv[0]))
            return "  ".join(f"{k}:{v}" for k, v in items if int(v) > 0)
        except Exception:
            return ""

    # Recolectar todas las tallas únicas presentes en el PP
    all_grades: list[str] = []
    for raw in df.get("grades_json", pd.Series()):
        try:
            g = _json.loads(raw) if isinstance(raw, str) else (raw or {})
            for k in g:
                if k not in all_grades:
                    all_grades.append(k)
        except Exception:
            pass
    all_grades = sorted(all_grades, key=extraer_valor_numerico_talla)

    # Construir tabla display
    avail = set(df.columns)
    ordered_raw = [c for c in
                   ["marca", "linea", "referencia", "style_code",
                    "material_code", "material", "color_code", "color", "grada",
                    "cantidad_cajas", "cantidad_inicial", "vendido", "saldo"]
                   if c in avail]

    display = df[ordered_raw].copy()

    col_map = {
        "marca":            "Marca",
        "linea":            "Línea",
        "referencia":       "Ref.",
        "style_code":       "Código",
        "material_code":    "Cód.Mat",
        "material":         "Material",
        "color_code":       "Cód.Col",
        "color":            "Color",
        "grada":            "Tallas",
        "cantidad_cajas":   "_cajas",   # auxiliar, se usa para calcular x Caja
        "cantidad_inicial": "Inicial",
        "vendido":          "Vendido",
        "saldo":            "Saldo",
    }
    display.rename(columns={k: v for k, v in col_map.items() if k in display.columns},
                   inplace=True)

    # Columna "x Caja" = pares por caja
    if "_cajas" in display.columns and "Inicial" in display.columns:
        display["x Caja"] = (
            display["Inicial"] / display["_cajas"].replace(0, 1)
        ).round(0).astype(int)
        display.drop(columns=["_cajas"], inplace=True)

    # Añadir columna por talla si hay grades_json
    if all_grades and "grades_json" in df.columns:
        for g in all_grades:
            display[g] = df["grades_json"].apply(
                lambda raw, _g=g: (
                    _json.loads(raw) if isinstance(raw, str) else {}
                ).get(_g, 0) if raw and raw not in ("", "nan", "null", "None") else 0
            )
        info_cols = [c for c in ["Marca", "Línea", "Ref.", "Código",
                                  "Cód.Mat", "Material", "Cód.Col", "Color",
                                  "Tallas", "x Caja"]
                     if c in display.columns]
        tot_cols  = ["Inicial", "Vendido", "Saldo"]
        display   = display[info_cols + all_grades + tot_cols]

    # Column config dinámica
    col_cfg: dict = {
        "Marca":    st.column_config.TextColumn(width=90),
        "Línea":    st.column_config.TextColumn(width=55),
        "Ref.":     st.column_config.TextColumn(width=45),
        "Código":   st.column_config.TextColumn(width=70),
        "Cód.Mat":  st.column_config.TextColumn(width=70),
        "Material": st.column_config.TextColumn(width=155),
        "Cód.Col":  st.column_config.TextColumn(width=65),
        "Color":    st.column_config.TextColumn(width=110),
        "Tallas":   st.column_config.TextColumn(width=55),
        "x Caja":   st.column_config.NumberColumn(format="%d", width=55),
        "Inicial":  st.column_config.NumberColumn(format="%d", width=65),
        "Vendido":  st.column_config.NumberColumn(format="%d", width=65),
        "Saldo":    st.column_config.NumberColumn(format="%d", width=65),
    }
    for g in all_grades:
        col_cfg[g] = st.column_config.NumberColumn(format="%d", width=44)

    st.dataframe(display, column_config=col_cfg,
                 hide_index=True, use_container_width=True)


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
