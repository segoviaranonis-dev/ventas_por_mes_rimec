# =============================================================================
# SISTEMA: RIMEC Business Intelligence - NEXUS CORE
# UBICACIÓN: core/data_sanitizer.py
# VERSION: 2.0.0 (UNIVERSAL - PROTOCOLO DE ADUANA GENÉRICA)
# DESCRIPCIÓN: Aduana de Datos Universal.
#              v2.0.0: El core ya no conoce columnas de ningún módulo.
#              Cada módulo define sus propias reglas (SANITIZER_RULES) y
#              las pasa como argumento. Backward-compat con module="sales".
# =============================================================================

import pandas as pd
import numpy as np
import time
import sys
import re
from core.settings import settings


# ─────────────────────────────────────────────────────────────────────────────
# TIPO: Reglas de sanitización por módulo
# Cada módulo define un dict con esta estructura en su logic.py o constants.py
# ─────────────────────────────────────────────────────────────────────────────
# SANITIZER_RULES = {
#     "id_patterns":  [r'^id_', r'^codigo'],   # regex para detectar cols ID
#     "id_explicit":  ['codigo_cliente'],       # cols ID por nombre exacto
#     "text_cols":    ['vendedor', 'marca'],    # cols de texto a domar
#     "numeric_cols": ['monto', 'cantidad'],    # cols numéricas a proteger
#     "business_rule": callable | None,        # función(df) -> df opcional
# }


class DataSanitizer:
    """
    Aduana de Datos NEXUS CORE.
    Punto único de saneamiento. El core no conoce el negocio de ningún módulo.
    """

    # Variantes de nulo reconocidas por el sistema
    NULL_VARIANTS = ['None', 'nan', 'NULL', 'null', 'NoneType', '', ' ',
                     'NaN', 'NAN', '<NA>', 'nanType']

    @staticmethod
    def _log(msg, level="INFO"):
        levels = {
            "INFO":  f"\033[94m🛂 {settings.LOG_PREFIX}-INFO\033[0m",
            "ERROR": f"\033[91m🚨 {settings.LOG_PREFIX}-CRITICO\033[0m",
            "WARN":  f"\033[93m⚠️  {settings.LOG_PREFIX}-ALERTA\033[0m",
        }
        ts = time.strftime("%H:%M:%S")
        print(f"{levels.get(level, '[ADUANA]')} [{ts}] {msg}", file=sys.stderr)

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODO PRINCIPAL
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def clean_data(df: pd.DataFrame, rules: dict | None = None, module: str = "sales") -> pd.DataFrame:
        """
        Punto de entrada universal.

        Uso moderno (recomendado):
            DataSanitizer.clean_data(df, rules=MiModulo.SANITIZER_RULES)

        Uso heredado (backward-compat):
            DataSanitizer.clean_data(df)              # usa module="sales"
            DataSanitizer.clean_data(df, module="sales")
        """
        if df is None or df.empty:
            DataSanitizer._log("Intento de saneamiento en DataFrame nulo.", "ERROR")
            return pd.DataFrame()

        pd.set_option('future.no_silent_downcasting', True)
        t_start = time.time()
        df_clean = df.copy()

        # 1. Traducción de nulos vectorizada
        df_clean = df_clean.replace(DataSanitizer.NULL_VARIANTS, '---').infer_objects(copy=False)

        # 2. Protocolo genérico (rules dict) o legacy (module string)
        if rules is not None:
            df_clean = DataSanitizer._apply_rules(df_clean, rules)
        elif module == "sales":
            df_clean = DataSanitizer._protocol_sales_legacy(df_clean)

        duration = (time.time() - t_start) * 1000
        tag = f"rules={list(rules.keys())}" if rules else f"module={module}"
        DataSanitizer._log(f"Protocolo [{tag}] OK: {len(df_clean)} filas en {duration:.1f}ms")

        return df_clean

    # ─────────────────────────────────────────────────────────────────────────
    # PROTOCOLO GENÉRICO — nuevo camino para todos los módulos futuros
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _apply_rules(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
        """
        Aplica las reglas de sanitización definidas por el módulo.
        No contiene lógica de negocio propia.
        """
        # A. Blindaje de IDs
        id_patterns = rules.get("id_patterns", [])
        id_explicit = rules.get("id_explicit", [])

        for col in df.columns:
            str_col = str(col).lower().strip()
            is_id = (
                any(re.search(pat, str_col) for pat in id_patterns)
                or col in id_explicit
            )
            if not is_id:
                continue

            temp = df[col].astype(str).str.replace('.0', '', regex=False)
            temp = temp.replace(['nan', 'None', 'NULL', '---'], '0')
            if temp.str.isdigit().all():
                df[col] = pd.to_numeric(temp, errors='coerce').fillna(0).astype(np.int64).astype(str)
            else:
                df[col] = temp.str.strip().str.upper()
            df[col] = df[col].replace(['0', 'NAN', 'NONE', '<NA>', '', '---'], 'S/I')

        # B. Doma de textos
        for col in rules.get("text_cols", []):
            if col in df.columns:
                df[col] = (df[col].astype(str)
                           .replace(['nan', 'None', 'NoneType', '---'], 'S/I')
                           .str.strip().str.upper())

        # C. Protección numérica
        for col in rules.get("numeric_cols", []):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # D. Regla de negocio personalizada (hook opcional)
        business_rule = rules.get("business_rule")
        if callable(business_rule):
            df = business_rule(df)

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODO DE COMPATIBILIDAD — para AgGrid (no depende de módulo)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def clean_sales_matrix(df: pd.DataFrame) -> pd.DataFrame:
        """Prepara un DataFrame ya procesado para renderizar en AgGrid."""
        if df is None or df.empty:
            return df

        df.columns = [str(c).strip() for c in df.columns]

        text_cols = df.select_dtypes(exclude=[np.number]).columns
        for col in text_cols:
            df[col] = (df[col].astype(str).str.strip()
                       .replace(['nan', 'None', 'NULL', 'nanType', 'NaN', 'NAN',
                                 'NoneType', '<NA>', 'null', ''], '---')
                       .str.upper())

        num_cols = df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            if col == 'LEVEL':
                df[col] = df[col].fillna(2).astype(int)
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).astype(float)

        return df

    # ─────────────────────────────────────────────────────────────────────────
    # PROTOCOLO LEGACY — solo para el módulo de ventas hasta que migre a rules
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _protocol_sales_legacy(df: pd.DataFrame) -> pd.DataFrame:
        """
        Protocolo heredado de ventas.
        Pendiente de migrar: sales_report debe definir SANITIZER_RULES
        y llamar clean_data(df, rules=SANITIZER_RULES).
        """
        id_patterns  = [r'^id_', r'^codigo', r'identificador', r'sku']
        id_explicit  = ['id_tipo', 'id_marca', 'id_cliente', 'id_vendedor',
                        'id_categoria', 'codigo_cliente']
        text_cols    = ['vendedor', 'marca', 'cliente', 'cadena', 'tipo',
                        'departamento', 'mes_nombre']
        numeric_cols = ['monto', 'cantidad', 'anio', 'mes_idx',
                        'monto_25', 'cant_25', 'monto_obj', 'cant_obj',
                        'monto_26', 'cant_26', 'Variación %',
                        'Var % Cant', 'Var % Monto']

        def _identificador_rule(df):
            if 'cadena' in df.columns and 'cliente' in df.columns:
                invalid = ['-', 'S/C', 'NONE', 'NAN', 'N/A', '', 'NULL', 'S/I', '---']
                df['Identificador'] = np.where(
                    df['cadena'].str.upper().isin(invalid),
                    df['cliente'], df['cadena']
                )
            return df

        rules = {
            "id_patterns":   id_patterns,
            "id_explicit":   id_explicit,
            "text_cols":     text_cols,
            "numeric_cols":  numeric_cols,
            "business_rule": _identificador_rule,
        }
        return DataSanitizer._apply_rules(df, rules)
