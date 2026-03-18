"""
SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
UBICACIÓN: modules/sales_report/logic.py
VERSION: 85.0.0 (PLAN 1: PROTOCOLO IDENTIDAD ÚNICA - NIVEL PIEDRA)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Motor con unificación de ADN. Forzamos etiquetas de 'Vendedor' y 'Cadena/Cliente'
              en todas las capas para que la UI proyecte sin redundancias.
"""

import pandas as pd
import numpy as np
import time
from core.settings import settings
from core.database import DBInspector

def _safe_variacion(real_series, obj_series):
    """
    Cálculo RIMEC 3.0: (Real - Objetivo) / Objetivo * 100.
    FACTOR 100X: Devuelve el número listo para ser mostrado como % sin que la UI calcule.
    """
    real = pd.to_numeric(pd.Series(real_series), errors='coerce').fillna(0).values
    obj = pd.to_numeric(pd.Series(obj_series), errors='coerce').fillna(0).values

    with np.errstate(divide='ignore', invalid='ignore'):
        # Lógica binaria para casos límite
        res = np.where((obj == 0) & (real > 0), 1.0,
              np.where((obj > 0) & (real == 0), -1.0,
              np.where(obj > 0, (real - obj) / obj, 0.0)))

    return np.round(res * 100, 2)

class SalesLogic:
    """
    Motor v85.0.0: El Dictador de Identidad.
    Asegura que la UI reciba nombres de columnas consistentes (Protocolo Picapiedra).
    """

    MESES_ORDEN = {
        "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
        "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
        "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
    }

    @staticmethod
    def _ui_mic(msg, level="INFO"):
        log_msg = f"🧠 [LOGIC-CORE] {msg}"
        DBInspector.log(log_msg, level)
        print(log_msg)

    @staticmethod
    def _sanitize_and_align(df, label_for_mic="Table"):
        """
        🛡️ BLINDAJE PLAN 1:
        1. Rescate de Identidad: Mueve índices a columnas.
        2. Force String: Sanitización de ADN contra 'nan'.
        3. Footer Blindado: Inyección de totales calculados.
        """
        if df is None or df.empty:
            return {'data': pd.DataFrame(), 'totals': {}}

        df = df.copy()

        # 1. RESCATE DE IDENTIDAD
        if df.index.name:
            df = df.reset_index()

        # 2. LIMPIEZA DE COLUMNAS
        df.columns = [str(c).strip() for c in df.columns]

        # 3. FORCE STRING EN ADN
        text_cols = df.select_dtypes(exclude=[np.number]).columns
        for col in text_cols:
            df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', 'NoneType', ''], '---')

        # 4. BLINDAJE NUMÉRICO
        num_cols = df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        # 5. CÁLCULO DE TOTALES
        totals = {}
        for col in df.columns:
            if col in num_cols:
                if any(x in col.upper() for x in ['%', 'VAR']):
                    # Buscar columnas de referencia para variación global
                    m_obj_col = next((c for c in df.columns if any(x in c.upper() for x in ['OBJ MONTO', 'MONTO OBJ'])), None)
                    m_real_col = next((c for c in df.columns if any(x in c.upper() for x in ['MONT 26', 'MONTO 26'])), None)

                    if m_obj_col and m_real_col:
                        sum_obj = df[m_obj_col].sum()
                        sum_real = df[m_real_col].sum()
                        totals[col] = float(_safe_variacion([sum_real], [sum_obj])[0])
                    else:
                        totals[col] = 0.0
                else:
                    totals[col] = float(df[col].sum())
            else:
                totals[col] = ""

        if len(text_cols) > 0:
            totals[text_cols[0]] = "TOTAL GENERAL"

        # MICRÓFONO: Audita si las columnas son las esperadas
        SalesLogic._ui_mic(f"Integridad {label_for_mic} | Columnas: {list(df.columns)}")

        return {'data': df, 'totals': totals}

    @staticmethod
    def get_full_analysis_package(df, objetivo_pct, meses_filtro):
        """🚀 ORQUESTRADOR MAESTRO: Genera el paquete de Súper Objetos blindados."""
        t_init = time.time()

        df_base = SalesLogic._align_temporal_data(df, meses_filtro)
        if df_base.empty:
            SalesLogic._ui_mic("Aduana: DataFrame vacío tras filtrar.", "WARNING")
            return None

        # Pivot Maestro con Identificadores Planos
        df_master = df_base.groupby(
            ['vendedor', 'Identificador', 'cliente', 'marca', 'mes_nombre', 'mes_idx'],
            observed=True, as_index=False
        ).agg({
            'monto_obj': 'sum',
            'monto_26': 'sum',
            'cant_obj': 'sum',
            'cant_26': 'sum'
        })

        pkg = {
            'evolucion': SalesLogic.process_comparison_matrix(df_master),
            'cartera': SalesLogic.process_customer_opportunity(df_master),
            'marcas': SalesLogic.process_brand_drilldown(df_master),
            'vendedores': SalesLogic.process_seller_drilldown(df_master),
            'kpis': SalesLogic.get_kpis_fixed(df_master)
        }

        v_total = _safe_variacion([df_master['monto_26'].sum()], [df_master['monto_obj'].sum()])[0]
        pkg['kpis']['variacion_total'] = float(v_total)

        SalesLogic._ui_mic(f"Análisis v85 (Protocolo Único) completado en {time.time() - t_init:.4f}s")
        return pkg

    @staticmethod
    def _align_temporal_data(df, meses_filtro):
        df = df.copy()
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['mes_idx'] = df['fecha'].dt.month
            inv_meses = {v: k for k, v in SalesLogic.MESES_ORDEN.items()}
            df['mes_nombre'] = df['mes_idx'].map(inv_meses)
            if meses_filtro:
                df = df[df['mes_nombre'].isin(meses_filtro)]
        return df

    @staticmethod
    def process_customer_opportunity(df_m):
        """Unifica etiquetas para evitar redundancias en la UI."""
        cartera = df_m.groupby(['vendedor', 'Identificador', 'cliente'], as_index=False).agg({
            'monto_obj': 'sum', 'monto_26': 'sum'
        })
        cartera['Variación %'] = _safe_variacion(cartera['monto_26'], cartera['monto_obj'])
        # Protocolo Picapiedra: 'Vendedor' -> 'Cadena' -> 'Cliente'
        cartera.columns = ['Vendedor', 'Cadena', 'Cliente', 'Monto Obj', 'Monto 26', 'Variación %']

        c_full_data = SalesLogic._sanitize_and_align(cartera, "Cartera Base")['data']

        return {
            'crecimiento': SalesLogic._sanitize_and_align(c_full_data[c_full_data['Monto 26'] > c_full_data['Monto Obj']], "Cli Crecimiento"),
            'decrecimiento': SalesLogic._sanitize_and_align(c_full_data[(c_full_data['Monto 26'] <= c_full_data['Monto Obj']) & (c_full_data['Monto 26'] > 0)], "Cli Decrecimiento"),
            'sin_compra': SalesLogic._sanitize_and_align(c_full_data[c_full_data['Monto 26'] <= 0], "Cli Sin Compra")
        }

    @staticmethod
    def process_brand_drilldown(df_m):
        rank = df_m.groupby('marca', as_index=False).agg({'monto_obj': 'sum', 'monto_26': 'sum'})
        rank['Variación %'] = _safe_variacion(rank['monto_26'], rank['monto_obj'])
        rank.columns = ['Marca', 'Monto Obj', 'Monto 26', 'Variación %']

        det = df_m.groupby(['marca', 'Identificador', 'cliente', 'vendedor'], as_index=False).agg({'monto_obj': 'sum', 'monto_26': 'sum'})
        det.columns = ['Marca', 'Cadena', 'Cliente', 'Vendedor', 'Obj Monto', 'Mont 26']
        det['Var % Monto'] = _safe_variacion(det['Mont 26'], det['Obj Monto'])

        return (
            SalesLogic._sanitize_and_align(rank.sort_values('Monto 26', ascending=False), "Marcas Rank"),
            SalesLogic._sanitize_and_align(det, "Marcas Detalle")
        )

    @staticmethod
    def process_seller_drilldown(df_m):
        rank = df_m.groupby('vendedor', as_index=False).agg({'monto_obj': 'sum', 'monto_26': 'sum'})
        rank['Variación %'] = _safe_variacion(rank['monto_26'], rank['monto_obj'])
        rank.columns = ['Vendedor', 'Monto Obj', 'Monto 26', 'Variación %']

        det = df_m.copy()[['vendedor', 'Identificador', 'cliente', 'marca', 'mes_nombre', 'cant_obj', 'cant_26', 'monto_obj', 'monto_26']]
        # Mantenemos consistencia con la jerarquía: Vendedor -> Cadena -> Cliente -> Marca
        det.columns = ['Vendedor', 'Cadena', 'Cliente', 'Marca', 'Mes', 'Obj Cant', 'Cant 26', 'Obj Monto', 'Mont 26']
        det['Var % Cant'] = _safe_variacion(det['Cant 26'], det['Obj Cant'])
        det['Var % Monto'] = _safe_variacion(det['Mont 26'], det['Obj Monto'])

        return (
            SalesLogic._sanitize_and_align(rank.sort_values('Monto 26', ascending=False), "Vendedores Rank"),
            SalesLogic._sanitize_and_align(det, "Vendedores Detalle")
        )

    @staticmethod
    def process_comparison_matrix(df_m):
        df_m = df_m.copy()
        df_m['Semestre'] = np.where(df_m['mes_idx'] <= 6, "1er SEMESTRE", "2do SEMESTRE")

        res = df_m.groupby(['Semestre', 'mes_idx', 'mes_nombre'], as_index=False).agg({
            'monto_obj': 'sum', 'monto_26': 'sum'
        }).sort_values('mes_idx')

        res['Variación %'] = _safe_variacion(res['monto_26'], res['monto_obj'])

        final = res[['Semestre', 'mes_nombre', 'monto_obj', 'monto_26', 'Variación %']].rename(
            columns={'mes_nombre': 'Mes', 'monto_obj': 'Monto Obj', 'monto_26': 'Monto 26'}
        )
        return SalesLogic._sanitize_and_align(final, "Evolución Mensual")

    @staticmethod
    def get_kpis_fixed(df_m):
        cl_26 = df_m[df_m['monto_26'] > 0]['cliente'].nunique()
        total_cl = df_m['cliente'].nunique()
        return {
            'clientes_26': int(cl_26),
            'total_cl': int(total_cl),
            'atendimiento': float((cl_26 / total_cl * 100) if total_cl > 0 else 0.0)
        }