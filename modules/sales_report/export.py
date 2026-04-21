# =============================================================================
# SISTEMA: RIMEC Business Intelligence - NEXUS CORE
# UBICACIÓN: modules/sales_report/export.py
# VERSION: 100.1.0
# AUTOR: Héctor & Claude AI
# DESCRIPCIÓN: Puente de Exportación.
#               Orquesta la generación de PDFs delegando al ReportEngine.
# =============================================================================

from datetime import datetime
from core.settings import settings


class ExportManager:

    @staticmethod
    def get_template_context():
        """ADN Visual para Templates HTML (contexto institucional)."""
        return {
            "company_name": settings.COMPANY_NAME,
            "system_name":  settings.SYSTEM_NAME,
            "tagline":       settings.TAGLINE,
            "version":       settings.VERSION,
            "primary_color": settings.PDF_PRIMARY,
            "secondary_color": settings.UI_SECONDARY,
            "accent_color":  settings.UI_PRIMARY,
            "pos_color":     settings.PDF_VAR_POS,
            "neg_color":     settings.PDF_VAR_NEG,
            "subtotal_bg":   getattr(settings, 'PDF_SUBTOTAL_BG', '#E2E8F0'),
            "subtotal_text": settings.PDF_SUBTOTAL_TEXT,
            "timestamp":     datetime.now().strftime("%d/%m/%Y %H:%M"),
        }

    @staticmethod
    def generate_general_report(title, pkg_item, group_cols=None, meta_info=None,
                                show_total=True, mode="gerencial"):
        """
        Orquestador principal de PDF.
        mode="gerencial" → reporte ejecutivo con jerarquía y subtotales.
        mode="listado"   → listado informativo, fila completa sin ocultar repetidos.
        """
        from core.report_engine import ReportEngine

        df_to_print = pkg_item['data'] if isinstance(pkg_item, dict) and 'data' in pkg_item else pkg_item

        return ReportEngine.generate_pdf(
            title,
            df_to_print,
            group_cols=group_cols,
            meta_info=meta_info,
            show_total=show_total,
            mode=mode,
        )
