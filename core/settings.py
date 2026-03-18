"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
UBICACIÓN: core/settings.py
VERSION: 94.3.0 (STRICT SEPARATION - PIANO PDF)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: El Cerebro del Rascacielos. Blindado contra colapsos de UI.
             MODIFICACIÓN V94.3: 
             1. Separación Radical: PIANO_PDF y PIANO_UI son ahora independientes.
             2. Piano PDF (4 Niveles): MARCA, CLIENTE, CADENA, VENDEDOR.
             3. Fix Fatal: Restauradas claves 'bg_ui' y 'text_ui' para evitar KeyError en AG Grid.
"""

import os
import time

class BrandConfig:
    # --- 1. IDENTIDAD CORPORATIVA ---
    COMPANY_NAME = "RIMEC"
    SYSTEM_NAME = "NEXUS CORE"
    TAGLINE = "Sales Intelligence Engine"
    EDITION = "Obsidian & Strict Piano"
    VERSION = "94.3.0" 
    LOG_PREFIX = f"[{SYSTEM_NAME}]"

    # --- 2. EL CONTRATO DE COLOR UI (MANTENIDO ORO/OBSIDIANA) ---
    UI_PRIMARY = "#D4AF37"
    UI_SECONDARY = "#1A1C25"
    UI_BACKGROUND = "#0B0D17"
    TEXT_DARK = "#0B0D17"
    TEXT_LIGHT = "#F8FAFC"
    TEXT_MUTED = "#94A3B8"
    COLOR_SUCCESS = "#10B981"
    COLOR_CRITICAL = "#EF4444"

    # --- 3. CONTRATO PDF (ESTÉTICA SLIM) ---
    PDF_PRIMARY = "#0055A4"    # Azul Francia (Headers)
    PDF_SECONDARY = "#FFFFFF"
    PDF_TEXT_MAIN = "#334155"
    PDF_TEXT_MONEY = "#1E293B"
    PDF_VAR_POS = "#059669"
    PDF_VAR_NEG = "#DC2626"
    PDF_SUBTOTAL_TEXT = "#000000"

    # --- 4. [PIANO PDF] - JERARQUÍA PARA REPORTES (COLORES SOLICITADOS) ---
    # SEPARADO de la UI para evitar colisiones.
    PIANO_PDF_MAP = {
        0: {"name": "Nivel 1: MARCA",    "bg": "#F7E5B7", "text": "#000000"},
        1: {"name": "Nivel 2: CLIENTE",  "bg": "#D3EADA", "text": "#000000"},
        2: {"name": "Nivel 3: CADENA",   "bg": "#FFE6BB", "text": "#000000"},
        3: {"name": "Nivel 4: VENDEDOR", "bg": "#BCD8EC", "text": "#000000"}
    }

    # --- 5. [PIANO UI] - JERARQUÍA PARA AG-GRID (RESTAURADO) ---
    # Estas claves NO deben tocarse para que el ui.py no colapse.
    PIANO_GEOMETRY_MAP = {
        0: {
            "name": "Maestro",
            "bg_ui": UI_PRIMARY,
            "text_ui": TEXT_DARK,
            "border": UI_PRIMARY
        },
        1: {
            "name": "Táctico",
            "bg_ui": UI_SECONDARY,
            "text_ui": TEXT_LIGHT,
            "border": "#475569"
        },
        2: {
            "name": "Detalle",
            "bg_ui": "#334155",
            "text_ui": "#CBD5E1",
            "border": "#1E293B"
        }
    }

    # --- 6. CONFIGURACIÓN DE INTERFAZ (SLIM MODE) ---
    UI_CONFIG = {
        "grid_theme": "ag-theme-alpine-dark", 
        "auto_expand_level": 1,
        "precision_currency": 0,
        "precision_pct": 2,
        "pdf_font_size": 6.2,
        "pdf_padding": 2
    }

    # --- 7. GESTIÓN DE RUTAS ---
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CORE_DIR = os.path.join(BASE_DIR, "core")
    STATIC_REPORTS_DIR = os.path.join(CORE_DIR, "static", "reports")

    @classmethod
    def get_terminal_banner(cls):
        width = 65
        line = "═" * width
        return (
            f"\n{line}\n"
            f"   {cls.COMPANY_NAME} • {cls.SYSTEM_NAME} v{cls.VERSION}\n"
            f"   STATUS: STRICT PIANO SYNC READY\n"
            f"   FECHA: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{line}\n"
        )

# --- [INICIALIZACIÓN] ---
print(BrandConfig.get_terminal_banner())
settings = BrandConfig