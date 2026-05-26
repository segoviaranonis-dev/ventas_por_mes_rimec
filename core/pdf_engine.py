"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
MÓDULO: core/pdf_engine.py
VERSION: 1.0.0 (UNIVERSAL HTML→PDF ENGINE)
AUTOR: Héctor & Claude AI
DESCRIPCIÓN: Motor universal de generación de PDFs desde HTML + Jinja2.
             Convive con ReportEngine (ReportLab) sin conflictos.

ARQUITECTURA:
    HTML Template (Jinja2)
         ↓
    Renderizado con contexto
         ↓
    weasyprint (HTML → PDF)
         ↓
    PDF bytes

USO:
    from core.pdf_engine import PDFEngine

    pdf_bytes = PDFEngine.generate(
        template_name="factura_interna",
        context={...},
        base_layout="main_layout"  # usa main_layout.html
    )
"""

import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from datetime import datetime
from io import BytesIO

from core.settings import settings


class PDFEngine:
    """Motor universal de generación de PDFs desde HTML."""

    # Rutas base
    BASE_DIR = Path(__file__).parent.parent
    TEMPLATES_DIR = BASE_DIR / "templates"
    STATIC_DIR = BASE_DIR / "core" / "static"

    # Ambiente Jinja2
    _jinja_env = None

    @classmethod
    def _get_jinja_env(cls):
        """Inicializa el ambiente Jinja2 (lazy loading)."""
        if cls._jinja_env is None:
            cls._jinja_env = Environment(
                loader=FileSystemLoader([
                    str(cls.TEMPLATES_DIR),
                    str(cls.BASE_DIR / "core" / "static" / "reports"),
                    str(cls.BASE_DIR / "modules" / "sales_report"),
                ]),
                autoescape=select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True
            )
        return cls._jinja_env

    @classmethod
    def _get_base_context(cls):
        """Contexto base con variables institucionales."""
        return {
            # Identidad corporativa
            "company_name": settings.COMPANY_NAME,
            "system_name": settings.SYSTEM_NAME,
            "tagline": settings.TAGLINE,
            "version": settings.VERSION,

            # Colores dinámicos desde settings
            "primary_color": settings.PDF_PRIMARY,
            "secondary_color": settings.UI_SECONDARY,
            "accent_color": settings.UI_PRIMARY,
            "critical_color": getattr(settings, 'PDF_VAR_NEG', '#EF4444'),

            # Metadatos
            "timestamp": datetime.now().strftime('%d/%m/%Y %H:%M'),
            "security_tag": "CONFIDENCIAL - USO INTERNO",

            # Otros
            "footer_text": f"Generado por {settings.SYSTEM_NAME}",
        }

    @classmethod
    def generate(
        cls,
        template_name: str,
        context: dict,
        base_layout: str = "main_layout",
        css_file: str = None,
        output_format: str = "bytes"
    ):
        """
        Genera un PDF desde una plantilla HTML.

        Args:
            template_name: Nombre del template (sin .html)
            context: Diccionario con datos para el template
            base_layout: Layout base a usar (default: main_layout.html)
            css_file: CSS adicional (opcional)
            output_format: "bytes" o "file"

        Returns:
            bytes del PDF o path del archivo

        Example:
            pdf = PDFEngine.generate(
                template_name="factura_interna",
                context={
                    "report_title": "Factura Interna",
                    "facturas": [...],
                    "total_general": 10144800
                }
            )
        """
        env = cls._get_jinja_env()

        # Merge contexto base con contexto específico
        full_context = cls._get_base_context()
        full_context.update(context)

        # Renderizar contenido específico
        try:
            content_template = env.get_template(f"{template_name}.html")
            content_html = content_template.render(**full_context)
        except Exception as e:
            # Si no existe template específico, usar el contenido directo
            content_html = context.get('module_content', '')
            if not content_html:
                raise ValueError(f"Template '{template_name}.html' no encontrado y no hay module_content")

        # Renderizar layout base
        full_context['module_content'] = content_html

        try:
            layout_template = env.get_template(f"{base_layout}.html")
            final_html = layout_template.render(**full_context)
        except Exception as e:
            # Fallback: usar el contenido sin layout
            final_html = content_html

        # CSS adicional
        stylesheets = []
        if css_file:
            css_path = cls.STATIC_DIR / "reports" / css_file
            if css_path.exists():
                stylesheets.append(CSS(filename=str(css_path)))

        # Generar PDF
        html_doc = HTML(string=final_html, base_url=str(cls.BASE_DIR))

        if output_format == "bytes":
            return html_doc.write_pdf(stylesheets=stylesheets)
        else:
            # Guardar en archivo temporal o ruta especificada
            output_path = context.get('output_path', '/tmp/output.pdf')
            html_doc.write_pdf(output_path, stylesheets=stylesheets)
            return output_path

    @classmethod
    def generate_from_html(cls, html_string: str, css_string: str = None):
        """
        Genera PDF desde HTML string directo (sin template).
        Útil para casos ad-hoc o testing.

        Args:
            html_string: HTML completo
            css_string: CSS adicional (opcional)

        Returns:
            bytes del PDF
        """
        html_doc = HTML(string=html_string)
        stylesheets = []

        if css_string:
            stylesheets.append(CSS(string=css_string))

        return html_doc.write_pdf(stylesheets=stylesheets)

    @classmethod
    def validate_template(cls, template_name: str) -> bool:
        """Verifica si un template existe."""
        env = cls._get_jinja_env()
        try:
            env.get_template(f"{template_name}.html")
            return True
        except:
            return False


# Función de conveniencia para uso rápido
def generate_pdf(template_name: str, context: dict, **kwargs):
    """
    Shortcut para generar PDFs.

    Example:
        from core.pdf_engine import generate_pdf

        pdf = generate_pdf("mi_reporte", {
            "report_title": "Mi Reporte",
            "data": [...]
        })
    """
    return PDFEngine.generate(template_name, context, **kwargs)


# [EXECUTION-CONFIRMED] v1.0.0 - Universal HTML→PDF Engine
