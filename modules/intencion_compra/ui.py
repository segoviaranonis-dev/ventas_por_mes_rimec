# =============================================================================
# MÓDULO: Intención de Compra
# ARCHIVO: modules/intencion_compra/ui.py
# DESCRIPCIÓN: Interfaz de alta gerencia para registrar intenciones de compra.
#
#  PROHIBIDO en este módulo: material, color, línea, referencia, proforma.
#  Solo cabecera financiera: proveedor, cliente (por código), vendedor, marca,
#  plazo, pares totales, montos, descuentos, fechas y estado.
#
#  El número de registro (IC-YYYY-XXXX) se genera automáticamente al guardar.
# =============================================================================

import streamlit as st
import pandas as pd
from datetime import date

from modules.intencion_compra.logic import (
    get_proveedores, get_vendedores,
    get_marcas, get_plazos, buscar_cliente,
    get_intenciones, get_dashboard_eta,
    calcular_neto, save_intencion,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _opts(df: pd.DataFrame, id_col: str, label_col: str) -> dict:
    return {row[label_col]: row[id_col] for _, row in df.iterrows()}


def _fmt_gs(v: float) -> str:
    return f"Gs. {v:,.0f}"


# ─────────────────────────────────────────────────────────────────────────────
# FORMULARIO
# ─────────────────────────────────────────────────────────────────────────────

def _render_form():
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

    # ── FILA 1: Proveedor + Marca ─────────────────────────────────────────────
    c1, c2 = st.columns(2)
    sel_prov = c1.selectbox("Proveedor", list(opts_prov.keys()), key="ic_prov")
    sel_marc = c2.selectbox("Marca",     list(opts_marc.keys()), key="ic_marc")

    # ── FILA 2: Código de cliente (lookup) + Vendedor ─────────────────────────
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**Cliente** — Ingresá el código del papel/email")
        cod_cliente = st.number_input(
            "Código de Cliente",
            min_value=1, step=1, value=276,
            key="ic_cod_cli",
            label_visibility="collapsed",
        )
        nombre_cliente = buscar_cliente(int(cod_cliente))
        if nombre_cliente:
            st.success(f"✔ {cod_cliente} — {nombre_cliente}")
        else:
            st.error(f"✗ Código {cod_cliente} no encontrado en la BD.")

    with c4:
        sel_vend = st.selectbox(
            "Vendedor Responsable",
            list(opts_vend.keys()),
            key="ic_vend",
        )

    # ── FILA 3: Plazo + Pares + Fechas ────────────────────────────────────────
    c5, c6, c7, c8 = st.columns([2, 1, 1, 1])
    sel_plaz  = c5.selectbox("Plazo de Pago",      list(opts_plaz.keys()), key="ic_plaz")
    pares     = c6.number_input("Total Pares",      min_value=0, step=12, value=0, key="ic_pares")
    fecha_reg = c7.date_input("Fecha Registro",     value=date.today(), key="ic_fecha_reg")
    fecha_eta = c8.date_input("ETA (Llegada PY)",   value=None, key="ic_fecha_eta",
                               help="Fecha estimada de arribo a Paraguay")

    # ── FILA 4: Nota de pedido ────────────────────────────────────────────────
    nota_pedido = st.text_input(
        "Nota / Referencia del Pedido",
        placeholder="Ej: Email 30-03 | Nota pedido #4567 | Proforma 3130",
        key="ic_nota",
        help="Referencia del papel o email recibido con la orden del cliente.",
    )

    # ── FILA 5: Monto y descuentos ────────────────────────────────────────────
    st.markdown("**Condiciones Financieras** — Montos pueden registrarse en 0 para definir en etapa posterior")
    monto_bruto = st.number_input(
        "Monto Bruto Total (Gs.)",
        min_value=0.0, step=1_000_000.0, value=0.0, format="%.0f",
        key="ic_bruto",
    )
    cd1, cd2, cd3, cd4 = st.columns(4)
    d1 = cd1.number_input("Desc. 1 (%)", 0.0, 100.0, 0.0, 0.5, key="ic_d1", format="%.2f")
    d2 = cd2.number_input("Desc. 2 (%)", 0.0, 100.0, 0.0, 0.5, key="ic_d2", format="%.2f")
    d3 = cd3.number_input("Desc. 3 (%)", 0.0, 100.0, 0.0, 0.5, key="ic_d3", format="%.2f")
    d4 = cd4.number_input("Desc. 4 (%)", 0.0, 100.0, 0.0, 0.5, key="ic_d4", format="%.2f")

    # Cálculo en tiempo real
    monto_neto = calcular_neto(monto_bruto, d1, d2, d3, d4)
    st.markdown(
        f"""<div style="background:#1C1F2E;border-left:4px solid #D4AF37;
                padding:10px 16px;border-radius:4px;margin:8px 0;">
            <span style="color:#94A3B8;font-size:0.8rem;">MONTO NETO CALCULADO</span><br>
            <span style="color:#D4AF37;font-size:1.4rem;font-weight:bold;">{_fmt_gs(monto_neto)}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── OBSERVACIONES ─────────────────────────────────────────────────────────
    observaciones = st.text_area(
        "Observaciones", height=70,
        placeholder="Condiciones especiales, notas de negociación...",
        key="ic_obs",
    )

    # ── BOTÓN ─────────────────────────────────────────────────────────────────
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
            "id_proveedor":        opts_prov[sel_prov],
            "id_cliente":          int(cod_cliente),
            "id_vendedor":         opts_vend[sel_vend],
            "id_marca":            opts_marc[sel_marc],
            "id_plazo":            opts_plaz[sel_plaz],
            "cantidad_total_pares": pares,
            "monto_bruto":         monto_bruto,
            "descuento_1": d1, "descuento_2": d2,
            "descuento_3": d3, "descuento_4": d4,
            "fecha_registro":  fecha_reg,
            "fecha_llegada":   fecha_eta,
            "nota_pedido":     nota_pedido,
            "observaciones":   observaciones,
        })

        if ok:
            st.success(f"Registrado: **{resultado}** | {sel_marc} | {pares:,} pares | ETA {fecha_eta}")
            st.rerun()
        else:
            st.error(resultado)


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD ETA
# ─────────────────────────────────────────────────────────────────────────────

def _render_dashboard():
    df = get_dashboard_eta()
    if df.empty:
        return

    st.markdown("#### Compromisos por Fecha de Llegada")

    df["fecha_llegada"] = pd.to_datetime(df["fecha_llegada"], errors="coerce").dt.strftime("%Y-%m-%d")

    col_tabla, col_totales = st.columns([3, 1])
    with col_tabla:
        st.dataframe(
            df[["numero_registro", "fecha_llegada", "marca", "pares", "neto", "estado"]].rename(columns={
                "numero_registro": "IC Nro.",
                "fecha_llegada":   "ETA",
                "marca":           "Marca",
                "pares":           "Pares",
                "neto":            "Monto Neto (Gs.)",
                "estado":          "Estado",
            }),
            column_config={
                "IC Nro.":          st.column_config.TextColumn(width=130),
                "ETA":              st.column_config.TextColumn(width=100),
                "Marca":            st.column_config.TextColumn(width=110),
                "Pares":            st.column_config.NumberColumn(format="%d", width=80),
                "Monto Neto (Gs.)": st.column_config.NumberColumn(format="%.0f", width=130),
                "Estado":           st.column_config.TextColumn(width=160),
            },
            hide_index=True,
            use_container_width=True,
        )

    with col_totales:
        st.metric("Total Registros", len(df))
        st.metric("Total Pares", f"{int(df['pares'].sum()):,}")
        st.metric("Total Neto", _fmt_gs(float(df["neto"].sum())))


# ─────────────────────────────────────────────────────────────────────────────
# GRID INTENCIONES
# ─────────────────────────────────────────────────────────────────────────────

def _render_grid():
    filtros = st.session_state.get("ic_filtros", {})
    df = get_intenciones(filtros)

    estado_lbl = filtros.get("estado", "TODOS")
    st.markdown(f"#### Intenciones Registradas &nbsp;`{len(df)} registros` — estado: `{estado_lbl}`")

    if df.empty:
        st.info("No hay intenciones que coincidan con los filtros.")
        return

    df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["fecha_llegada"]  = pd.to_datetime(df["fecha_llegada"],  errors="coerce").dt.strftime("%Y-%m-%d")

    st.dataframe(
        df[[
            "numero_registro", "marca", "id_cliente", "cliente",
            "vendedor", "plazo", "pares",
            "monto_bruto", "descuento_1", "descuento_2", "descuento_3", "descuento_4",
            "monto_neto", "fecha_registro", "fecha_llegada",
            "estado", "nota_pedido", "observaciones",
        ]].rename(columns={
            "numero_registro": "IC Nro.",
            "marca":           "Marca",
            "id_cliente":      "Cód. Cliente",
            "cliente":         "Cliente",
            "vendedor":        "Vendedor",
            "plazo":           "Plazo",
            "pares":           "Pares",
            "monto_bruto":     "Bruto (Gs.)",
            "descuento_1":     "D1%",
            "descuento_2":     "D2%",
            "descuento_3":     "D3%",
            "descuento_4":     "D4%",
            "monto_neto":      "Neto (Gs.)",
            "fecha_registro":  "Registro",
            "fecha_llegada":   "ETA",
            "estado":          "Estado",
            "nota_pedido":     "Nota Pedido",
            "observaciones":   "Obs.",
        }),
        column_config={
            "IC Nro.":      st.column_config.TextColumn(width=130),
            "Marca":        st.column_config.TextColumn(width=110),
            "Cód. Cliente": st.column_config.NumberColumn(format="%d", width=90),
            "Cliente":      st.column_config.TextColumn(width=160),
            "Vendedor":     st.column_config.TextColumn(width=100),
            "Plazo":        st.column_config.TextColumn(width=130),
            "Pares":        st.column_config.NumberColumn(format="%d", width=80),
            "Bruto (Gs.)":  st.column_config.NumberColumn(format="%.0f", width=110),
            "D1%":          st.column_config.NumberColumn(format="%.2f", width=60),
            "D2%":          st.column_config.NumberColumn(format="%.2f", width=60),
            "D3%":          st.column_config.NumberColumn(format="%.2f", width=60),
            "D4%":          st.column_config.NumberColumn(format="%.2f", width=60),
            "Neto (Gs.)":   st.column_config.NumberColumn(format="%.0f", width=110),
            "Registro":     st.column_config.TextColumn(width=95),
            "ETA":          st.column_config.TextColumn(width=95),
            "Estado":       st.column_config.TextColumn(width=160),
            "Nota Pedido":  st.column_config.TextColumn(width=200),
            "Obs.":         st.column_config.TextColumn(width=180),
        },
        hide_index=True,
        use_container_width=True,
    )


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

    with st.expander(
        "➕ Registrar Nueva Intención",
        expanded=st.session_state.get("ic_mostrar_form", True),
    ):
        _render_form()
        st.session_state["ic_mostrar_form"] = False

    st.divider()
    _render_dashboard()
    st.divider()
    _render_grid()
