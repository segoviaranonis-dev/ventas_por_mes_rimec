"""
SISTEMA: CHUNACHUNA IMPORT Business Intelligence - NEXUS CORE
UBICACIÓN: core/styles.py
VERSION: 70.4.5 (OBSIDIAN ELITE - STRICT PIANO READY)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: El Ejecutor Visual de Elite.
             Sincronización total de la Armadura Obsidian.
             MODIFICACIÓN V70.4.5: REQ-01 - Verificación de variables de color.
             Preparación de CSS para el renderizado jerárquico Strict Piano.
"""

import streamlit as st
from reportlab.lib import colors
from core.settings import settings

# ─────────────────────────────────────────────────────────────────────────────
# ADN CENTRAL (SINCRONIZACIÓN CON ARMADURA OBSIDIAN)
# ─────────────────────────────────────────────────────────────────────────────
COLOR_GOLD = settings.UI_PRIMARY    # Oro (#D4AF37)
COLOR_DEEP = settings.UI_BACKGROUND  # Obsidiana Pura (#0B0D17)
COLOR_SOFT = settings.UI_SECONDARY   # Obsidiana Ligera (#1A1C25)
COLOR_TEXT = settings.TEXT_LIGHT     # Blanco Nieve (#F8FAFC)

class PDFStyleFactory:
    """Fábrica de Estilos para PDF (Mantenemos legibilidad en papel con acentos Oro)."""
    @staticmethod
    def get_pdf_colors():
        return {
            'primary': colors.HexColor(settings.PDF_PRIMARY),
            'secondary': colors.HexColor(settings.PDF_SECONDARY),
            'text_main': colors.black,
            'text_soft': colors.grey,
            'critical': colors.HexColor(settings.COLOR_CRITICAL)
        }

class StatusFactory:
    """Señalética de Negocio: Alertas con Glow dinámico sobre fondo oscuro."""
    @staticmethod
    def alert(tipo, mensaje):
        colores = {
            "success": (settings.COLOR_SUCCESS, "✅"),
            "error": (settings.COLOR_CRITICAL, "❌")
        }
        bg, icon = colores.get(tipo, (COLOR_GOLD, "ℹ️"))

        st.markdown(f"""
            <div style="background-color:{bg}15; padding:15px; border-radius:10px; border:1px solid {bg};
            color:{COLOR_TEXT}; font-weight:600; box-shadow: 0 0 10px {bg}22;">
                {icon} {mensaje}
            </div>
        """, unsafe_allow_html=True)

class GlowDynamics:
    """
    MOTOR DE RESPLANDOR CONDICIONAL (Fase IV: JsCode Glow):
    Inyecta lógica JavaScript para que AgGrid renderice colores con opacidad
    dinámica del 15% basada en el signo del dato.
    """
    @staticmethod
    def get_variation_js():
        """Retorna el JsCode para el resplandor de celdas de variación."""
        from st_aggrid import JsCode
        return JsCode("""
        function(params) {
            if (params.value == null || params.value === '---') return {};
            var val = parseFloat(params.value);

            // LÓGICA DE INGENIERÍA: Resplandor Verde (Éxito)
            if (val >= 0) {
                return {
                    'color': '#10B981',
                    'backgroundColor': 'rgba(16, 185, 129, 0.15)',
                    'fontWeight': 'bold',
                    'borderLeft': '4px solid #10B981',
                    'boxShadow': 'inset 0 0 10px rgba(16, 185, 129, 0.1)'
                };
            }
            // LÓGICA DE INGENIERÍA: Resplandor Rojo (Riesgo)
            else {
                return {
                    'color': '#EF4444',
                    'backgroundColor': 'rgba(239, 68, 68, 0.15)',
                    'fontWeight': 'bold',
                    'borderLeft': '4px solid #EF4444',
                    'boxShadow': 'inset 0 0 10px rgba(239, 68, 68, 0.1)'
                };
            }
        };
        """)

def apply_ui_theme():
    """Inyección de CSS: El blindaje Obsidian v70.5.0 — anti light-mode."""
    print(f"🎨 [STYLES] Sincronizando Armadura Obsidian v{settings.VERSION}")

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        /* ═══════════════════════════════════════════════════════════
           0. BLINDAJE TOTAL CONTRA MODO CLARO DEL NAVEGADOR
           Fuerza dark-scheme a nivel raíz para que el navegador
           no sobreescriba colores de texto con su CSS de sistema.
           ═══════════════════════════════════════════════════════════ */
        :root {{
            color-scheme: dark !important;
        }}

        /* Override explícito cuando el SO está en modo claro */
        @media (prefers-color-scheme: light) {{
            :root {{ color-scheme: dark !important; }}
            html, body {{
                background-color: {COLOR_DEEP} !important;
                color: {COLOR_TEXT} !important;
            }}
            * {{ color: {COLOR_TEXT} !important; }}
            /* Re-aplicar excepciones que necesitan colores propios */
            div.stButton > button {{ color: {COLOR_GOLD} !important; }}
            div.stButton > button:hover {{ color: {COLOR_DEEP} !important; }}
            a {{ color: {COLOR_GOLD} !important; }}
        }}

        /* ═══════════════════════════════════════════════════════════
           1. RESET Y FONDO OBSIDIANA
           ═══════════════════════════════════════════════════════════ */
        html, body, [data-testid="stAppViewContainer"],
        [data-testid="stHeader"], [data-testid="stMain"] {{
            background-color: {COLOR_DEEP} !important;
            font-family: 'Inter', sans-serif !important;
            color: {COLOR_TEXT} !important;
        }}

        /* Todos los textos generados por Streamlit heredan el color claro */
        p, span, div, li, td, th, label, small, caption,
        .stMarkdown, .stText, .element-container {{
            color: {COLOR_TEXT} !important;
        }}

        /* Selectores específicos de Streamlit */
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] span,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] strong,
        [data-testid="stMarkdownContainer"] em {{
            color: {COLOR_TEXT} !important;
        }}

        /* Labels de inputs, selects, sliders */
        .stTextInput label, .stSelectbox label, .stMultiSelect label,
        .stSlider label, .stRadio label, .stCheckbox label,
        .stFileUploader label, .stDateInput label,
        .stNumberInput label, .stTextArea label {{
            color: {COLOR_TEXT} !important;
        }}

        /* Captions y texto muted */
        [data-testid="stCaptionContainer"],
        .stCaption, .stCaption p {{
            color: {settings.TEXT_MUTED} !important;
        }}

        [data-testid="stSidebarNav"] {{ display: none !important; }}

        /* ═══════════════════════════════════════════════════════════
           2. SIDEBAR PROFESIONAL
           ═══════════════════════════════════════════════════════════ */
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] > div {{
            background-color: {COLOR_SOFT} !important;
            border-right: 1px solid {COLOR_GOLD}44;
        }}

        /* ═══════════════════════════════════════════════════════════
           3. TÍTULOS Y TEXTO
           ═══════════════════════════════════════════════════════════ */
        h1, h2, h3, h4, h5, h6 {{
            color: {COLOR_TEXT} !important;
            font-weight: 800 !important;
            letter-spacing: -0.03em !important;
        }}

        /* ═══════════════════════════════════════════════════════════
           4. BOTONES: Estilo Prestige
           ═══════════════════════════════════════════════════════════ */
        div.stButton > button {{
            border-radius: 10px !important;
            background-color: {COLOR_DEEP} !important;
            color: {COLOR_GOLD} !important;
            border: 1px solid {COLOR_GOLD} !important;
            font-weight: 700 !important;
            padding: 0.5rem 1rem !important;
            width: 100% !important;
            transition: all 0.25s ease;
        }}

        div.stButton > button:hover {{
            background-color: {COLOR_GOLD} !important;
            color: {COLOR_DEEP} !important;
            box-shadow: 0 0 20px {COLOR_GOLD}55;
            transform: translateY(-2px);
        }}

        /* ═══════════════════════════════════════════════════════════
           5. CARDS LEGACY (rimec-card)
           ═══════════════════════════════════════════════════════════ */
        .rimec-card {{
            background-color: {COLOR_SOFT} !important;
            padding: 22px;
            border-radius: 15px;
            border-left: 5px solid {COLOR_GOLD};
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            margin-bottom: 15px;
            transition: transform 0.2s ease;
        }}

        .rimec-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 6px 20px {COLOR_GOLD}22;
        }}

        /* ═══════════════════════════════════════════════════════════
           6. LAUNCHER CARDS (módulo home)
           ═══════════════════════════════════════════════════════════ */
        .nx-card {{
            background: {COLOR_SOFT};
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 14px;
            padding: 20px 18px 14px 18px;
            margin-bottom: 6px;
            transition: all 0.2s ease;
            min-height: 120px;
        }}

        .nx-card:hover {{
            border-color: {COLOR_GOLD}88;
            background: #1E2030;
            transform: translateY(-2px);
            box-shadow: 0 8px 28px rgba(0,0,0,0.45);
        }}

        .nx-card-icon {{
            font-size: 1.7rem;
            line-height: 1;
            margin-bottom: 8px;
            display: block;
        }}

        .nx-card-title {{
            font-size: 0.88rem;
            font-weight: 700;
            color: {COLOR_TEXT} !important;
            line-height: 1.3;
            margin-bottom: 4px;
        }}

        .nx-card-desc {{
            font-size: 0.71rem;
            color: {settings.TEXT_MUTED} !important;
            line-height: 1.4;
        }}

        .nx-section-label {{
            font-size: 0.68rem;
            font-weight: 700;
            color: {settings.TEXT_MUTED} !important;
            text-transform: uppercase;
            letter-spacing: 2px;
            padding-bottom: 10px;
            border-bottom: 1px solid {COLOR_GOLD}30;
            margin-bottom: 2px;
        }}

        .nx-hero {{
            background: linear-gradient(135deg, {COLOR_SOFT} 0%, #0F1120 100%);
            border: 1px solid {COLOR_GOLD}33;
            border-radius: 16px;
            padding: 28px 32px;
            margin-bottom: 8px;
            position: relative;
            overflow: hidden;
        }}

        .nx-hero::before {{
            content: '';
            position: absolute;
            top: -40px; right: -40px;
            width: 180px; height: 180px;
            background: radial-gradient(circle, {COLOR_GOLD}15 0%, transparent 70%);
            pointer-events: none;
        }}

        .nx-hero-brand {{
            font-size: 0.72rem;
            font-weight: 600;
            color: {COLOR_GOLD} !important;
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-bottom: 4px;
        }}

        .nx-hero-title {{
            font-size: 2rem;
            font-weight: 800;
            color: {COLOR_TEXT} !important;
            line-height: 1.1;
            margin-bottom: 6px;
        }}

        .nx-hero-sub {{
            font-size: 0.82rem;
            color: {settings.TEXT_MUTED} !important;
        }}

        .nx-status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(16,185,129,0.12);
            border: 1px solid rgba(16,185,129,0.35);
            border-radius: 20px;
            padding: 4px 12px;
            font-size: 0.72rem;
            font-weight: 600;
            color: {settings.COLOR_SUCCESS} !important;
        }}

        .nx-status-badge.offline {{
            background: rgba(239,68,68,0.12);
            border-color: rgba(239,68,68,0.35);
            color: {settings.COLOR_CRITICAL} !important;
        }}

        /* ═══════════════════════════════════════════════════════════
           7. AG-GRID (Integración Obsidian & Piano)
           ═══════════════════════════════════════════════════════════ */
        .ag-theme-balham, .ag-theme-alpine-dark {{
            --ag-background-color: {COLOR_DEEP} !important;
            --ag-header-background-color: {COLOR_SOFT} !important;
            --ag-header-foreground-color: {COLOR_GOLD} !important;
            --ag-foreground-color: {COLOR_TEXT} !important;
            --ag-border-color: #334155 !important;
            --ag-row-hover-color: {COLOR_GOLD}11 !important;
            --ag-selected-row-background-color: {COLOR_GOLD}22 !important;
            --ag-odd-row-background-color: {COLOR_DEEP} !important;
            --ag-font-family: 'Inter', sans-serif !important;
            --ag-font-size: 13px;
        }}

        /* ═══════════════════════════════════════════════════════════
           8. SCROLLBARS
           ═══════════════════════════════════════════════════════════ */
        ::-webkit-scrollbar {{ width: 7px; height: 7px; }}
        ::-webkit-scrollbar-track {{ background: {COLOR_DEEP}; }}
        ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 10px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: {COLOR_GOLD}88; }}
        </style>
    """, unsafe_allow_html=True)

    print(f"✅ {settings.LOG_PREFIX} >>> ARMADURA OBSIDIAN v70.5.0 DESPLEGADA.")

def header_section(title, subtitle=None):
    """Encabezado Premium con subrayado en Oro."""
    st.markdown(f'<h1 style="font-size: 2.5rem; margin-bottom: 0;">{title}</h1>', unsafe_allow_html=True)
    st.markdown(f'<div style="height:4px; width:60px; background:{COLOR_GOLD}; border-radius:10px; margin-bottom:25px;"></div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<p style="color:{settings.TEXT_MUTED}; font-size:1.15rem; margin-top:-15px; font-weight:500;">{subtitle}</p>', unsafe_allow_html=True)

def card_style(titulo, valor):
    """Métricas Estilo Prestige (Geometría Obsidian)."""
    st.markdown(f"""
        <div class="rimec-card">
            <div style="color:{settings.TEXT_MUTED}; font-size:0.85rem; font-weight:600; text-transform:uppercase; letter-spacing:1px;">{titulo}</div>
            <div style="color:{COLOR_TEXT}; font-size:1.85rem; font-weight:800;">{valor}</div>
        </div>
    """, unsafe_allow_html=True)

def card_metric(titulo, valor, delta=None):
    """Alias de card_style para compatibilidad con el árbol de llamadas actual."""
    return card_style(titulo, valor)

# -----------------------------------------------------------------------------
# [EXECUTION-CONFIRMED] Se han aplicado los cambios de la TABLA DE EJECUCIÓN QUIRÚRGICA sobre el script core/styles.py
# -----------------------------------------------------------------------------