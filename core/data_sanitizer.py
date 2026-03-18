"""
SISTEMA: CHUNACHUNA IMPORT Business Intelligence - NEXUS CORE
UBICACIÓN: core/data_sanitizer.py
VERSION: 70.4.2 (OBSIDIAN ADUANA MASTER)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Aduana de Datos Universal.
             Sincroniza el blindaje de IDs con la Geometría Piano de SalesLogic.
"""

import pandas as pd
import numpy as np
import time
import sys
import re
from core.settings import settings

class DataSanitizer:
    """
    Protocolo de Aduana NEXUS CORE: El único punto de entrada para datos crudos.
    Misión: Blindar IDs, normalizar textos y asegurar tipos de datos para AgGrid.
    """

    @staticmethod
    def _log_aduana(msg, level="INFO"):
        """Monitor de flujo de datos con identidad de marca."""
        levels = {
            "INFO": f"\033[94m🛂 {settings.LOG_PREFIX}-INFO\033[0m",
            "ERROR": f"\033[91m🚨 {settings.LOG_PREFIX}-CRITICO\033[0m",
            "WARN": f"\033[93m⚠️ {settings.LOG_PREFIX}-ALERTA\033[0m",
            "DEBUG": f"\033[95m🔍 {settings.LOG_PREFIX}-DEBUG\033[0m"
        }
        timestamp = time.strftime("%H:%M:%S")
        print(f"{levels.get(level, '[ADUANA]')} [{timestamp}] {msg}", file=sys.stderr)

    @staticmethod
    def clean_sales_matrix(df):
        """
        🚀 MÉTODO CRUCIAL: Interfaz directa para SalesLogic.
        Asegura que las tablas procesadas por la Geometría Piano sean legibles por AgGrid.
        """
        if df is None or df.empty: return df

        # 1. Normalización de Cabeceras
        df.columns = [str(c).strip() for c in df.columns]

        # 2. Blindaje de Texto (Evita el brillo por ausencia en la UI)
        # Sincronizado con 'Doma de Letras'
        text_cols = df.select_dtypes(exclude=[np.number]).columns
        for col in text_cols:
            df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', 'nan', 'NULL'], '---')
            df[col] = df[col].str.upper()

        # 3. Blindaje Numérico Arrow-Safe (Crucial para AgGrid)
        num_cols = df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            if col == 'LEVEL':
                df[col] = df[col].fillna(2).astype(int)
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        return df

    @staticmethod
    def clean_data(df, module="sales"):
        """Punto de entrada universal para saneamiento de datos crudos (Raw Data)."""
        if df is None or df.empty:
            DataSanitizer._log_aduana("Intento de saneamiento en DataFrame nulo o vacío.", "ERROR")
            return pd.DataFrame()

        pd.set_option('future.no_silent_downcasting', True)
        t_start = time.time()
        df_clean = df.copy()

        # 1. TRADUCCIÓN DE NULOS VECTORIZADA
        null_variants = ['None', 'nan', 'NULL', 'null', 'NoneType', '', ' ', 'NaN', 'NAN', '<NA>']
        df_clean = df_clean.replace(null_variants, np.nan).infer_objects(copy=False)

        # 2. DERIVACIÓN POR PROTOCOLO
        if module == "sales":
            df_clean = DataSanitizer._protocol_sales(df_clean)

        duration = (time.time() - t_start) * 1000
        DataSanitizer._log_aduana(f"Protocolo '{module}' finalizado: {len(df_clean)} registros en {duration:.2f}ms")

        return df_clean

    @staticmethod
    def _protocol_sales(df):
        """Protocolo específico para Ventas v70: Control Total e IDs Inmunes."""

        # --- A. BLINDAJE DE IDENTIDADES (Smart Shield v70.2) ---
        id_patterns = [r'^id_', r'^codigo', r'identificador', r'sku']
        explicit_ids = ['id_tipo', 'id_marca', 'id_cliente', 'id_vendedor', 'id_categoria', 'codigo_cliente']

        for col in df.columns:
            str_col = str(col).lower().strip()
            is_id = any(re.search(pat, str_col) for pat in id_patterns) or col in explicit_ids

            if is_id:
                temp_series = df[col].astype(str).str.replace('.0', '', regex=False).replace(['nan', 'None', 'NULL'], '0')
                if temp_series.str.isdigit().all():
                    df[col] = pd.to_numeric(temp_series, errors='coerce').fillna(0).astype(np.int64).astype(str)
                else:
                    df[col] = temp_series.str.strip().str.upper()

                df[col] = df[col].replace(['0', 'NAN', 'NONE', '<NA>', ''], 'S/I')

        # --- B. DOMA DE LETRAS (Textos Limpios) ---
        text_cols = ['vendedor', 'marca', 'cliente', 'cadena', 'tipo', 'departamento', 'mes_nombre']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace(['nan', 'None', 'NoneType'], 'S/I').str.strip().str.upper()

        # --- C. PROTECCIÓN MATEMÁTICA ---
        numeric_cols = [
            'monto', 'cantidad', 'anio', 'mes_idx',
            'monto_25', 'cant_25', 'monto_obj', 'cant_obj', 'monto_26', 'cant_26',
            'Variación %', 'Var % Cant', 'Var % Monto'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- D. REGLA DE NEGOCIO: IDENTIFICADOR CHUNACHUNA ---
        if 'cadena' in df.columns and 'cliente' in df.columns:
            invalid_labels = ['-', 'S/C', 'NONE', 'NAN', 'N/A', '', 'NULL', 'S/I']
            df['Identificador'] = np.where(
                (df['cadena'].str.upper().isin(invalid_labels)),
                df['cliente'],
                df['cadena']
            )

        return df