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
    """Inyección de CSS: El blindaje Obsidian v70.4.5."""
    print(f"🎨 [STYLES] Sincronizando Armadura Obsidian v{settings.VERSION}")

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        /* 1. RESET Y FONDO OBSIDIANA */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
            background-color: {COLOR_DEEP} !important;
            font-family: 'Inter', sans-serif !important;
            color: {COLOR_TEXT} !important;
        }}

        [data-testid="stSidebarNav"] {{ display: none !important; }}

        /* 2. SIDEBAR PROFESIONAL */
        [data-testid="stSidebar"] {{
            background-color: {COLOR_SOFT} !important;
            border-right: 1px solid {COLOR_GOLD}44;
        }}

        /* 3. TÍTULOS Y TEXTO */
        h1, h2, h3 {{
            color: {COLOR_TEXT} !important;
            font-weight: 800 !important;
            letter-spacing: -0.05em !important;
        }}

        /* 4. BOTONES: Estilo Prestige */
        div.stButton > button {{
            border-radius: 10px !important;
            background-color: {COLOR_DEEP} !important;
            color: {COLOR_GOLD} !important;
            border: 1px solid {COLOR_GOLD} !important;
            font-weight: 700 !important;
            padding: 0.5rem 1rem !important;
            width: 100% !important;
            transition: all 0.3s ease;
        }}

        div.stButton > button:hover {{
            background-color: {COLOR_GOLD} !important;
            color: {COLOR_DEEP} !important;
            box-shadow: 0 0 20px {COLOR_GOLD}66;
            transform: translateY(-2px);
        }}

        /* 5. CARDS DINÁMICAS (OBSIDIAN GLOW) */
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

        /* 6. ESTILO PARA AG-GRID (Integración Obsidian & Piano) */
        .ag-theme-balham {{
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

        /* Ajustes para Scrollbars en Obsidian Mode */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: {COLOR_DEEP}; }}
        ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 10px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: {COLOR_GOLD}88; }}
        </style>
    """, unsafe_allow_html=True)

    print(f"✅ {settings.LOG_PREFIX} >>> ARMADURA OBSIDIAN DESPLEGADA (v{settings.VERSION}).")

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