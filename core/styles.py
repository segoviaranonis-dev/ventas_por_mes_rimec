"""
SISTEMA: CHUNACHUNA IMPORT Business Intelligence - NEXUS CORE
UBICACIÓN: core/styles.py
VERSION: 70.4.2 (OBSIDIAN ELITE - FINAL SYNC)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: El Ejecutor Visual de Elite.
             Sincronización total de la Armadura Obsidian.
             REPARACIÓN: Reintegración de card_metric para evitar colapso de importación.
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

def apply_ui_theme():
    """Inyección de CSS: El blindaje Obsidian v70.4.2."""
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

# 🚨 COMPATIBILIDAD CRUCIAL: Alias para evitar el ImportError en main.py / home.py
def card_metric(titulo, valor, delta=None):
    """Alias de card_style para compatibilidad con el árbol de llamadas actual."""
    return card_style(titulo, valor)