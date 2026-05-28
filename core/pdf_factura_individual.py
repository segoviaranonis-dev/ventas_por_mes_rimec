"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
MÓDULO: core/pdf_factura_individual.py
VERSION: 1.0.0 (PDF DE FI INDIVIDUAL)
AUTOR: Héctor & Claude AI
DESCRIPCIÓN: Genera PDF de UNA factura interna individual.

USO:
    from core.pdf_factura_individual import generar_pdf_fi_individual

    pdf_bytes = generar_pdf_fi_individual(fi_id=123)
"""

from typing import Optional
from datetime import datetime, timedelta
from io import BytesIO
import re
import requests
from PIL import Image

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.platypus import Image as RLImage

from core.database import get_dataframe
from core.settings import settings


def _get_image_from_url(url: str, max_width: float = 15*mm, max_height: float = 15*mm) -> Optional[RLImage]:
    """
    Descarga una imagen desde URL y la convierte a RLImage redimensionada.

    Args:
        url: URL de la imagen
        max_width: Ancho máximo en mm
        max_height: Alto máximo en mm

    Returns:
        RLImage o None si falla
    """
    if not url:
        return None

    try:
        # Descargar imagen
        response = requests.get(url, timeout=3)
        if response.status_code != 200:
            return None

        # Abrir con PIL
        img_buffer = BytesIO(response.content)
        pil_img = Image.open(img_buffer)

        # Calcular dimensiones manteniendo aspect ratio
        aspect = pil_img.width / pil_img.height
        if aspect > 1:  # Imagen ancha
            width = max_width
            height = max_width / aspect
        else:  # Imagen alta
            height = max_height
            width = max_height * aspect

        # Crear RLImage
        img_buffer.seek(0)
        rl_img = RLImage(img_buffer, width=width, height=height)
        return rl_img

    except Exception as e:
        # Si falla, retornar None (no imagen)
        return None


def generar_pdf_fi_individual(fi_id: int) -> Optional[bytes]:
    """
    Genera el PDF de UNA factura interna individual.

    Args:
        fi_id: ID de la factura_interna

    Returns:
        bytes del PDF o None si hay error
    """
    # 1. Obtener datos de la FI
    fi_query = """
        SELECT
            fi.id,
            fi.nro_factura,
            fi.pp_id,
            pp.numero_registro as pp_nro,
            pp.numero_proforma as proforma,
            qa.descripcion as quincena_llegada,
            fi.marca,
            fi.caso,
            fi.total_pares,
            fi.total_monto,
            fi.estado,
            fi.cliente_id,
            c.descp_cliente as cliente_nombre,
            c.id_cliente as cliente_codigo,
            fi.vendedor_id,
            v.descp_usuario as vendedor_nombre,
            fi.plazo_id,
            pl.descp_plazo as plazo_nombre,
            fi.lista_precio_id,
            fi.descuento_1,
            fi.descuento_2,
            fi.descuento_3,
            fi.descuento_4,
            fi.created_at
        FROM public.factura_interna fi
        LEFT JOIN public.pedido_proveedor pp ON pp.id = fi.pp_id
        LEFT JOIN public.quincena_arribo qa ON qa.id = pp.quincena_arribo_id
        LEFT JOIN public.cliente_v2 c ON c.id_cliente = fi.cliente_id
        LEFT JOIN public.usuario_v2 v ON v.id_usuario = fi.vendedor_id
        LEFT JOIN public.plazo_v2 pl ON pl.id_plazo = fi.plazo_id
        WHERE fi.id = :fi_id
        LIMIT 1
    """

    df_fi = get_dataframe(fi_query, {"fi_id": fi_id})
    if df_fi is None or df_fi.empty:
        raise ValueError(f"Factura Interna ID {fi_id} no encontrada")

    fi_data = df_fi.iloc[0].to_dict()

    # 2. Obtener items de la FI
    items_query = """
        SELECT
            fid.id,
            fid.cajas,
            fid.pares,
            fid.precio_unit,
            fid.subtotal,
            fid.precio_neto,
            fid.linea_snapshot
        FROM public.factura_interna_detalle fid
        WHERE fid.factura_id = :fi_id
        ORDER BY fid.id
    """

    df_items = get_dataframe(items_query, {"fi_id": fi_id})
    items = []

    if df_items is not None and not df_items.empty:
        for _, row in df_items.iterrows():
            # Parsear linea_snapshot (puede venir como dict, JSON string, o Python dict string)
            import json
            import ast

            snapshot = {}
            if row.get('linea_snapshot'):
                try:
                    ls = row['linea_snapshot']
                    if isinstance(ls, dict):
                        # Ya es dict
                        snapshot = ls
                    elif isinstance(ls, str):
                        # Intentar como JSON primero
                        try:
                            snapshot = json.loads(ls)
                        except json.JSONDecodeError:
                            # Si falla, intentar como dict de Python (comillas simples)
                            snapshot = ast.literal_eval(ls)
                    else:
                        snapshot = {}
                except Exception as e:
                    # Si todo falla, dejar vacío
                    snapshot = {}

            items.append({
                'linea_codigo': snapshot.get('linea_codigo', '?'),
                'ref_codigo': snapshot.get('ref_codigo', '?'),
                'color_nombre': snapshot.get('color_nombre', ''),
                'gradas_fmt': snapshot.get('gradas_fmt', ''),
                'imagen_url': snapshot.get('imagen_url', ''),
                'cajas': int(row['cajas']) if row['cajas'] else 0,
                'pares': int(row['pares']) if row['pares'] else 0,
                'precio_unit': float(row['precio_unit'] or 0),
                'precio_neto': float(row['precio_neto'] or 0),
                'subtotal': float(row['subtotal'] or 0),
            })

    # 3. Generar PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm,
    )

    story = []
    styles = getSampleStyleSheet()

    # Header Corporativo Nexus
    company_style = ParagraphStyle(
        'CompanyName',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1B3A6B'),  # NAVY
        alignment=TA_CENTER,
        spaceAfter=2,
        fontName='Helvetica-Bold'
    )

    system_style = ParagraphStyle(
        'SystemName',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#D4AF37'),  # GOLD
        alignment=TA_CENTER,
        spaceAfter=3
    )

    story.append(Paragraph(f"<b>{settings.COMPANY_NAME}</b>", company_style))
    story.append(Paragraph(settings.SYSTEM_NAME, system_style))
    story.append(Spacer(1, 3*mm))

    # Línea dorada separadora
    from reportlab.platypus import HRFlowable
    story.append(HRFlowable(
        width="100%",
        thickness=2,
        color=colors.HexColor('#D4AF37'),
        spaceAfter=8*mm
    ))

    # HEADER = NOMBRE DEL CLIENTE (la estrella del documento)
    cliente_header_style = ParagraphStyle(
        'ClienteHeader',
        parent=styles['Heading2'],
        fontSize=15,
        textColor=colors.white,
        backColor=colors.HexColor('#1B3A6B'),  # NAVY
        borderPadding=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    cliente_nombre = fi_data.get('cliente_nombre', 'CLIENTE NO ASIGNADO')
    cliente_codigo = fi_data.get('cliente_codigo', '')
    # Agregar código de cliente al lado del nombre
    if cliente_codigo:
        cliente_display = f"{cliente_nombre} ({cliente_codigo})"
    else:
        cliente_display = cliente_nombre
    story.append(Paragraph(cliente_display, cliente_header_style))
    story.append(Spacer(1, 5*mm))

    # JERARQUÍA 1: ETA LLEGADA (fecha del pedido proveedor)
    eta_style = ParagraphStyle(
        'ETADestacado',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#D4AF37'),  # Dorado
        fontName='Helvetica-Bold',
        alignment=TA_LEFT,
        spaceAfter=2
    )

    # JERARQUÍA 2: VENDEDORA
    vendedora_style = ParagraphStyle(
        'VendedoraDestacado',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748B'),
        fontName='Helvetica',
        alignment=TA_LEFT,
        spaceAfter=8
    )

    vendedor_nombre = fi_data.get('vendedor_nombre', 'N/A')

    # Quincena de llegada (cable de acero reforzado)
    quincena_llegada = fi_data.get('quincena_llegada', 'A CONFIRMAR')

    story.append(Paragraph(f"Llegada: {quincena_llegada}", eta_style))
    story.append(Paragraph(f"Vendedora: {vendedor_nombre}", vendedora_style))
    story.append(Spacer(1, 3*mm))

    # Info complementaria (datos secundarios)
    fecha_doc = fi_data.get('created_at')
    if fecha_doc:
        if hasattr(fecha_doc, 'strftime'):
            fecha_str = fecha_doc.strftime('%d/%m/%Y')
        else:
            fecha_str = str(fecha_doc)[:10]
    else:
        fecha_str = 'N/A'

    # Matrimonio PP + Proforma
    pp_display = fi_data.get('pp_nro', 'N/A')
    if fi_data.get('proforma'):
        pp_display = f"{pp_display} ({fi_data['proforma']})"

    # Plazo de la factura
    plazo_nombre = fi_data.get('plazo_nombre', 'N/A')

    # Descuentos (siempre mostrar las 4 casillas)
    desc_1 = fi_data.get('descuento_1', 0) or 0
    desc_2 = fi_data.get('descuento_2', 0) or 0
    desc_3 = fi_data.get('descuento_3', 0) or 0
    desc_4 = fi_data.get('descuento_4', 0) or 0
    descuentos_display = f"{desc_1}% / {desc_2}% / {desc_3}% / {desc_4}%"

    info_data = [
        ['Nro. FI:', fi_data.get('nro_factura', 'N/A'), 'PP:', pp_display],
        ['Marca:', fi_data.get('marca', 'N/A'), 'Plazo:', plazo_nombre],
        ['Estado:', fi_data.get('estado', 'RESERVADA'), 'Fecha:', fecha_str],
        ['Descuentos:', descuentos_display, '', ''],
    ]

    info_table = Table(info_data, colWidths=[22*mm, 73*mm, 22*mm, 73*mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748B')),  # Gris suave
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#64748B')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#E2E8F0')),  # Líneas sutiles
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5*mm))

    # Disclaimer minimalista
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#64748B'),
        backColor=colors.HexColor('#F8FAFC'),  # Gris muy suave
        borderPadding=6,
        alignment=TA_CENTER,
    )
    story.append(Paragraph(
        "Documento de uso interno - Sin valor legal",
        disclaimer_style
    ))
    story.append(Spacer(1, 5*mm))

    # Tabla de items (estilo ejecutivo IMF con imágenes)
    if items:
        items_data = [['Foto', 'Producto', 'Gradas', 'Cajas', 'Pares', 'Precio Sin Desc.', 'Precio Con Desc.', 'Subtotal']]

        for item in items:
            # Descargar imagen del producto
            img = _get_image_from_url(item.get('imagen_url', ''), max_width=12*mm, max_height=12*mm)
            if not img:
                # Placeholder si no hay imagen
                img = Paragraph('<font size=6 color="#94A3B8">Sin<br/>imagen</font>', styles['Normal'])

            # Formato producto: Línea-Ref + Color
            nombre = f"<b>{item['linea_codigo']}-{item['ref_codigo']}</b>"
            if item.get('color_nombre'):
                nombre += f"<br/><font size=7 color='#64748B'>{item['color_nombre'][:40]}</font>"

            items_data.append([
                img,
                Paragraph(nombre, styles['Normal']),
                item.get('gradas_fmt', 'N/A'),
                str(item['cajas']),
                str(item['pares']),
                f"Gs. {item['precio_unit']:,.0f}".replace(',', '.'),
                f"Gs. {item['precio_neto']:,.0f}".replace(',', '.'),
                f"Gs. {item['subtotal']:,.0f}".replace(',', '.')
            ])

        items_table = Table(
            items_data,
            colWidths=[15*mm, 35*mm, 30*mm, 14*mm, 14*mm, 22*mm, 22*mm, 25*mm]
        )
        items_table.setStyle(TableStyle([
            # Header (NAVY ejecutivo)
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B3A6B')),  # NAVY
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),  # Foto centrada
            ('ALIGN', (1, 0), (2, 0), 'LEFT'),    # Producto y Gradas a la izquierda
            ('ALIGN', (3, 0), (-1, 0), 'CENTER'), # Resto centrado

            # Datos
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (1, 1), (-1, -1), 7),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Imágenes centradas
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),  # Números a la derecha
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Padding (reducido para acomodar más columnas)
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),

            # Bordes y fondos
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#D4AF37')),  # Línea dorada bajo header
            ('GRID', (0, 1), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 6*mm))

    # Totales (sección ejecutiva)
    # IMPORTANTE: Los subtotales de cada item YA tienen el descuento aplicado
    # porque usan precio_neto (que incluye descuentos).
    # NO debemos aplicar descuentos otra vez aquí.
    total_neto = sum(i['subtotal'] for i in items)

    # Total de pares
    total_pares = sum(i['pares'] for i in items)
    total_cajas = sum(i['cajas'] for i in items)

    total_data = []

    # Total Neto directo (sin línea de descuentos porque ya está aplicado en precios)
    total_data.append([
        'TOTAL NETO:',
        f"Gs. {total_neto:,.0f}".replace(',', '.')
    ])

    # Resumen cantidades (sin tags font, solo texto)
    total_data.append([
        f'({total_cajas} cajas - {total_pares} pares)',
        ''
    ])

    total_table = Table(total_data, colWidths=[135*mm, 55*mm])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -2), (0, -2), 'Helvetica-Bold'),  # Solo label en bold
        ('FONTNAME', (1, -2), (1, -2), 'Helvetica-Bold'),  # Monto en bold
        ('FONTSIZE', (0, 0), (-1, -3), 10),
        ('FONTSIZE', (0, -2), (-1, -2), 14),
        ('FONTSIZE', (0, -1), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR', (0, 0), (-1, -3), colors.HexColor('#334155')),
        ('TEXTCOLOR', (0, -2), (-1, -2), colors.HexColor('#1B3A6B')),  # NAVY para total
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#64748B')),
        ('LINEABOVE', (0, -2), (-1, -2), 1.5, colors.HexColor('#D4AF37')),  # Línea dorada
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(total_table)

    # Footer corporativo
    story.append(Spacer(1, 12*mm))

    # Línea separadora antes del footer
    story.append(HRFlowable(
        width="100%",
        thickness=1,
        color=colors.HexColor('#CBD5E1'),
        spaceAfter=4*mm
    ))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#64748B'),
        alignment=TA_CENTER
    )

    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
    story.append(Paragraph(
        f"<b>{settings.COMPANY_NAME}</b> · {settings.SYSTEM_NAME} v{settings.VERSION}<br/>"
        f"Generado el {timestamp}",
        footer_style
    ))

    # Construir PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


# [EXECUTION-CONFIRMED] v1.0.0 - PDF Factura Individual
