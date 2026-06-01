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

def apply_login_contrast():
    """Blindaje adicional del login perimetral contra prefers-color-scheme: light."""
    st.markdown(f"""
        <style>
        /* ═══════════════════════════════════════════════════════════
           9. LOGIN NEXUS CORE — contraste forzado (sin reglas globales *)
           ═══════════════════════════════════════════════════════════ */
        [data-testid="stAppViewContainer"]:has([data-testid="stForm"]) {{
            color-scheme: dark !important;
        }}

        [data-testid="stForm"] {{
            background: linear-gradient(160deg, {COLOR_SOFT} 0%, {COLOR_DEEP} 100%) !important;
            border: 1px solid {COLOR_GOLD}44 !important;
            border-radius: 16px !important;
            padding: 1.25rem 1.5rem 1.5rem !important;
            color-scheme: dark !important;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45) !important;
        }}

        [data-testid="stForm"] label,
        [data-testid="stForm"] [data-testid="stWidgetLabel"],
        [data-testid="stForm"] [data-testid="stWidgetLabel"] p,
        [data-testid="stForm"] [data-testid="stWidgetLabel"] span {{
            color: {COLOR_TEXT} !important;
            font-weight: 600 !important;
        }}

        [data-testid="stForm"] div[data-testid="stTextInput"] input,
        [data-testid="stForm"] div[data-testid="stTextInput"] textarea {{
            background-color: {COLOR_SOFT} !important;
            color: {COLOR_TEXT} !important;
            -webkit-text-fill-color: {COLOR_TEXT} !important;
            caret-color: {COLOR_TEXT} !important;
            border: 1px solid {COLOR_GOLD}66 !important;
            border-radius: 8px !important;
            color-scheme: dark !important;
        }}

        [data-testid="stForm"] div[data-testid="stTextInput"] input::placeholder {{
            color: {settings.TEXT_MUTED} !important;
            opacity: 1 !important;
        }}

        [data-testid="stForm"] div[data-testid="stTextInput"] input:focus {{
            border-color: {COLOR_GOLD} !important;
            box-shadow: 0 0 0 2px {COLOR_GOLD}33 !important;
            outline: none !important;
        }}

        [data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill,
        [data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill:hover,
        [data-testid="stForm"] div[data-testid="stTextInput"] input:-webkit-autofill:focus {{
            -webkit-box-shadow: 0 0 0 1000px {COLOR_SOFT} inset !important;
            -webkit-text-fill-color: {COLOR_TEXT} !important;
            caret-color: {COLOR_TEXT} !important;
            border: 1px solid {COLOR_GOLD}66 !important;
        }}

        [data-testid="stFormSubmitButton"] button,
        [data-testid="stForm"] div.stButton > button {{
            background-color: {COLOR_DEEP} !important;
            color: {COLOR_GOLD} !important;
            border: 2px solid {COLOR_GOLD} !important;
            font-weight: 800 !important;
            letter-spacing: 0.04em !important;
        }}

        [data-testid="stFormSubmitButton"] button:hover:not(:disabled),
        [data-testid="stForm"] div.stButton > button:hover:not(:disabled) {{
            background-color: {COLOR_GOLD} !important;
            color: {COLOR_DEEP} !important;
        }}

        [data-testid="stFormSubmitButton"] button:disabled,
        [data-testid="stForm"] div.stButton > button:disabled {{
            opacity: 0.45 !important;
            cursor: not-allowed !important;
            color: {settings.TEXT_MUTED} !important;
            border-color: {settings.TEXT_MUTED} !important;
        }}

        /* Título y caption del login (fuera del form, misma pantalla) */
        [data-testid="stMainBlockContainer"] h1,
        [data-testid="stMainBlockContainer"] [data-testid="stMarkdownContainer"] h1 {{
            color: {COLOR_TEXT} !important;
        }}

        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {{
            color: {settings.TEXT_MUTED} !important;
        }}

        /* Alertas login (credenciales inválidas / bloqueo) */
        [data-testid="stAlert"],
        [data-testid="stAlert"] [data-testid="stMarkdownContainer"],
        [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {{
            color: {COLOR_DEEP} !important;
        }}

        @media (prefers-color-scheme: light) {{
            [data-testid="stForm"] div[data-testid="stTextInput"] input,
            [data-testid="stForm"] div[data-testid="stTextInput"] textarea {{
                background-color: {COLOR_SOFT} !important;
                color: {COLOR_TEXT} !important;
                -webkit-text-fill-color: {COLOR_TEXT} !important;
            }}

            [data-testid="stForm"] label,
            [data-testid="stForm"] [data-testid="stWidgetLabel"],
            [data-testid="stForm"] [data-testid="stWidgetLabel"] p {{
                color: {COLOR_TEXT} !important;
            }}

            [data-testid="stFormSubmitButton"] button {{
                color: {COLOR_GOLD} !important;
            }}

            [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {{
                color: {COLOR_DEEP} !important;
            }}
        }}
        </style>
    """, unsafe_allow_html=True)


def apply_ui_theme():
    """Inyección de CSS: El blindaje Obsidian v70.5.0 — anti light-mode."""
    print(f"[STYLES] Sincronizando Armadura Obsidian v{settings.VERSION}")

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
            [data-testid="stAppViewContainer"],
            [data-testid="stHeader"],
            [data-testid="stMain"] {{
                background-color: {COLOR_DEEP} !important;
                color: {COLOR_TEXT} !important;
            }}
            p, span, label, h1, h2, h3, h4, h5, h6,
            [data-testid="stMarkdownContainer"] p,
            [data-testid="stMarkdownContainer"] span,
            [data-testid="stWidgetLabel"],
            [data-testid="stWidgetLabel"] p {{
                color: {COLOR_TEXT} !important;
            }}
            div.stButton > button {{ color: {COLOR_GOLD} !important; }}
            div.stButton > button:hover {{ color: {COLOR_DEEP} !important; }}
            a {{ color: {COLOR_GOLD} !important; }}
            div[data-testid="stTextInput"] input,
            div[data-testid="stTextInput"] textarea {{
                background-color: {COLOR_SOFT} !important;
                color: {COLOR_TEXT} !important;
                -webkit-text-fill-color: {COLOR_TEXT} !important;
                caret-color: {COLOR_TEXT} !important;
                border: 1px solid {COLOR_GOLD}55 !important;
                color-scheme: dark !important;
            }}
            div[data-testid="stTextInput"] input::placeholder {{
                color: {settings.TEXT_MUTED} !important;
                opacity: 1 !important;
            }}
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

        /* Inputs — legibles en modo claro del navegador (autofill / fondo claro) */
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextInput"] textarea,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextArea"] textarea {{
            background-color: {COLOR_SOFT} !important;
            color: {COLOR_TEXT} !important;
            -webkit-text-fill-color: {COLOR_TEXT} !important;
            caret-color: {COLOR_TEXT} !important;
            border: 1px solid {COLOR_GOLD}55 !important;
            border-radius: 8px !important;
            color-scheme: dark !important;
        }}

        div[data-testid="stTextInput"] input::placeholder,
        div[data-testid="stTextArea"] textarea::placeholder {{
            color: {settings.TEXT_MUTED} !important;
            opacity: 1 !important;
        }}

        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus,
        div[data-testid="stNumberInput"] input:focus {{
            border-color: {COLOR_GOLD} !important;
            box-shadow: 0 0 0 2px {COLOR_GOLD}33 !important;
            outline: none !important;
        }}

        div[data-testid="stTextInput"] input:-webkit-autofill,
        div[data-testid="stTextInput"] input:-webkit-autofill:hover,
        div[data-testid="stTextInput"] input:-webkit-autofill:focus {{
            -webkit-box-shadow: 0 0 0 1000px {COLOR_SOFT} inset !important;
            -webkit-text-fill-color: {COLOR_TEXT} !important;
            caret-color: {COLOR_TEXT} !important;
        }}

        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] span {{
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
           4. BOTONES / INPUTS: Controles profesionales y anti-wrap
           ═══════════════════════════════════════════════════════════ */
        div.stButton > button,
        div[data-testid="stDownloadButton"] > button {{
            border-radius: 11px !important;
            background: linear-gradient(180deg, #111827 0%, {COLOR_DEEP} 100%) !important;
            color: {COLOR_GOLD} !important;
            border: 1px solid {COLOR_GOLD}CC !important;
            font-weight: 800 !important;
            padding: 0.62rem 0.9rem !important;
            width: 100% !important;
            min-height: 42px !important;
            transition: all 0.20s ease !important;
            white-space: nowrap !important;
            word-break: keep-all !important;
            overflow-wrap: normal !important;
            line-height: 1.15 !important;
            letter-spacing: .01em !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 8px 20px rgba(0,0,0,0.18) !important;
        }}

        div.stButton > button *,
        div[data-testid="stDownloadButton"] > button * {{
            white-space: nowrap !important;
            word-break: keep-all !important;
            overflow-wrap: normal !important;
        }}

        div.stButton > button:hover,
        div[data-testid="stDownloadButton"] > button:hover {{
            background: linear-gradient(180deg, {COLOR_GOLD} 0%, #B99022 100%) !important;
            color: {COLOR_DEEP} !important;
            box-shadow: 0 0 20px {COLOR_GOLD}55 !important;
            transform: translateY(-1px) !important;
        }}

        div.stButton > button[kind="primary"],
        button[kind="primary"] {{
            background: linear-gradient(180deg, #16A34A 0%, #15803D 100%) !important;
            color: #FFFFFF !important;
            border-color: rgba(34,197,94,0.55) !important;
        }}

        input, textarea,
        [data-baseweb="input"] input,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"] textarea {{
            background-color: #111827 !important;
            color: {COLOR_TEXT} !important;
            border-color: rgba(212,175,55,0.28) !important;
            border-radius: 10px !important;
        }}

        input:disabled, textarea:disabled,
        [aria-disabled="true"] {{
            opacity: .92 !important;
            -webkit-text-fill-color: {COLOR_TEXT} !important;
        }}

        /* Inputs numericos: evita que el navegador claro los pinte ilegibles */
        [data-testid="stNumberInput"] input {{
            text-align: center !important;
            font-weight: 800 !important;
            font-variant-numeric: tabular-nums !important;
            background: #182235 !important;
            color: #F8FAFC !important;
        }}

        /* ═══════════════════════════════════════════════════════════
           4B. EXPANDERS / CONTENEDORES: acordeones limpios
           ═══════════════════════════════════════════════════════════ */
        [data-testid="stExpander"] {{
            border: 1px solid rgba(212,175,55,0.28) !important;
            border-radius: 14px !important;
            background: rgba(26,28,37,0.72) !important;
            overflow: hidden !important;
            box-shadow: 0 8px 26px rgba(0,0,0,0.18) !important;
            margin-bottom: .75rem !important;
        }}

        [data-testid="stExpander"] summary {{
            background: rgba(30,41,59,0.72) !important;
            color: {COLOR_TEXT} !important;
            font-weight: 800 !important;
            border-bottom: 1px solid rgba(255,255,255,0.05) !important;
        }}

        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary span {{
            color: {COLOR_TEXT} !important;
        }}

        .nx-action-panel {{
            border: 1px solid rgba(212,175,55,0.18);
            border-radius: 14px;
            background: linear-gradient(180deg, rgba(15,23,42,.96), rgba(11,13,23,.98));
            padding: 14px;
            margin: 8px 0 16px 0;
        }}

        .nx-editor-header {{
            background: linear-gradient(135deg, #162033 0%, #1F2A44 55%, #24314F 100%);
            border: 1px solid rgba(212,175,55,0.24);
            border-left: 4px solid {COLOR_GOLD};
            border-radius: 14px;
            padding: 16px 18px;
            margin: 14px 0 18px 0;
            box-shadow: 0 12px 28px rgba(0,0,0,.22);
        }}

        .nx-editor-header h3 {{
            color: {COLOR_TEXT} !important;
            margin: 0 !important;
            letter-spacing: -.02em !important;
        }}

        .nx-readonly-metric {{
            background: #121A2A;
            border: 1px solid rgba(212,175,55,0.22);
            border-radius: 10px;
            padding: 8px 12px;
            text-align: center;
            min-height: 54px;
        }}

        .nx-readonly-metric .label {{
            font-size: .64rem;
            color: {settings.TEXT_MUTED} !important;
            text-transform: uppercase;
            letter-spacing: .08em;
        }}

        .nx-readonly-metric .value {{
            font-size: 1.35rem;
            font-weight: 900;
            color: {COLOR_TEXT} !important;
            line-height: 1.15;
            font-variant-numeric: tabular-nums;
        }}

        .nx-readonly-metric .hint {{
            font-size: .70rem;
            color: #CBD5E1 !important;
            margin-top: 3px;
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

    print(f"[OK] {settings.LOG_PREFIX} >>> ARMADURA OBSIDIAN v70.5.0 DESPLEGADA.")

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