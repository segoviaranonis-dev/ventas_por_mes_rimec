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
            fid.pares,
            fid.cajas,
            fid.precio_unit,
            fid.subtotal,
            fid.precio_neto,
            fid.linea_snapshot,
            ppd.sku,
            pc.nombre as producto_nombre,
            pc.imagen_url,
            l.cod_linea as linea_codigo,
            r.cod_ref as ref_codigo,
            col.nombre as color_nombre
        FROM public.factura_interna_detalle fid
        LEFT JOIN public.pedido_proveedor_det ppd ON ppd.id = fid.ppd_id
        LEFT JOIN public.producto_cab pc ON pc.id = ppd.id_producto_cab
        LEFT JOIN public.linea l ON l.id = pc.id_linea
        LEFT JOIN public.referencia r ON r.id = pc.id_referencia
        LEFT JOIN public.color col ON col.id = ppd.id_color
        WHERE fid.factura_id = :fi_id
        ORDER BY fid.id
    """

    df_items = get_dataframe(items_query, {"fi_id": fi_id})
    items = []

    if df_items is not None and not df_items.empty:
        for _, row in df_items.iterrows():
            # Parsear linea_snapshot si existe
            import json
            snapshot = {}
            if row.get('linea_snapshot'):
                try:
                    if isinstance(row['linea_snapshot'], str):
                        snapshot = json.loads(row['linea_snapshot'])
                    else:
                        snapshot = row['linea_snapshot']
                except:
                    pass

            items.append({
                'linea_codigo': row['linea_codigo'] or snapshot.get('linea_codigo', '?'),
                'ref_codigo': row['ref_codigo'] or snapshot.get('ref_codigo', '?'),
                'color_nombre': row['color_nombre'] or snapshot.get('color_nombre', ''),
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

    # Header
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1E293B'),
        alignment=TA_CENTER,
        spaceAfter=10
    )

    story.append(Paragraph(f"<b>{settings.COMPANY_NAME}</b>", title_style))
    story.append(Paragraph(f"{settings.SYSTEM_NAME}", styles['Normal']))
    story.append(Spacer(1, 10*mm))

    # Título de la factura
    factura_style = ParagraphStyle(
        'FacturaTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.white,
        backColor=colors.HexColor(settings.UI_SECONDARY),
        borderPadding=5,
        alignment=TA_CENTER
    )

    story.append(Paragraph(
        f"<b>FACTURA INTERNA: {fi_data['nro_factura']}</b>",
        factura_style
    ))
    story.append(Spacer(1, 5*mm))

    # Info de la factura
    info_data = [
        ['<b>PP:</b>', fi_data.get('pp_nro', 'N/A'), '<b>Marca:</b>', fi_data.get('marca', 'N/A')],
        ['<b>Caso:</b>', fi_data.get('caso', 'N/A'), '<b>Estado:</b>', fi_data.get('estado', 'N/A')],
        ['<b>Cliente:</b>', fi_data.get('cliente_nombre', 'N/A')[:40], '<b>Vendedor:</b>', fi_data.get('vendedor_nombre', 'N/A')],
        ['<b>Plazo:</b>', fi_data.get('plazo_nombre', 'N/A'), '<b>Lista:</b>', f"LP{fi_data.get('lista_precio_id', 1)}"],
    ]

    info_table = Table(info_data, colWidths=[30*mm, 65*mm, 30*mm, 65*mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 8*mm))

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
        "Este documento es para uso interno y no genera obligaciones fiscales.",
        disclaimer_style
    ))
    story.append(Spacer(1, 8*mm))

    # Tabla de items
    if items:
        items_data = [['Producto', 'Gradas', 'Cajas', 'Pares', 'Precio Unit.', 'Subtotal']]

        for item in items:
            nombre = f"L{item['linea_codigo']}:R{item['ref_codigo']}"
            if item.get('color_nombre'):
                nombre += f"\n{item['color_nombre']}"

            items_data.append([
                nombre,
                item.get('gradas_fmt', ''),
                str(item['cajas']),
                str(item['pares']),
                f"Gs. {item['precio_unit']:,.0f}".replace(',', '.'),
                f"Gs. {item['subtotal']:,.0f}".replace(',', '.')
            ])

        items_table = Table(
            items_data,
            colWidths=[60*mm, 40*mm, 20*mm, 20*mm, 25*mm, 25*mm]
        )
        items_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(settings.PDF_PRIMARY)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 5*mm))

    # Totales
    subtotal = sum(i['subtotal'] for i in items)
    descuentos = [
        fi_data.get('descuento_1', 0) or 0,
        fi_data.get('descuento_2', 0) or 0,
        fi_data.get('descuento_3', 0) or 0,
        fi_data.get('descuento_4', 0) or 0
    ]
    descuentos_activos = [d for d in descuentos if d > 0]

    total_neto = subtotal
    for desc in descuentos_activos:
        total_neto = total_neto * (1 - desc / 100)

    total_data = [
        ['Subtotal:', f"Gs. {subtotal:,.0f}".replace(',', '.')],
        ['Descuentos:', ' + '.join([f"{d}%" for d in descuentos_activos]) if descuentos_activos else 'Sin descuento'],
        ['<b>TOTAL NETO:</b>', f"<b>Gs. {total_neto:,.0f}</b>".replace(',', '.')]
    ]

    total_table = Table(total_data, colWidths=[140*mm, 50*mm])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (0, 2), (-1, 2), 2, colors.HexColor(settings.PDF_PRIMARY)),
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor(settings.PDF_PRIMARY)),
    ]))
    story.append(total_table)

    # Footer
    story.append(Spacer(1, 10*mm))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#94A3B8'),
        alignment=TA_CENTER
    )
    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
    story.append(Paragraph(
        f"Generado por {settings.SYSTEM_NAME} · {timestamp}",
        footer_style
    ))

    # Construir PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


# [EXECUTION-CONFIRMED] v1.0.0 - PDF Factura Individual
