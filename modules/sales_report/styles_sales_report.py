"""
SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
UBICACIÓN: modules/sales_report/styles_sales_report.py
VERSION: 70.4.1 (THE PIANO OVERHAUL - OBSIDIAN & GOLD)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Motor de Estética AgGrid de Lujo.
             Implementa Piano Geometry v70.4.1 con blindaje Enterprise.
             Sincronización total con la lógica de "Dilema del Cálculo".
"""

from st_aggrid import JsCode
from core.settings import settings

class SalesGridStyles:
    """
    Motor de Estética Unificado (Armadura Obsidian).
    Convierte tablas de datos en monitores tácticos mediante inyección de JS y CSS.
    """

    @staticmethod
    def get_value_formatter(is_pct=False):
        """Estandariza el formato de números (de-DE) con protección contra Nulos."""
        js_is_pct = 'true' if is_pct else 'false'
        precision = settings.UI_CONFIG.get('precision_pct' if is_pct else 'precision_currency', 0)

        return JsCode(f"""
            function(params) {{
                if (params.value == null || isNaN(params.value)) return '';
                let val = parseFloat(params.value);

                // Formato Alemán para consistencia financiera (1.250,00)
                let formatted = val.toLocaleString('de-DE', {{
                    minimumFractionDigits: {precision},
                    maximumFractionDigits: {precision}
                }});
                return {js_is_pct} ? formatted + '%' : formatted;
            }}
        """)

    @staticmethod
    def get_conditional_formatting():
        """
        Glow Dynamics: Semáforo táctico para variaciones.
        Aplica un resplandor (glow) sutil para diferenciar éxito de criticidad.
        """
        c_success = settings.COLOR_SUCCESS
        c_critical = settings.COLOR_CRITICAL

        return JsCode(f"""
            function(params) {{
                if (params.value === null || params.value === undefined || isNaN(params.value)) return null;

                const styles = {{
                    'fontWeight': 'bold',
                    'textAlign': 'right',
                    'borderRadius': '4px',
                    'paddingRight': '10px',
                    'transition': 'all 0.3s ease'
                }};

                if (params.value > 0.0001) {{
                    styles['color'] = '{c_success}';
                    styles['backgroundColor'] = '{c_success}15';
                    styles['borderRight'] = '3px solid {c_success}aa';
                    return styles;
                }} else if (params.value < -0.0001) {{
                    styles['color'] = '{c_critical}';
                    styles['backgroundColor'] = '{c_critical}15';
                    styles['borderRight'] = '3px solid {c_critical}aa';
                    return styles;
                }}
                return {{'textAlign': 'right', 'color': '{settings.TEXT_LIGHT}'}};
            }}
        """)

    @staticmethod
    def get_piano_geometry():
        """
        Piano Geometry v70.4.1: Jerarquía de niveles por color.
        Nivel 0: Obsidian Deep & Gold (La Raíz del Poder).
        Nivel 1: Carbon & Snow (El Nivel Táctico).
        Nivel 2: Steel & Slate (El Detalle Técnico).
        """
        p_map = settings.PIANO_GEOMETRY_MAP
        ui_gold = settings.UI_PRIMARY
        ui_deep = settings.UI_BACKGROUND

        return JsCode(f"""
            function(params) {{
                const styles = {{ 'transition': 'background 0.2s' }};

                // 1. BLINDAJE DE TOTALES (Footer y Pinned Rows)
                if (params.node.footer || params.node.rowPinned === 'bottom') {{
                    styles['backgroundColor'] = '{ui_deep}';
                    styles['color'] = '{ui_gold}';
                    styles['fontWeight'] = '900';
                    styles['fontSize'] = '1rem';
                    styles['borderTop'] = '2px solid {ui_gold}66';
                    styles['textTransform'] = 'uppercase';
                    return styles;
                }}

                // 2. LÓGICA DE NIVELES (Enterprise Hierarchy)
                if (params.node.group) {{
                    const level = params.node.level;
                    if (level === 0) {{
                        // PRESTIGE GOLD: Para el primer nivel de agrupamiento
                        styles['backgroundColor'] = '{ui_deep}';
                        styles['color'] = '{ui_gold}';
                        styles['fontWeight'] = 'bold';
                        styles['letterSpacing'] = '0.5px';
                        styles['borderBottom'] = '1px solid {ui_gold}22';
                    }} else if (level === 1) {{
                        // CARBON LEVEL: Para el segundo nivel
                        styles['backgroundColor'] = '{p_map[1]["bg_ui"]}';
                        styles['color'] = '{p_map[1]["text_ui"]}';
                        styles['fontWeight'] = '600';
                    }}
                    return styles;
                }}

                // 3. FILA DE DETALLE (Hoja final)
                return {{
                    'backgroundColor': '{p_map[2]["bg_ui"]}',
                    'color': '{p_map[2]["text_ui"]}',
                    'fontSize': '0.85rem',
                    'opacity': '0.9'
                }};
            }}
        """)

    @staticmethod
    def get_header_overrides():
        """
        Inyección de CSS Global para AgGrid.
        Fuerza al motor Enterprise a usar el tema Obsidian.
        """
        grid_theme = settings.UI_CONFIG.get('grid_theme', 'ag-theme-balham-dark')
        gold = settings.UI_PRIMARY
        deep = settings.UI_BACKGROUND

        return f"""
        <style>
            /* Contenedor Principal del Grid */
            .{grid_theme} {{
                --ag-header-background-color: {deep} !important;
                --ag-header-foreground-color: {gold} !important;
                --ag-border-color: {gold}22 !important;
                --ag-row-hover-color: {gold}15 !important;
                --ag-selected-row-background-color: {gold}25 !important;
                --ag-odd-row-background-color: {deep} !important;
                --ag-font-family: 'Inter', 'Segoe UI', sans-serif !important;
                --ag-grid-size: 4px;
                border-radius: 8px !important;
                border: 1px solid {gold}33 !important;
            }}

            /* Headers: Fuerza la estética de élite */
            .{grid_theme} .ag-header-cell {{
                border-bottom: 2px solid {gold}44 !important;
            }}

            .{grid_theme} .ag-header-cell-label {{
                justify-content: center;
                text-transform: uppercase;
                letter-spacing: 1.2px;
                font-weight: 800 !important;
                font-size: 0.75rem;
            }}

            /* Iconos de flechitas (Chevron) en Oro */
            .{grid_theme} .ag-group-expanded,
            .{grid_theme} .ag-group-contracted {{
                color: {gold} !important;
            }}

            /* Scrollbars tipo Cyberpunk */
            .{grid_theme} ::-webkit-scrollbar {{
                width: 8px;
                height: 8px;
            }}
            .{grid_theme} ::-webkit-scrollbar-thumb {{
                background: {gold}33 !important;
                border-radius: 10px;
            }}
            .{grid_theme} ::-webkit-scrollbar-thumb:hover {{
                background: {gold}88 !important;
            }}
        </style>
        """

# [EXECUTION-CONFIRMED] v70.4.1 restaurado — aspecto aprobado por cliente.
