"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
MÓDULO: core/pdf_engine.py
VERSION: 2.0.0 (REPORTLAB ENGINE - Windows Compatible)
AUTOR: Héctor & Claude AI
DESCRIPCIÓN: Motor universal de generación de PDFs usando ReportLab.
             Compatible con Windows sin dependencias externas.

CAMBIOS v2.0.0:
    - Migrado de weasyprint a reportlab
    - Sin dependencias GTK+ (100% Python)
    - Compatible con Windows out-of-the-box
    - Mantiene la misma API pública

USO:
    from core.pdf_engine import PDFEngine

    pdf_bytes = PDFEngine.generate(
        template_name="factura_interna",
        context={...}
    )
"""

import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.platypus import Image as RLImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from core.settings import settings


class PDFEngine:
    """Motor universal de generación de PDFs usando ReportLab."""

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
        Genera un PDF usando ReportLab.

        NOTA: Los parámetros base_layout y css_file se mantienen por compatibilidad
        pero no se usan en la versión ReportLab.

        Args:
            template_name: Nombre del template (sin extensión)
            context: Diccionario con datos para el template
            base_layout: (No usado en v2.0)
            css_file: (No usado en v2.0)
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
        # Merge contexto base con contexto específico
        full_context = cls._get_base_context()
        full_context.update(context)

        # Crear PDF en memoria
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=15*mm,
        )

        # Construir contenido basado en el template
        story = []

        if template_name == "facturas/factura_interna":
            story = cls._build_factura_interna(full_context)
        else:
            # Template genérico
            story = cls._build_generic(full_context)

        # Generar PDF
        doc.build(story)

        if output_format == "bytes":
            pdf_bytes = buffer.getvalue()
            buffer.close()
            return pdf_bytes
        else:
            output_path = context.get('output_path', '/tmp/output.pdf')
            pdf_bytes = buffer.getvalue()
            buffer.close()
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            return output_path

    @classmethod
    def _build_factura_interna(cls, context: dict):
        """Construye el contenido del PDF de Factura Interna."""
        story = []
        styles = getSampleStyleSheet()

        # Estilo personalizado para título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1E293B'),
            spaceAfter=6,
            alignment=TA_CENTER
        )

        # Estilo para subtítulos
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#64748B'),
            spaceAfter=20,
            alignment=TA_CENTER
        )

        # Encabezado
        story.append(Paragraph(f"<b>{context['company_name']}</b>", title_style))
        story.append(Paragraph(context['system_name'], subtitle_style))
        story.append(Spacer(1, 10*mm))

        # Título del documento
        story.append(Paragraph(f"<b>{context.get('report_title', 'Factura Interna')}</b>", title_style))
        story.append(Spacer(1, 5*mm))

        # Información del pedido
        cliente_codigo = context.get('cliente_codigo', 0)
        cliente_nombre = context.get('cliente_nombre', 'N/A')
        cliente_display = f"{cliente_nombre} ({cliente_codigo})" if cliente_codigo else cliente_nombre

        pedido_data = [
            ['<b>Pedido:</b>', context.get('nro_pedido', 'N/A')],
            ['<b>Cliente:</b>', cliente_display],
            ['<b>Vendedor:</b>', context.get('vendedor_nombre', 'N/A')],
            ['<b>Plazo:</b>', context.get('plazo_nombre', 'N/A')],
            ['<b>Lista:</b>', context.get('lista_nombre', 'N/A')],
        ]

        pedido_table = Table(pedido_data, colWidths=[40*mm, 120*mm])
        pedido_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748B')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(pedido_table)
        story.append(Spacer(1, 10*mm))

        # Disclaimer
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#92400E'),
            backColor=colors.HexColor('#FEF3C7'),
            borderPadding=5,
        )
        story.append(Paragraph(
            "<b>⚠️ FACTURA PROVISORIA INTERNA (SIN VALOR LEGAL)</b><br/>"
            "Este documento es para uso interno y no genera obligaciones fiscales ni comerciales.",
            disclaimer_style
        ))
        story.append(Spacer(1, 10*mm))

        # Facturas
        for idx, factura in enumerate(context.get('facturas', [])):
            if idx > 0:
                story.append(Spacer(1, 8*mm))

            # Título de factura
            factura_style = ParagraphStyle(
                'FacturaTitle',
                parent=styles['Heading2'],
                fontSize=12,
                textColor=colors.white,
                backColor=colors.HexColor(context['secondary_color']),
                borderPadding=3,
            )
            story.append(Paragraph(
                f"⚡ {factura['nro_factura']} — {factura['marca']} · {factura['caso']}",
                factura_style
            ))
            story.append(Spacer(1, 3*mm))

            # Metadata de factura
            meta_data = [
                ['PP:', factura['pp_nro'], 'Marca:', factura['marca'], 'Caso:', factura['caso']]
            ]
            meta_table = Table(meta_data, colWidths=[15*mm, 45*mm, 20*mm, 40*mm, 15*mm, 40*mm])
            meta_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#64748B')),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ]))
            story.append(meta_table)
            story.append(Spacer(1, 3*mm))

            # Tabla de items (con imagen y material)
            items_data = [['', 'Producto', 'Gradas', 'Cj', 'Ps', 'Sin Desc', 'Con Desc', 'Subtotal']]

            for item in factura.get('items', []):
                # Imagen del producto (thumbnail pequeño)
                img_cell = ""
                if item.get('imagen_url'):
                    try:
                        import urllib.request
                        from urllib.error import URLError
                        # Intentar cargar imagen desde URL
                        with urllib.request.urlopen(item['imagen_url'], timeout=3) as response:
                            img_data = BytesIO(response.read())
                            img = RLImage(img_data, width=12*mm, height=12*mm)
                            img_cell = img
                    except (URLError, Exception):
                        # Si falla, usar placeholder
                        img_cell = "📦"
                else:
                    img_cell = "📦"

                # Nombre del producto con material
                producto_nombre = f"{item['linea_codigo']}-{item['ref_codigo']}"
                if item.get('nombre'):  # Material
                    producto_nombre += f"\n{item['nombre']}"
                if item.get('color_nombre'):
                    producto_nombre += f"\n{item['color_nombre']}"

                items_data.append([
                    img_cell,
                    producto_nombre,
                    item.get('gradas_fmt', ''),
                    str(item.get('cajas', 0)),
                    str(item.get('pares', 0)),
                    f"Gs. {item.get('precio_unit', 0):,.0f}".replace(',', '.'),
                    f"Gs. {item.get('precio_neto', 0):,.0f}".replace(',', '.'),
                    f"Gs. {item.get('subtotal', 0):,.0f}".replace(',', '.')
                ])

            items_table = Table(
                items_data,
                colWidths=[15*mm, 45*mm, 28*mm, 12*mm, 12*mm, 22*mm, 22*mm, 24*mm]
            )
            items_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(context['primary_color'])),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ]))
            story.append(items_table)
            story.append(Spacer(1, 3*mm))

            # Totales
            total_data = [
                ['Subtotal:', f"Gs. {factura['subtotal']:,.0f}".replace(',', '.')],
                ['Descuentos:', f"-Gs. {factura['descuentos_aplicados']:,.0f}".replace(',', '.')],
                ['<b>TOTAL:</b>', f"<b>Gs. {factura['total_neto']:,.0f}</b>".replace(',', '.')]
            ]
            total_table = Table(total_data, colWidths=[140*mm, 50*mm])
            total_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('LINEABOVE', (0, 2), (-1, 2), 2, colors.HexColor(context['primary_color'])),
                ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor(context['primary_color'])),
            ]))
            story.append(total_table)

        # Total General
        story.append(Spacer(1, 10*mm))
        total_general_style = ParagraphStyle(
            'TotalGeneral',
            parent=styles['Normal'],
            fontSize=14,
            textColor=colors.white,
            backColor=colors.HexColor(context['primary_color']),
            borderPadding=8,
            alignment=TA_CENTER
        )
        story.append(Paragraph(
            f"<b>TOTAL GENERAL DEL PEDIDO</b><br/>"
            f"<font size=20>Gs. {context.get('total_general', 0):,.0f}</font><br/>".replace(',', '.') +
            f"{context.get('total_pares_general', 0)} pares · "
            f"{len(context.get('facturas', []))} factura(s)",
            total_general_style
        ))

        # Footer
        story.append(Spacer(1, 10*mm))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.HexColor('#94A3B8'),
            alignment=TA_CENTER
        )
        story.append(Paragraph(
            f"Generado por {context['system_name']} · {context['timestamp']}",
            footer_style
        ))

        return story

    @classmethod
    def _build_generic(cls, context: dict):
        """Construye un PDF genérico simple."""
        story = []
        styles = getSampleStyleSheet()

        title = context.get('report_title', 'Reporte')
        story.append(Paragraph(f"<b>{title}</b>", styles['Title']))
        story.append(Spacer(1, 12))

        body = context.get('body', 'Sin contenido')
        story.append(Paragraph(body, styles['Normal']))

        return story

    @classmethod
    def generate_from_html(cls, html_string: str, css_string: str = None):
        """
        Genera PDF desde HTML string directo.
        NOTA: En v2.0 con ReportLab, el soporte HTML es limitado.
        """
        raise NotImplementedError(
            "generate_from_html no está implementado en la versión ReportLab. "
            "Usa generate() con template_name en su lugar."
        )

    @classmethod
    def validate_template(cls, template_name: str) -> bool:
        """Verifica si un template existe."""
        # En v2.0, los templates son funciones Python, no archivos
        return template_name in ["facturas/factura_interna", "generic"]


# Función de conveniencia para uso rápido
def generate_pdf(template_name: str, context: dict, **kwargs):
    """
    Shortcut para generar PDFs.

    Example:
        from core.pdf_engine import generate_pdf

        pdf = generate_pdf("factura_interna", {
            "report_title": "Mi Reporte",
            "data": [...]
        })
    """
    return PDFEngine.generate(template_name, context, **kwargs)


# [EXECUTION-CONFIRMED] v2.0.0 - ReportLab Engine (Windows Compatible)
