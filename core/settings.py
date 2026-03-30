"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
UBICACIÓN: core/settings.py
VERSION: 100.3.1 (PLAN 3: PROTOCOLO DE HIERRO - NIVEL DIAMANTE)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: El Cerebro del Rascacielos. Blindado contra colapsos de UI.
              MODIFICACIÓN V100.3.1:
              Fase 2 - Blindaje de SCHEMA_MAP y Sincronización de Alias.
              Vínculo estricto con motor SQL v72 para evitar duplicidad.
"""

import os
import time
import threading
from core.constants import ALIAS_CURRENT_VALUE, ALIAS_TARGET_VALUE, ALIAS_VARIATION

class BrandConfig:
    # --- 1. IDENTIDAD CORPORATIVA ---
    COMPANY_NAME = "RIMEC"
    SYSTEM_NAME = "NEXUS CORE"
    TAGLINE = "Sales Intelligence Engine"
    EDITION = "Obsidian & Strict Piano"
    VERSION = "100.3.1"
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

    # --- 3. CONTRATO PDF (ESTÉTICA EJECUTIVA - IMF STYLE) ---
    PDF_PRIMARY = "#0055A4"    # Azul Francia (Headers)
    PDF_SECONDARY = "#FFFFFF"
    PDF_TEXT_MAIN = "#334155"
    PDF_TEXT_MONEY = "#1E293B"
    PDF_VAR_POS = "#059669"
    PDF_VAR_NEG = "#DC2626"
    PDF_SUBTOTAL_TEXT = "#000000"

    # --- 3B. PALETA PDF EJECUTIVA (IMF STYLE) ---
    # Modificar aquí afecta SOLO los PDFs generados por report_engine.py
    # La sección UI (arriba) permanece completamente independiente.
    PDF_PALETTE = {
        # Estructura principal
        'NAVY':      '#1B3A6B',   # Header de tabla + L0 subtotal
        'NAVY_MID':  '#2D5080',   # L1 subtotal (Cadena)
        'SLATE':     '#334155',   # Texto principal de datos
        'MUTED':     '#64748B',   # Texto secundario (cabecera doc)
        'BORDER':    '#CBD5E1',   # Línea de borde normal
        'BORDER_LT': '#E2E8F0',   # Línea de borde suave
        'BG_ALT':    '#F8FAFC',   # Fondo filas alternadas
        'WHITE':     '#FFFFFF',
        # Jerarquía de fondos de subtotales (del más oscuro al más suave)
        'BG_L0':     '#1B3A6B',   # Nivel 0 (ej. Vendedor) → navy oscuro
        'BG_L1':     '#3A6EA8',   # Nivel 1 (ej. Cadena)   → azul medio
        'BG_L2':     '#C5D9EE',   # Nivel 2 (ej. Cliente)  → azul suave
        'BG_L3':     '#E4EEF7',   # Nivel 3 (ej. Marca)    → celeste leve
        # Texto sobre cada fondo de subtotal
        'TXT_L0':    '#FFFFFF',
        'TXT_L1':    '#FFFFFF',
        'TXT_L2':    '#1B3A6B',
        'TXT_L3':    '#2D5080',
        # Semáforo y acento
        'SUCCESS':   '#059669',
        'CRITICAL':  '#DC2626',
        'GOLD':      '#D4AF37',   # Separador dorado (línea bajo header)
    }

    # --- 4. [PIANO PDF] - JERARQUÍA PARA REPORTES ---
    PIANO_PDF_MAP = {
        0: {"name": "Nivel 1: MARCA",    "bg": "#F7E5B7", "text": "#000000"},
        1: {"name": "Nivel 2: CLIENTE",  "bg": "#D3EADA", "text": "#000000"},
        2: {"name": "Nivel 3: CADENA",   "bg": "#FFE6BB", "text": "#000000"},
        3: {"name": "Nivel 4: VENDEDOR", "bg": "#BCD8EC", "text": "#000000"}
    }

    # --- 5. [PIANO UI] - JERARQUÍA PARA AG-GRID ---
    # NOTA: Las claves bg_ui/text_ui son el contrato visual aprobado por el cliente.
    # No modificar sin aprobación. styles_sales_report.py v70.4.1 las lee directamente.
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

    # --- 6. CONFIGURACIÓN DE INTERFAZ (SLIM MODE + NEXUS V100) ---
    UI_CONFIG = {
        "grid_theme": "ag-theme-alpine-dark",
        "auto_expand_level": 1,
        "precision_currency": 0,
        "precision_pct": 2,
        "pdf_font_size": 6.2,
        "pdf_padding": 2
    }

    UI_LAYOUT = {
        "CELL_PADDING": 2.5,
        "PCT_PRECISION": 2,
        "CURRENCY_PRECISION": 0
    }

    # ─────────────────────────────────────────────────────────────────────────────
    # INYECCIÓN: SCHEMA MAP - CEREBRO DEL AGNOSTICISMO TEMPORAL (v100.3.1)
    # ─────────────────────────────────────────────────────────────────────────────
    # [BLINDAJE QUIRÚRGICO] Sincronización absoluta con motor SQL v72.
    # Evita que aparezcan columnas técnicas (monto_2026) y fuerza el uso de ALIAS.
    SCHEMA_MAP = {
        'CURRENT_YEAR': 2026,
        'TARGET_YEAR': 2025,
        'COLUMNS': {
            # Mapeo de Ventas
            'SALES_REAL': ALIAS_CURRENT_VALUE,    # Mapeo -> "Monto 26"
            'SALES_OBJ':  ALIAS_TARGET_VALUE,     # Mapeo -> "Monto Obj"
            'VARIATION':  ALIAS_VARIATION,        # Mapeo -> "Variación %"
            'CLIENT_ID':  'codigo_cliente',
            'VENDOR_ID':  'vendedor',
            'CHAIN':      'cadena',

            # Mapeo de Identificadores Motor SQL v72
            'sql_real_col': ALIAS_CURRENT_VALUE,
            'sql_goal_col': ALIAS_TARGET_VALUE,
            'sql_diff_col': ALIAS_VARIATION
        }
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
            f"   STATUS: SCHEMA SYNC READY (MOTOR v72)\n"
            f"   FECHA: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{line}\n"
        )

    @staticmethod
    def safe_log_async(msg, level="INFO"):
        def _async_task(m, l):
            try:
                from core.database import DBInspector
                DBInspector.log(m, l)
            except Exception:
                pass

        thread = threading.Thread(target=_async_task, args=(msg, level), daemon=True)
        thread.start()

    @classmethod
    def get_column_alias(cls, logical_name):
        """Retorna el nombre físico de la columna según el SCHEMA_MAP."""
        return cls.SCHEMA_MAP['COLUMNS'].get(logical_name, logical_name)

    @classmethod
    def get(cls, key, default=None):
        return getattr(cls, key, default)

# --- [INICIALIZACIÓN] ---
if __name__ == "__main__":
    print(BrandConfig.get_terminal_banner())

settings = BrandConfig

# -----------------------------------------------------------------------------
# [EXECUTION-CONFIRMED] Se han aplicado los cambios de la TABLA DE EJECUCIÓN QUIRÚRGICA sobre el script core/settings.py
# -----------------------------------------------------------------------------