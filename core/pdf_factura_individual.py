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
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from core.database import get_dataframe
from core.settings import settings


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
            fi.marca,
            fi.caso,
            fi.total_pares,
            fi.total_monto,
            fi.estado,
            fi.cliente_id,
            c.descp_cliente as cliente_nombre,
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
                'cajas': int(row['cajas']) if row['cajas'] else 0,
                'pares': int(row['pares']) if row['pares'] else 0,
                'precio_unit': float(row['precio_unit'] or 0),
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

    # Título de la factura (Navy ejecutivo)
    factura_style = ParagraphStyle(
        'FacturaTitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.white,
        backColor=colors.HexColor('#1B3A6B'),  # NAVY
        borderPadding=8,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    story.append(Paragraph(
        f"FACTURA INTERNA · {fi_data['nro_factura']}",
        factura_style
    ))
    story.append(Spacer(1, 6*mm))

    # Info de la factura (estilo ejecutivo)
    fecha_creacion = fi_data.get('created_at')
    if fecha_creacion:
        if hasattr(fecha_creacion, 'strftime'):
            fecha_str = fecha_creacion.strftime('%d/%m/%Y')
        else:
            fecha_str = str(fecha_creacion)[:10]
    else:
        fecha_str = 'N/A'

    info_data = [
        ['<b>Pedido Proveedor:</b>', fi_data.get('pp_nro', 'N/A'), '<b>Marca:</b>', fi_data.get('marca', 'N/A')],
        ['<b>Caso:</b>', fi_data.get('caso', 'N/A'), '<b>Estado:</b>', fi_data.get('estado', 'RESERVADA')],
        ['<b>Cliente:</b>', fi_data.get('cliente_nombre', 'N/A')[:45], '<b>Fecha:</b>', fecha_str],
        ['<b>Vendedor:</b>', fi_data.get('vendedor_nombre', 'N/A')[:45], '<b>Plazo:</b>', fi_data.get('plazo_nombre', 'N/A')],
        ['<b>Lista de Precio:</b>', f"Lista {fi_data.get('lista_precio_id', 1)}", '', ''],
    ]

    info_table = Table(info_data, colWidths=[38*mm, 57*mm, 30*mm, 65*mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1B3A6B')),  # Labels en NAVY
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#1B3A6B')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 7*mm))

    # Disclaimer (ejecutivo, menos alarmista)
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#1B3A6B'),
        backColor=colors.HexColor('#E4EEF7'),  # Azul suave ejecutivo
        borderPadding=8,
        alignment=TA_CENTER,
        leftIndent=10,
        rightIndent=10
    )
    story.append(Paragraph(
        "<b>DOCUMENTO DE USO INTERNO</b><br/>"
        "Factura provisoria sin valor legal. No genera obligaciones fiscales ni comerciales.",
        disclaimer_style
    ))
    story.append(Spacer(1, 7*mm))

    # Tabla de items (estilo ejecutivo IMF)
    if items:
        items_data = [['Producto', 'Gradas', 'Cajas', 'Pares', 'Precio/Par', 'Subtotal']]

        for item in items:
            # Formato producto: Línea:Ref + Color
            nombre = f"<b>{item['linea_codigo']}-{item['ref_codigo']}</b>"
            if item.get('color_nombre'):
                nombre += f"<br/><font size=7>{item['color_nombre']}</font>"

            items_data.append([
                Paragraph(nombre, styles['Normal']),
                item.get('gradas_fmt', 'N/A'),
                str(item['cajas']),
                str(item['pares']),
                f"₲ {item['precio_unit']:,.0f}".replace(',', '.'),
                f"₲ {item['subtotal']:,.0f}".replace(',', '.')
            ])

        items_table = Table(
            items_data,
            colWidths=[55*mm, 45*mm, 18*mm, 18*mm, 27*mm, 27*mm]
        )
        items_table.setStyle(TableStyle([
            # Header (NAVY ejecutivo)
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B3A6B')),  # NAVY
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (1, 0), 'LEFT'),
            ('ALIGN', (2, 0), (-1, 0), 'CENTER'),

            # Datos
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),

            # Bordes y fondos
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#D4AF37')),  # Línea dorada bajo header
            ('GRID', (0, 1), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 6*mm))

    # Totales (sección ejecutiva)
    subtotal = sum(i['subtotal'] for i in items)
    descuentos = [
        fi_data.get('descuento_1', 0) or 0,
        fi_data.get('descuento_2', 0) or 0,
        fi_data.get('descuento_3', 0) or 0,
        fi_data.get('descuento_4', 0) or 0
    ]
    descuentos_activos = [d for d in descuentos if d > 0]

    total_neto = subtotal
    monto_descuento = 0
    for desc in descuentos_activos:
        total_neto = total_neto * (1 - desc / 100)
    monto_descuento = subtotal - total_neto

    # Total de pares
    total_pares = sum(i['pares'] for i in items)
    total_cajas = sum(i['cajas'] for i in items)

    total_data = []

    # Subtotal
    total_data.append(['Subtotal:', f"₲ {subtotal:,.0f}".replace(',', '.')])

    # Descuentos si existen
    if descuentos_activos:
        desc_text = ' + '.join([f"{d}%" for d in descuentos_activos])
        total_data.append([f'Descuentos ({desc_text}):', f"- ₲ {monto_descuento:,.0f}".replace(',', '.')])

    # Total Neto (destacado)
    total_data.append([
        '<b>TOTAL NETO:</b>',
        f'<b>₲ {total_neto:,.0f}</b>'.replace(',', '.')
    ])

    # Resumen cantidades
    total_data.append([
        f'<font size=8>({total_cajas} cajas · {total_pares} pares)</font>',
        ''
    ])

    total_table = Table(total_data, colWidths=[135*mm, 55*mm])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -3), 10),
        ('FONTSIZE', (0, -2), (-1, -2), 14),
        ('FONTSIZE', (0, -1), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR', (0, 0), (-1, -3), colors.HexColor('#334155')),
        ('TEXTCOLOR', (0, -2), (-1, -2), colors.HexColor('#1B3A6B')),  # NAVY para total
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#64748B')),
        ('LINEABOVE', (0, -2), (-1, -2), 2, colors.HexColor('#D4AF37')),  # Línea dorada
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
