"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
MODULO: modules/sales_report/export.py
VERSION: 93.8.0 (METADATA BRIDGE - PROXY SEGURO)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Gestor de exportación y puente de ADN visual para HTML/PDF.
              MODIFICACIÓN V93.8: 
              1. Habilitación de canal meta_info para trazabilidad de filtros.
              2. Sincronización de semáforo con ReportEngine central.
              3. Preservación de CSS Blindado para integridad numérica.
"""

import pandas as pd
from datetime import datetime
from core.settings import settings

class ExportManager:
    """
    Motor de Proxy hacia el ReportEngine Central con soporte de Layout HTML.
    """

    @staticmethod
    def get_template_context():
        """
        Prepara el ADN visual para el renderizador HTML/PDF.
        Aquí se define la estética que recibirá el template report_template.html.
        """
        return {
            "company_name": settings.COMPANY_NAME,
            "system_name": settings.SYSTEM_NAME,
            "tagline": settings.TAGLINE,
            "version": settings.VERSION,
            
            # --- COLORES DE MARCA ---
            "primary_color": settings.PDF_PRIMARY,      # Azul Francia
            "secondary_color": settings.UI_SECONDARY,   # Obsidiana
            "accent_color": settings.UI_PRIMARY,        # Oro Real (para detalles)
            
            # --- SEMÁFORO DE VARIACIÓN ---
            "pos_color": settings.PDF_VAR_POS,          # Verde Bosque
            "neg_color": settings.PDF_VAR_NEG,          # Rojo Sangre
            
            # --- SUBTOTALES (PASTEL FUERTE) ---
            "subtotal_bg": settings.PDF_SUBTOTAL_BG,    # Azul Acero Fuerte
            "subtotal_text": settings.PDF_SUBTOTAL_TEXT, # Negro Puro
            
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "security_tag": "CONFIDENCIAL - USO INTERNO"
        }

    @staticmethod
    def get_injected_css():
        """
        Retorna el bloque de CSS blindado para garantizar la integridad numérica
        y el efecto escala en el renderizado HTML.
        """
        return f"""
        <style>
            /* LEY DE INTEGRIDAD NUMÉRICA: Prohibido romper números */
            .money, .pct-cell {{
                text-align: right !important;
                white-space: nowrap !important;
                padding-right: 4px !important;
                padding-left: 2px !important;
                font-variant-numeric: tabular-nums;
            }}

            /* SEMÁFORO DINÁMICO */
            .val-positive {{ color: {settings.PDF_VAR_POS}; font-weight: bold; }}
            .val-negative {{ color: {settings.PDF_VAR_NEG}; font-weight: bold; }}

            /* EFECTO ESCALA - SUB_TOTALES */
            .row-subtotal {{
                background-color: {settings.PDF_SUBTOTAL_BG} !important;
                color: {settings.PDF_SUBTOTAL_TEXT} !important;
                font-weight: bold;
            }}

            /* La celda de la izquierda en un subtotal debe ser blanca 
               para mantener el efecto escalera si no pertenece al grupo */
            .empty-stair {{
                background-color: #FFFFFF !important;
                border: none !important;
            }}
        </style>
        """

    @staticmethod
    def generate_general_report(title, df_input, group_cols=None, meta_info=None):
        """
        Delega la responsabilidad al motor central ReportEngine.
        ReportEngine ya utiliza los colores de settings para el dibujo directo.
        
        CIRUGÍA V93.8: Se añade meta_info para que el semáforo PDF responda
        al objetivo configurado en los filtros.
        """
        from core.report_engine import ReportEngine
        return ReportEngine.generate_pdf(title, df_input, group_cols, meta_info=meta_info)