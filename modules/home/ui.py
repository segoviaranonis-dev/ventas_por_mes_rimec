# =============================================================================
# SISTEMA: RIMEC Business Intelligence — NEXUS CORE
# MÓDULO:  modules/home/ui.py
# VERSION: 2.0.0 (NEXUS LAUNCHER — Modular Command Center)
# DESCRIPCIÓN: Pantalla de inicio tipo launcher: cards por sector de negocio.
#              Navega a cualquier módulo sin pasar por el sidebar.
# =============================================================================

import streamlit as st
from core.database import get_engine, DBInspector
from core.settings import settings


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _nav(key: str):
    """Navega al módulo indicado. El radio del sidebar usa index desde piso_actual."""
    st.session_state.piso_actual = key
    st.rerun()


def _section(icon: str, title: str, subtitle: str):
    """Renderiza el encabezado de una sección del launcher."""
    st.markdown(f"""
        <div class="nx-section-label" style="margin-top:28px;">
            {icon}&nbsp;&nbsp;{title}
            <span style="font-weight:400; text-transform:none; letter-spacing:0;
                         color:#475569; font-size:0.67rem; margin-left:8px;">
                — {subtitle}
            </span>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)


def _card_html(icon: str, title: str, desc: str) -> str:
    """Genera HTML de una card visual del launcher."""
    return f"""
        <div class="nx-card">
            <span class="nx-card-icon">{icon}</span>
            <div class="nx-card-title">{title}</div>
            <div class="nx-card-desc">{desc}</div>
        </div>
    """


def _card(col, icon: str, title: str, desc: str, btn_key: str, module_key: str):
    """Renderiza una card completa con su botón de navegación en la columna dada."""
    with col:
        st.markdown(_card_html(icon, title, desc), unsafe_allow_html=True)
        if st.button("Abrir →", key=btn_key, use_container_width=True):
            _nav(module_key)


# ─────────────────────────────────────────────────────────────────────────────
# RENDER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_home():
    """Command Center — Launcher modular NEXUS v2.0."""

    # ── DB STATUS ─────────────────────────────────────────────────────────────
    engine = get_engine()
    db_ok  = engine is not None

    status_class = "nx-status-badge" if db_ok else "nx-status-badge offline"
    status_dot   = "●" if db_ok else "●"
    status_txt   = "Base de datos conectada" if db_ok else "Sin conexión a la base de datos"

    # ── HERO ──────────────────────────────────────────────────────────────────
    st.markdown(f"""
        <div class="nx-hero">
            <div class="nx-hero-brand">{settings.COMPANY_NAME} &nbsp;·&nbsp; {settings.SYSTEM_NAME}</div>
            <div class="nx-hero-title">Command Center</div>
            <div class="nx-hero-sub" style="margin-bottom:14px;">
                Sistema de Gestión Integral · v{settings.VERSION}
            </div>
            <span class="{status_class}">{status_dot}&nbsp;{status_txt}</span>
        </div>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # SECCIÓN 1 — ANÁLISIS COMERCIAL
    # ══════════════════════════════════════════════════════════════════════════
    _section("📊", "ANÁLISIS COMERCIAL", "Reportes e inteligencia de ventas")

    col_sr, col_empty = st.columns([1, 2])
    _card(
        col_sr,
        icon  = "📊",
        title = "Sales Report",
        desc  = "Análisis de ventas por período, vendedor, marca y cadena. Exportación PDF ejecutiva.",
        btn_key     = "nav_sales",
        module_key  = "sales",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SECCIÓN 2 — CICLO DE IMPORTACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    _section("🚢", "CICLO DE IMPORTACIÓN", "Motor de precios · Flujo completo desde intención hasta depósito")

    c0, c1, c2, c3, c4, c5, c6, c7 = st.columns(8)

    _card(
        c0,
        icon  = "⚙️",
        title = "Motor de Precios",
        desc  = "Importar FOB del proveedor, configurar casos y generar listas LPN / LPC03 / LPC04.",
        btn_key    = "nav_engine",
        module_key = "rimec_engine",
    )
    _card(
        c1,
        icon  = "📋",
        title = "Intención de Compra",
        desc  = "Cabecera financiera. Cuotas por marca y límite de crédito.",
        btn_key     = "nav_ic",
        module_key  = "intencion_compra",
    )
    _card(
        c2,
        icon  = "⌨️",
        title = "Digitación",
        desc  = "Asigna nro. de fábrica a ICs autorizadas y las agrupa en Pedidos Proveedor.",
        btn_key     = "nav_dig",
        module_key  = "digitacion",
    )
    _card(
        c3,
        icon  = "📦",
        title = "Pedido Proveedor",
        desc  = "SKUs F9, gradaciones, proformas y ventas en tránsito.",
        btn_key     = "nav_pp",
        module_key  = "pedido_proveedor",
    )
    _card(
        c4,
        icon  = "✅",
        title = "Aprobación de Pedidos",
        desc  = "Pedidos RIMEC mayorista. Verificar y autorizar. Divide por PP, Marca y Caso.",
        btn_key     = "nav_aprobacion",
        module_key  = "aprobacion_pedidos",
    )
    _card(
        c5,
        icon  = "🏛️",
        title = "Compra Legal",
        desc  = "Consolidación de PPs. Generación de compras legales y traspasos.",
        btn_key     = "nav_cl",
        module_key  = "compra_legal",
    )
    _card(
        c6,
        icon  = "🧾",
        title = "Facturación",
        desc  = "FAC-INT en tránsito. Distribución a sucursales y cliente 5000.",
        btn_key     = "nav_fac",
        module_key  = "facturacion",
    )
    _card(
        c7,
        icon  = "🏭",
        title = "Depósito RIMEC",
        desc  = "Saldo físico en depósito. Compra inicial menos venta en tránsito.",
        btn_key     = "nav_dep",
        module_key  = "deposito",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SECCIÓN 4 — BAZAR WEB
    # ══════════════════════════════════════════════════════════════════════════
    _section("🛍️", "BAZAR WEB", "Operación del catálogo y tienda online")

    b1, b2, b3, b4 = st.columns([1, 1, 1, 2])

    _card(
        b1,
        icon  = "🛒",
        title = "Pedidos Web",
        desc  = "Recepción y confirmación de pedidos del catálogo online.",
        btn_key     = "nav_pw",
        module_key  = "pedido_web",
    )
    _card(
        b2,
        icon  = "📥",
        title = "Compra Web",
        desc  = "Recepción de mercadería en almacén web (ALM_WEB_01).",
        btn_key     = "nav_cw",
        module_key  = "compra_web",
    )
    _card(
        b3,
        icon  = "📦",
        title = "Depósito Web",
        desc  = "Stock disponible en tienda. Vista de saldo por artículo.",
        btn_key     = "nav_dw",
        module_key  = "deposito_web",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # SECCIÓN 5 — SISTEMA
    # ══════════════════════════════════════════════════════════════════════════
    _section("⚙️", "SISTEMA", "Herramientas de mantenimiento y diagnóstico")

    s1, s2, s3 = st.columns([1, 1, 3])

    _card(
        s1,
        icon  = "📥",
        title = "Importar Datos",
        desc  = "Carga de archivos F9, catálogos y datos históricos.",
        btn_key     = "nav_import",
        module_key  = "import",
    )
    _card(
        s2,
        icon  = "🔧",
        title = "Estado del Sistema",
        desc  = "Diagnóstico de conexión, logs y salud de la base de datos.",
        btn_key     = "nav_status",
        module_key  = "diagnostics",
    )

    # ── FOOTER ────────────────────────────────────────────────────────────────
    st.markdown("<div style='margin-top:32px;'></div>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style="text-align:center; color:#334155; font-size:0.68rem; padding: 16px 0;">
            {settings.COMPANY_NAME} · {settings.SYSTEM_NAME} v{settings.VERSION}
            &nbsp;·&nbsp; {settings.EDITION}
        </div>
    """, unsafe_allow_html=True)

    DBInspector.log("🚀 [HOME] Launcher v2.0 renderizado", "SUCCESS")
