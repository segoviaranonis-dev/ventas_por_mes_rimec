"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
MODULO: core/report_engine.py
VERSION: 94.7.5 (METADATA & PRECISION SEMAPHORE)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Motor PDF con Piano de Colores y Semáforo de Precisión.
              Interpretación de metadatos desde FilterManager y 
              saneamiento de visualización jerárquica.
"""

import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, HRFlowable, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from core.settings import settings

class ReportEngine:
    @staticmethod
    def _hex(color_str, fallback):
        try: return colors.HexColor(color_str)
        except: return colors.HexColor(fallback)

    @classmethod
    def get_colors(cls):
        return {
            'HEADER_BG': cls._hex(getattr(settings, 'PDF_PRIMARY', '#0055A4'), "#0055A4"),
            'PRIMARY': cls._hex(getattr(settings, 'UI_PRIMARY', '#D4AF37'), "#D4AF37"),
            'SUCCESS': cls._hex(getattr(settings, 'PDF_VAR_POS', '#059669'), "#059669"),
            'CRITICAL': cls._hex(getattr(settings, 'PDF_VAR_NEG', '#DC2626'), "#DC2626"),
            'TEXT': colors.HexColor("#334155"),
            'MONEY': colors.HexColor("#1E293B"),
            'META_LABEL': colors.HexColor("#475569")
        }

    @staticmethod
    def _format_value(val, col_name="", paleta=None, objetivo_puro=0.2):
        """
        Formateador con semáforo inteligente.
        objetivo_puro: El valor decimal (0.2 para 20%) contra el cual comparar.
        """
        if val is None or (isinstance(val, (float, int)) and np.isnan(val)): return ""
        is_pct = any(x in str(col_name).upper() for x in ['%', 'VARIACION', 'VAR'])
        
        if isinstance(val, (np.integer, np.floating)): val = val.item()
        
        if is_pct:
            val_num = float(val)
            # Normalización Nexus: Tratamos tanto decimales como porcentajes enteros
            val_norm = val_num / 100 if abs(val_num) > 2.1 else val_num
            
            val_show = val_norm * 100
            txt = f"{val_show:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
            
            if paleta:
                # El semáforo decide: VERDE si supera el objetivo inyectado, ROJO si no.
                color = paleta['SUCCESS'].hexval() if val_norm >= objetivo_puro else paleta['CRITICAL'].hexval()
                return f"<b><font color='{color}'>{txt}</font></b>"
            return txt
            
        if isinstance(val, (int, float)): 
            return f"{val:,.0f}".replace(",", ".")
        return str(val)

    @staticmethod
    def generate_pdf(title, df_input, group_cols=None, meta_info=None):
        paleta = ReportEngine.get_colors()
        df = df_input.copy()
        
        # Extracción de parámetros de control desde meta_info (generado por FilterManager)
        info = meta_info or {}
        obj_referencia = info.get('objetivo_puro', 0.20) 

        # Limpieza técnica de columnas Nexus
        cols_to_keep = [c for c in df.columns if not str(c).startswith(':') and 'AUTO_UNIQUE_ID' not in str(c).upper() and c not in ['IS_SUBTOTAL', 'LEVEL']]
        df = df[cols_to_keep]
        group_cols = group_cols if isinstance(group_cols, list) else ([group_cols] if group_cols else [])

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                leftMargin=0.25*inch, rightMargin=0.25*inch,
                                topMargin=0.3*inch, bottomMargin=0.3*inch)
        elements = []

        # --- CABECERA DINÁMICA CON CAPTURA DE METADATA ---
        linea_meta = (
            f"<b>OBJETIVO:</b> {info.get('porcentaje', 'N/A')}  |  "
            f"<b>DEPTO:</b> {info.get('depto', 'TODOS')}  |  "
            f"<b>CATEGORÍA:</b> {info.get('cat', 'TODAS')}  |  "
            f"<b>PERIODO:</b> {info.get('periodo', 'N/A')}"
        )

        st_meta = ParagraphStyle('Meta', fontSize=6.5, leading=8, textColor=paleta['META_LABEL'], alignment=1)
        
        head_data = [[
            Paragraph(f"<b>{settings.COMPANY_NAME}</b> | <font color='{paleta['PRIMARY'].hexval()}'>{settings.SYSTEM_NAME}</font>", getSampleStyleSheet()['Normal']),
            [
                Paragraph(f"<b>{title.upper()}</b>", ParagraphStyle('T', fontSize=11, alignment=1, textColor=paleta['HEADER_BG'])),
                Paragraph(linea_meta, st_meta)
            ],
            Paragraph(f"{datetime.now().strftime('%d/%m/%Y %H:%M')}", ParagraphStyle('M', fontSize=5, alignment=2, textColor=colors.grey))
        ]]
        
        elements.append(Table(head_data, colWidths=[2.8*inch, 5.8*inch, 2.8*inch]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=paleta['PRIMARY'], spaceAfter=6))

        # --- ESTILOS DE CELDA ---
        f_size = 6.2 if len(df.columns) <= 10 else 5.2
        leading = f_size + 1.2
        base_f = {'fontSize': f_size, 'leading': leading}
        
        st_left = ParagraphStyle('L', **base_f, alignment=0, textColor=paleta['TEXT'])
        st_right = ParagraphStyle('R', **base_f, alignment=2, textColor=paleta['MONEY'])
        st_h = ParagraphStyle('H', fontSize=f_size, leading=leading, textColor=colors.white, alignment=1, fontName='Helvetica-Bold')

        num_cols_names = df.select_dtypes(include=[np.number]).columns.tolist()
        data_rows = []
        hierarchical_last_val = {col: None for col in group_cols}
        header_row_content = [Paragraph(str(c).upper(), st_h) for c in df.columns]

        def process_data(c_df, groups, level=0):
            nonlocal hierarchical_last_val
            if level >= len(groups):
                for _, row in c_df.iterrows():
                    f_row = []
                    for c in df.columns:
                        is_repeated = (c in groups and row[c] == hierarchical_last_val.get(c))
                        # Inyección del objetivo_puro al formateador para el semáforo
                        formatted = "" if is_repeated else ReportEngine._format_value(row[c], c, paleta, obj_referencia)
                        if c in groups: hierarchical_last_val[c] = row[c]
                        
                        style_choice = st_right if c in num_cols_names else st_left
                        f_row.append(Paragraph(formatted, style_choice))
                    data_rows.append(f_row + ['DATA', {}])
                return

            g_col = groups[level]
            for name in c_df[g_col].unique():
                if level == 0:
                    data_rows.append(header_row_content + ['HEADER_TAB', {}])
                    for k in groups: hierarchical_last_val[k] = None
                
                group = c_df[c_df[g_col] == name]
                process_data(group, groups, level + 1)

                sub_row = []
                start_idx = df.columns.get_loc(g_col)
                for i, col in enumerate(df.columns):
                    if i < start_idx: sub_row.append("")
                    elif col == g_col:
                        sub_row.append(Paragraph(f"Σ {str(name).upper()}", ParagraphStyle('S', **base_f, fontName='Helvetica-Bold')))
                    elif col in num_cols_names:
                        if any(x in str(col).upper() for x in ['%', 'VAR']):
                            c_r = next((c for c in df.columns if '26' in str(c).upper() and ('MONT' in str(c).upper() or 'CANT' not in str(c).upper())), None)
                            c_o = next((c for c in df.columns if 'OBJ' in str(c).upper() and ('MONT' in str(c).upper() or 'CANT' not in str(c).upper())), None)
                            val = ((group[c_r].sum() - group[c_o].sum()) / group[c_o].sum()) if c_r and c_o and group[c_o].sum() > 0 else 0.0
                        else: val = group[col].sum()
                        # Formateo de subtotales aplicando el semáforo de precisión
                        sub_row.append(Paragraph(ReportEngine._format_value(val, col, paleta, obj_referencia), st_right))
                    else: sub_row.append("")
                
                data_rows.append(sub_row + [f'SUB_{level}', {'level': level, 'start_col': start_idx}])

        if group_cols: process_data(df, group_cols)
        else: # Si no hay grupos, renderizado plano
            data_rows.append(header_row_content + ['HEADER_TAB', {}])
            for _, row in df.iterrows():
                f_row = [Paragraph(ReportEngine._format_value(row[c], c, paleta, obj_referencia), st_right if c in num_cols_names else st_left) for c in df.columns]
                data_rows.append(f_row + ['DATA', {}])
        
        usable_w = 11.3 * inch
        weights = [2.5 if any(x in str(c).upper() for x in ['CLIENTE', 'CADENA', 'VENDEDOR']) else 1.0 for c in df.columns]
        col_widths = [(w/sum(weights))*usable_w for w in weights]
        
        t = Table([r[:-2] for r in data_rows], colWidths=col_widths, hAlign='CENTER')
        
        style = [
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ]

        for ridx, full_row in enumerate(data_rows):
            rtype = str(full_row[-2])
            meta = full_row[-1]

            if rtype == 'HEADER_TAB':
                style.append(('BACKGROUND', (0, ridx), (-1, ridx), paleta['HEADER_BG']))
                continue

            if 'SUB' in rtype:
                lvl = meta.get('level', 0)
                sc = meta.get('start_col', 0)
                piano = settings.PIANO_PDF_MAP.get(lvl, {'bg': '#F1F5F9', 'text': '#000000'})
                style.append(('BACKGROUND', (sc, ridx), (-1, ridx), colors.HexColor(piano.get('bg'))))
                if piano.get('text'):
                    style.append(('TEXTCOLOR', (sc, ridx), (sc, ridx), colors.HexColor(piano.get('text'))))

        t.setStyle(TableStyle(style))
        elements.append(t)
        doc.build(elements)
        buffer.seek(0)
        return buffer