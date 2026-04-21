"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
MODULO: core/report_engine.py
VERSION: 101.0.0 (EXECUTIVE MINIMAL - IMF STYLE)
AUTOR: Héctor & Claude AI
DESCRIPCIÓN: Motor PDF estilo ejecutivo minimalista.
             - Cabecera limpia y profesional
             - Un único encabezado de tabla (sin repetición por grupo)
             - Sin subtotales redundantes en el último nivel de agrupación
             - Columna _path y técnicas ocultas automáticamente
             - Jerarquía visual por indentación y color sutil
"""

import numpy as np
import pandas as pd
from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, HRFlowable, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch

from core.settings import settings

# ─────────────────────────────────────────────────────────────────────────────
# PALETA EJECUTIVA — leída desde settings.PDF_PALETTE (fuente única de verdad)
# Para cambiar colores del PDF: editar core/settings.py → PDF_PALETTE
# ─────────────────────────────────────────────────────────────────────────────
_P = settings.PDF_PALETTE


def _c(hex_color):
    """Convierte hex a color ReportLab."""
    try:
        return colors.HexColor(hex_color)
    except Exception:
        return colors.HexColor('#334155')


class ReportEngine:

    @staticmethod
    def _fmt(val, col_name='', obj_puro=0.20, colorize=False):
        """Formatea un valor numérico o porcentual para el PDF."""
        if val is None:
            return ''
        try:
            if isinstance(val, (np.integer, np.floating)):
                val = val.item()
            if isinstance(val, float) and np.isnan(val):
                # Sin base de comparación: infinito matemático
                is_pct_col = any(x in str(col_name).upper() for x in ['%', 'VARIACION', 'VAR'])
                return '∞' if is_pct_col else ''
        except Exception:
            return ''

        is_pct = any(x in str(col_name).upper() for x in ['%', 'VARIACION', 'VAR'])

        if is_pct:
            val_num = float(val)
            # Normalización: si viene como entero (ej. -46.72) lo convertimos a decimal
            val_norm = val_num / 100 if abs(val_num) > 2.1 else val_num
            val_show = val_norm * 100
            txt = f"{val_show:,.2f}%".replace(',', 'X').replace('.', ',').replace('X', '.')
            if colorize:
                col = _P['SUCCESS'] if val_norm > 0 else _P['CRITICAL']
                return f"<b><font color='{col}'>{txt}</font></b>"
            return txt

        if isinstance(val, (int, float)):
            return f"{val:,.0f}".replace(',', '.')
        return str(val)

    @staticmethod
    def _sub_var(grp, _col, df_cols):
        """Calcula variación % para subtotales. Devuelve nan cuando base=0 y real>0 → ∞."""
        c_r = next((c for c in df_cols if '26' in str(c).upper() and 'CANT' not in str(c).upper()), None)
        c_o = next((c for c in df_cols if 'OBJ' in str(c).upper() and 'CANT' not in str(c).upper()), None)
        if c_r and c_o:
            obj_sum  = grp[c_o].sum()
            real_sum = grp[c_r].sum()
            if obj_sum > 0:
                return (real_sum - obj_sum) / obj_sum
            if real_sum > 0:
                return float('nan')  # → _fmt lo convierte a ∞
        return 0.0

    @staticmethod
    def generate_pdf(title, df_input, group_cols=None, meta_info=None, show_total=True, mode="gerencial"):

        df = df_input.copy()
        info = meta_info or {}
        obj_puro = info.get('objetivo_puro', 0.20)

        # ── Filtrar columnas técnicas (_path, _st_, etc.) ─────────────────────
        cols_ok = [
            c for c in df.columns
            if not str(c).startswith('_')
            and not str(c).startswith(':')
            and 'AUTO_UNIQUE_ID' not in str(c).upper()
            and c not in ['IS_SUBTOTAL', 'LEVEL']
        ]
        df = df[cols_ok]
        group_cols = [c for c in (group_cols or []) if c in df.columns]

        # ── Documento ─────────────────────────────────────────────────────────
        buffer = BytesIO()
        _page   = A4 if mode == "listado" else landscape(A4)
        _margin = 0.4 * inch
        doc = SimpleDocTemplate(
            buffer, pagesize=_page,
            leftMargin=_margin, rightMargin=_margin,
            topMargin=_margin, bottomMargin=0.35 * inch
        )
        _usable_w = _page[0] - 2 * _margin
        elements = []

        # ── CABECERA EJECUTIVA ────────────────────────────────────────────────
        st_brand = ParagraphStyle('BR', fontSize=7.5, textColor=_c(_P['MUTED']),
                                  fontName='Helvetica')
        st_title = ParagraphStyle('TI', fontSize=12, textColor=_c(_P['NAVY']),
                                  fontName='Helvetica-Bold', alignment=1, leading=15)
        st_meta  = ParagraphStyle('ME', fontSize=6, textColor=_c(_P['MUTED']),
                                  leading=9, alignment=1)
        st_date  = ParagraphStyle('DA', fontSize=6, textColor=_c(_P['MUTED']),
                                  alignment=2, fontName='Helvetica')

        if mode == "listado":
            # Listado informativo: subtítulo contextual, sin campos de sales report
            meta_line = info.get("subtitulo", "")
        else:
            # Reporte gerencial: metadatos de análisis comercial
            meta_line = (
                f"<b>Objetivo:</b> {info.get('porcentaje', 'N/A')}  ·  "
                f"<b>Departamento:</b> {info.get('depto', 'TODOS')}  ·  "
                f"<b>Categoría:</b> {info.get('cat', 'TODAS')}  ·  "
                f"<b>Período:</b> {info.get('periodo', 'N/A')}"
            )

        head_tbl = Table([[
            Paragraph(
                f"<b>{settings.COMPANY_NAME}</b>"
                f"<font color='{_P['MUTED']}'> · {settings.SYSTEM_NAME}</font>",
                st_brand
            ),
            [
                Paragraph(title.upper(), st_title),
                Spacer(1, 3),
                Paragraph(meta_line, st_meta),
            ],
            Paragraph(datetime.now().strftime('%d/%m/%Y  %H:%M'), st_date),
        ]], colWidths=[2.1 * inch, 6.7 * inch, 2.1 * inch])
        elements.append(head_tbl)
        elements.append(
            HRFlowable(width='100%', thickness=1.5, color=_c(_P['NAVY']),
                       spaceBefore=5, spaceAfter=7)
        )

        # ── ESTILOS DE TABLA ──────────────────────────────────────────────────
        fs   = 8.0 if mode == "listado" else 5.8
        ld   = fs + 2.2
        bf   = {'fontSize': fs, 'leading': ld}

        st_h   = ParagraphStyle('TH', fontSize=fs, leading=ld, textColor=colors.white,
                                alignment=1, fontName='Helvetica-Bold')
        st_num = ParagraphStyle('TN', **bf, alignment=2, textColor=_c(_P['SLATE']))
        st_txt = ParagraphStyle('TT', **bf, alignment=0, textColor=_c(_P['SLATE']))

        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        data_rows = []

        # Un único encabezado al inicio
        header_cells = [Paragraph(str(c).upper(), st_h) for c in df.columns]
        data_rows.append(header_cells + ['HEADER', {}])

        # ── PROCESO JERÁRQUICO ────────────────────────────────────────────────
        hv = {col: None for col in group_cols}

        def process_data(c_df, groups, level=0):
            nonlocal hv
            is_last_grp = (level == len(groups) - 1)

            if level >= len(groups):
                # Filas hoja
                for _, row in c_df.iterrows():
                    f_row = []
                    for c in df.columns:
                        repeated = c in groups and row[c] == hv.get(c)
                        txt = '' if repeated else ReportEngine._fmt(
                            row[c], c, obj_puro, colorize=True
                        )
                        if c in groups:
                            hv[c] = row[c]
                        f_row.append(Paragraph(txt, st_num if c in num_cols else st_txt))
                    data_rows.append(f_row + ['DATA', {'level': level}])
                return

            g_col = groups[level]
            for name in c_df[g_col].unique():
                grp = c_df[c_df[g_col] == name]
                process_data(grp, groups, level + 1)

                # Omitir subtotal del último nivel (siempre idéntico al dato hoja)
                if is_last_grp:
                    continue

                # Construir fila subtotal
                sc = df.columns.get_loc(g_col)
                # Fuente y color de texto según nivel (blanco sobre fondos oscuros)
                lbl_bold  = 'Helvetica-Bold'
                lbl_color = _P.get(f'TXT_L{level}', _P['SLATE'])

                st_lbl = ParagraphStyle(
                    f'SL{level}', **bf,
                    fontName=lbl_bold, textColor=_c(lbl_color)
                )
                st_snm = ParagraphStyle(
                    f'SN{level}', **bf,
                    alignment=2, fontName=lbl_bold, textColor=_c(lbl_color)
                )

                sub = []
                indent = '    ' * level
                for i, col in enumerate(df.columns):
                    if i < sc:
                        sub.append(Paragraph('', st_txt))
                    elif col == g_col:
                        sub.append(Paragraph(f"{indent}Σ  {str(name)}", st_lbl))
                    elif col in num_cols:
                        is_pct = any(x in str(col).upper() for x in ['%', 'VAR', 'VARIACION'])
                        if is_pct:
                            v = ReportEngine._sub_var(grp, col, df.columns)
                        else:
                            v = grp[col].sum()
                        # En fondos oscuros (L0, L1) no colorizar: texto blanco ya es legible.
                        # En fondos claros (L2+) colorizar normalmente.
                        colorize_sub = is_pct and level >= 2
                        sub.append(Paragraph(
                            ReportEngine._fmt(v, col, obj_puro, colorize=colorize_sub), st_snm
                        ))
                    else:
                        sub.append(Paragraph('', st_txt))

                data_rows.append(sub + [f'SUB_{level}', {'level': level, 'start_col': sc}])

        if mode == "listado":
            # MODO LISTADO: cada fila muestra TODOS los valores — sin ocultar repetidos,
            # sin subtotales. Pensado para listas de precios, catálogos, nóminas.
            for _, row in df.iterrows():
                f_row = [
                    Paragraph(
                        ReportEngine._fmt(row[c], c, obj_puro),
                        st_num if c in num_cols else st_txt
                    )
                    for c in df.columns
                ]
                data_rows.append(f_row + ['DATA', {'level': 0}])
        elif group_cols:
            process_data(df, group_cols)
        else:
            for _, row in df.iterrows():
                f_row = [
                    Paragraph(
                        ReportEngine._fmt(row[c], c, obj_puro, colorize=True),
                        st_num if c in num_cols else st_txt
                    )
                    for c in df.columns
                ]
                data_rows.append(f_row + ['DATA', {'level': 0}])

        # ── FILA TOTAL GENERAL (solo en modo gerencial) ───────────────────────
        if show_total and mode != "listado":
            st_tot_lbl = ParagraphStyle(
                'TOT_LBL', **bf,
                fontName='Helvetica-Bold', textColor=colors.white
            )
            st_tot_num = ParagraphStyle(
                'TOT_NUM', **bf,
                alignment=2, fontName='Helvetica-Bold', textColor=colors.white
            )
            tot_row = []
            first_text_done = False
            for i, col in enumerate(df.columns):
                if col in num_cols:
                    is_pct = any(x in str(col).upper() for x in ['%', 'VAR', 'VARIACION'])
                    if is_pct:
                        v = ReportEngine._sub_var(df, col, df.columns)
                    else:
                        v = df[col].sum()
                    tot_row.append(Paragraph(
                        ReportEngine._fmt(v, col, obj_puro, colorize=False),
                        st_tot_num
                    ))
                elif not first_text_done:
                    tot_row.append(Paragraph('TOTAL GENERAL', st_tot_lbl))
                    first_text_done = True
                else:
                    tot_row.append(Paragraph('', st_tot_lbl))
            data_rows.append(tot_row + ['TOTAL', {}])

        # ── ANCHOS DE COLUMNA ─────────────────────────────────────────────────
        if mode == "listado":
            # Auto-fit: proporcional al contenido, con techo de 22 chars
            # para que la descripción no engulla todo el ancho disponible.
            char_w = []
            for c in df.columns:
                header_len = len(str(c))
                data_max = df[c].apply(
                    lambda v: len(ReportEngine._fmt(v, c, obj_puro))
                    if pd.notna(v) and str(v) not in ('', 'nan') else 0
                ).max()
                raw = max(header_len, int(data_max), 3)
                char_w.append(min(raw, 22))  # techo: textos largos harán wrap
            col_widths = [(w / sum(char_w)) * _usable_w for w in char_w]
        else:
            weights = []
            for c in df.columns:
                cu = str(c).upper()
                if any(x in cu for x in ['CLIENTE']):
                    weights.append(3.2)
                elif any(x in cu for x in ['CADENA', 'VENDEDOR']):
                    weights.append(2.5)
                elif any(x in cu for x in ['MARCA']):
                    weights.append(1.8)
                elif any(x in cu for x in ['DESC']):
                    weights.append(3.0)
                elif 'MES' in cu:
                    weights.append(1.1)
                elif any(x in cu for x in ['LPN', 'LPC0', 'LPC ']):
                    weights.append(0.9)
                elif any(x in cu for x in ['LÍNEA', 'LINEA']):
                    weights.append(0.65)
                elif cu in ('REF.', 'REF'):
                    weights.append(0.35)
                elif 'REF' in cu:
                    weights.append(0.8)
                else:
                    weights.append(1.0)
            col_widths = [(w / sum(weights)) * _usable_w for w in weights]

        t = Table(
            [r[:-2] for r in data_rows],
            colWidths=col_widths,
            hAlign='CENTER',
            repeatRows=1
        )

        # ── ESTILOS DE TABLA ──────────────────────────────────────────────────
        style = [
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('TOPPADDING',    (0, 0), (-1, -1), 2.5),
            # Base blanca explícita para toda la tabla (garantía de precedencia)
            ('BACKGROUND',    (0, 0), (-1, -1), colors.white),
            # Líneas horizontales suaves para todas las filas
            ('LINEBELOW', (0, 0), (-1, -1), 0.25, _c(_P['BORDER_LT'])),
        ]

        if mode == "listado":
            style += [
                ('INNERGRID', (0, 0), (-1, -1), 0.3, _c('#BFBFBF')),  # gris Excel thin
                ('BOX',       (0, 0), (-1, -1), 0.5, _c('#ADADAD')),  # gris Excel borde ext.
            ]

        sub_bgs = {
            0: _P['BG_L0'],
            1: _P['BG_L1'],
            2: _P['BG_L2'],
            3: _P['BG_L3'],
        }
        sub_lines = {
            0: (1.5,  _P['GOLD']),    # Vendedor → línea gold como el header
            1: (1.0,  _P['NAVY_MID']),   # Cadena
            2: (0.5,  _P['NAVY_MID']),   # Cliente
            3: (0.5,  _P['BORDER']),     # Marca
        }

        nc = len(df.columns)

        for ridx, full_row in enumerate(data_rows):
            rtype = str(full_row[-2])
            meta  = full_row[-1]

            if rtype == 'HEADER':
                style.append(('BACKGROUND', (0, ridx), (nc - 1, ridx), _c(_P['NAVY'])))
                style.append(('LINEBELOW',  (0, ridx), (nc - 1, ridx), 2.0, _c(_P['GOLD'])))

            elif 'SUB' in rtype:
                lvl = meta.get('level', 0)
                sc  = meta.get('start_col', 0)
                bg  = sub_bgs.get(lvl, _P['WHITE'])
                lw, lc = sub_lines.get(lvl, (0.25, _P['BORDER_LT']))
                # Columnas izquierdas: blanco explícito celda a celda (sin rangos negativos)
                for ci in range(sc):
                    style.append(('BACKGROUND', (ci, ridx), (ci, ridx), colors.white))
                # Columnas desde el grupo hacia la derecha: color (sin índices negativos)
                style.append(('BACKGROUND', (sc, ridx), (nc - 1, ridx), _c(bg)))
                style.append(('LINEBELOW',  (sc, ridx), (nc - 1, ridx), lw, _c(lc)))
                if lvl == 0:
                    style.append(('LINEABOVE', (sc, ridx), (nc - 1, ridx), 0.5, _c(_P['BORDER'])))

            elif rtype == 'TOTAL':
                style.append(('BACKGROUND', (0, ridx), (nc - 1, ridx), _c(_P['NAVY'])))
                style.append(('LINEABOVE',  (0, ridx), (nc - 1, ridx), 2.0, _c(_P['GOLD'])))
                style.append(('LINEBELOW',  (0, ridx), (nc - 1, ridx), 1.5, _c(_P['GOLD'])))

            elif rtype == 'DATA':
                if ridx % 2 == 0:
                    style.append(('BACKGROUND', (0, ridx), (nc - 1, ridx), _c(_P['BG_ALT'])))

        t.setStyle(TableStyle(style))
        elements.append(t)
        doc.build(elements)
        buffer.seek(0)
        return buffer

# [EXECUTION-CONFIRMED] v101.0.0 - Executive Minimal IMF Style
