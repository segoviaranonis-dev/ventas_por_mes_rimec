# =============================================================================
# SISTEMA: RIMEC Business Intelligence - NEXUS CORE
# UBICACIÓN: core/theme_manager.py
# VERSION: 104.4.2 (PIANO PALETTE - JERARQUÍA TÁCTICA & PRECISIÓN)
# AUTOR: Héctor & Gemini AI
# DESCRIPCIÓN: Dictador de Estilo. Centraliza la estética de UI y PDF.
#                v104.4.2: REQ-02 - Consolidación de Paleta Strict Piano.
#                Inyección de códigos Hex exactos (#0B0D17, #D4AF37) y
#                lógica de niveles para renderizado de jerarquía.
# =============================================================================

import numpy as np
from core.settings import settings
from core.constants import META_PREFIX, PK_SOURCE, DNA_MONEY, DNA_RATIO # Inyección Protocolo Olympus

# CONSTANTES DE PROTOCOLO (Sincronizadas con logic.py a través de core.constants)
UNDEFINED_STATE = "---"
INFINITY_SYMBOL = "∞"
CRITICAL_GAP_SYMBOL = "—"

class ThemeManager:
    """
    CEREBRO VISUAL NEXUS:
    Punto único de control para la estética bancaria RIMEC.
    """

    _deployed = False

    @staticmethod
    def _trace(category, msg):
        """Microfonía de auditoría visual."""
        print(f"🎨 [{category}] {msg}")

    @classmethod
    def get_rendering_specs(cls):
        """
        CONTRATO DE RENDERIZADO PDF/UI:
        Centraliza el layout para ajustes globales de densidad de datos.
        """
        return {
            'pct_precision': 2,
            'currency_precision': 0,
            'grid_theme': 'ag-theme-balham',
            'pdf_font_size': getattr(settings, 'UI_CONFIG', {}).get('pdf_font_size', 6.2),
            'pdf_margin': getattr(settings, 'UI_CONFIG', {}).get('pdf_padding', 2),
            'font_family_mono': "'Courier', 'Inter', monospace", # Proyecta autoridad técnica
            'header_height': 40
        }

    @classmethod
    def get_pdf_colors(cls):
        """Paleta institucional para ReportLab (Grado FMI)."""
        return {
            'HEADER_BG': getattr(settings, 'PDF_PRIMARY', '#0055A4'),
            'HEADER_TEXT': '#FFFFFF',
            'TEXT_MAIN': '#334155',
            'MONEY': '#1E293B',
            'SUCCESS': getattr(settings, 'PDF_VAR_POS', '#059669'),
            'CRITICAL': getattr(settings, 'PDF_VAR_NEG', '#DC2626'),
            'NEUTRAL': "#64748B",  # Slate 500 (Para estados UNDEFINED)
            'META_LABEL': "#475569"
        }

    @classmethod
    def get_pdf_piano_style(cls, level):
        """
        DUALIDAD DE PIANO (LADO PDF).
        Lee desde settings.PIANO_PDF_MAP — modificar colores solo en settings.py.
        """
        piano_map = getattr(settings, 'PIANO_PDF_MAP', {})
        entry = piano_map.get(level, {"bg": "#FFFFFF", "text": "#334155"})
        return {"bg": entry.get("bg", "#FFFFFF"), "text": entry.get("text", "#334155")}

    @classmethod
    def get_ui_piano_style(cls, level):
        """
        DUALIDAD DE PIANO (LADO UI) - STRICT PIANO.
        Lee desde settings.PIANO_GEOMETRY_MAP — modificar colores solo en settings.py.
        """
        # Pesos visuales por nivel (no dependen del color, son constantes de UX)
        _weights = {0: "bold", 1: "600", 2: "normal"}

        piano_map = getattr(settings, 'PIANO_GEOMETRY_MAP', {})
        entry     = piano_map.get(level, {})

        return {
            "bg":     entry.get("bg_ui",   "#0B0D17"),
            "text":   entry.get("text_ui", "#94A3B8"),
            "name":   entry.get("name",    f"Nivel {level}"),
            "weight": _weights.get(level, "normal"),
        }

    @classmethod
    def get_row_style_by_pk(cls, row_data, metadata_store, mode='UI'):
        """
        SINCRONÍA DE ID:
        Consume el metadata_store usando el ID de la fila como puntero láser.
        """
        pk_val = row_data.get(PK_SOURCE)
        meta = metadata_store.get(pk_val, {})
        level = meta.get(f"{META_PREFIX}LEVEL", 0)

        if mode == 'UI':
            return cls.get_ui_piano_style(level)
        return cls.get_pdf_piano_style(level)

    @classmethod
    def get_semaphore_color(cls, value, objective=0.0, level=0):
        """
        SEMÁFORO BINARIO DIAMOND (BASE 1) - GLOW DYNAMICS:
        Aplica colores vibrantes con opacidad simulada para la Variación.
        """
        if value == UNDEFINED_STATE or value is None or (isinstance(value, float) and np.isnan(value)):
            return "#64748B"

        try:
            val_num = float(value)
            hierarchical_matrix = {
                0: ("#10B981", "#EF4444"), # Éxito / Crítico
                1: ("#34D399", "#F87171"),
                2: ("#6EE7B7", "#FCA5A5"),
            }
            c_pos, c_neg = hierarchical_matrix.get(level, ("#10B981", "#EF4444"))

            if val_num >= objective:
                return c_pos
            return c_neg

        except (ValueError, TypeError):
            return "#64748B"

    @classmethod
    def get_export_metadata_style(cls):
        """CONTRATO DE EXPORTACIÓN (METADATA)"""
        return {
            'fontName': 'Courier-Bold',
            'fontSize': 6.5,
            'textColor': cls.get_pdf_colors()['META_LABEL'],
            'letterSpacing': 0.5,
            'alignment': 1
        }

    @classmethod
    def format_value_visual(cls, value, type_id):
        """
        INTERCEPTOR DE SIMBOLOGÍA CRÍTICA (Fase 4 - REGLAS DE EXCEPCIÓN):
        Trata errores matemáticos como 0/0 o divisiones por cero.
        """
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return UNDEFINED_STATE

        # Gestión de Ratios / Porcentajes
        if type_id == DNA_RATIO:
            if isinstance(value, (float, int)) and np.isinf(value):
                return INFINITY_SYMBOL

            if isinstance(value, (float, int)) and value > 999999:
                 return CRITICAL_GAP_SYMBOL

            if value == 0 and settings.get('STRICT_EMPTY_CHECK', False):
                return CRITICAL_GAP_SYMBOL

        return value

    @classmethod
    def apply_dna_formatting(cls, column_name, dna_map):
        """
        MAPEO DE ADN VISUAL - PROTOCOLO DE MONEDA LOCAL (Fase 4):
        Configura el renderizado basado en DNA_ IDs.

        [REGLA QUIRÚRGICA]:
        - Montos (DNA_MONEY): 0 decimales, separador de miles por punto (.).
        - Ratios (DNA_RATIO): 2 decimales, separador decimal por coma (,).
        """
        type_id = dna_map.get(column_name)

        if type_id == DNA_RATIO:
            return {
                "precision": 2,
                "suffix": "%",
                "align": "right",
                "font_weight": "bold",
                "thousand_separator": ".",
                "decimal_separator": ","
            }

        if type_id == DNA_MONEY:
            return {
                "precision": 0,          # ELIMINACIÓN TOTAL DE DECIMALES (Contable)
                "suffix": "",
                "align": "right",
                "font_weight": "normal",
                "thousand_separator": ".", # SEPARADOR DE MILES LOCAL (.)
                "decimal_separator": ""    # BLINDAJE CONTRA DECIMALES EN MONTOS
            }

        return {"precision": None, "suffix": "", "align": "left", "font_weight": "normal"}

# --- INICIALIZACIÓN ---
if not ThemeManager._deployed:
    ThemeManager._trace("THEME-AUTH", f"Protocolo Diamante v104.4 Activo. [PALETA: STRICT PIANO]")
    ThemeManager._deployed = True

# -----------------------------------------------------------------------------
# [EXECUTION-CONFIRMED] Se han aplicado los cambios de la TABLA DE EJECUCIÓN QUIRÚRGICA sobre el script core/theme_manager.py
# -----------------------------------------------------------------------------