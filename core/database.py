# =============================================================================
# SISTEMA: RIMEC Business Intelligence
# MODULO: core/database.py
# VERSION: 94.5.2 | NEXUS CORE (TELEMETRY ENABLED)
# AUTOR: Héctor & Gemini AI
# DESCRIPCIÓN: Motor Database optimizado con soporte para telemetría de latencia.
#              Sincronizado con el protocolo de 3 argumentos para DBInspector.
# =============================================================================

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import time
import sys
import numpy as np
import logging

# Configuración del Logger para trazabilidad profesional
logger = logging.getLogger("RIMEC.Database")

class DBInspector:
    """Protocolo de auditoría técnica: Blindaje y Telemetría v94.5."""

    @staticmethod
    def log(msg, level="DB-AUDIT", duration=None):
        """
        Registra eventos en consola y logger profesional.
        Soporta telemetría de latencia opcional.
        """
        colors = {
            "AVISO": "\033[93m",
            "ERROR": "\033[91m",
            "MANTENIMIENTO": "\033[95m",
            "DB-AUDIT": "\033[96m",
            "V2-TRACE": "\033[94m",
            "SUCCESS": "\033[92m"
        }
        reset = "\033[0m"
        color = colors.get(level, reset)

        # Formateo de Telemetría si existe duración
        time_tag = f" | ⏱️ {duration:.2f}ms" if duration is not None else ""
        full_msg = f"{msg}{time_tag}"

        # Salida a sys.stderr para visibilidad en consola de Streamlit
        print(f"{color}[{level}]{reset} {full_msg}", file=sys.stderr)

        if level == "ERROR":
            logger.error(full_msg)
        else:
            logger.info(f"[{level}] {full_msg}")

@st.cache_resource
def get_engine():
    """Motor persistente con Pool de Conexiones Optimizado v94.5."""
    try:
        s = st.secrets["postgres"]
        app_name = "rimec_nexus_v94"

        conn_str = (
            f"postgresql://{s['user']}:{s['password']}@"
            f"{s['host']}:{s['port']}/{s['dbname']}"
            f"?sslmode=require&application_name={app_name}"
        )

        return create_engine(
            conn_str,
            pool_pre_ping=True,
            pool_size=25,
            max_overflow=35,
            pool_recycle=1800,
            connect_args={
                "connect_timeout": 20,
                "options": "-c client_encoding=utf8"
            }
        )
    except Exception as e:
        # Aquí usamos el nuevo soporte de 2 argumentos (el 3ero es opcional)
        DBInspector.log(f"🚨 FALLO CRÍTICO EN ENGINE: {e}", "ERROR")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# ⚡ IGNICIÓN DEL MOTOR (DECLARACIÓN GLOBAL)
# ─────────────────────────────────────────────────────────────────────────────
engine = get_engine()

def get_dataframe(query, params=None):
    """Lectura Atómica con Normalización Pandas 2.0+."""
    start_time = time.time()

    if engine is None:
        return pd.DataFrame()

    safe_params = {}
    if params:
        for k, v in params.items():
            if v == "TODOS" or v == ["TODOS"]:
                continue
            if isinstance(v, str) and v.strip() == "":
                safe_params[k] = None
            else:
                safe_params[k] = v

    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=safe_params)

        if df.empty:
            return df

        # --- NORMALIZACIÓN PANDAS 2.0+ ---
        text_cols = df.select_dtypes(include=['object']).columns
        null_variants = ['None', 'nan', 'NULL', '', ' ']

        df = df.replace(null_variants, np.nan).infer_objects(copy=False)

        for col in text_cols:
            df[col] = df[col].astype(str).str.strip()

        duration = (time.time() - start_time) * 1000
        # Inyectamos telemetría en el log de éxito
        DBInspector.log(f"✅ SQL OK | Filas: {len(df)}", "SUCCESS", duration)
        return df

    except Exception as e:
        DBInspector.log(f"❌ ERROR SQL: {e}", "ERROR")
        return pd.DataFrame()

def commit_query(query, params=None, show_error=True):
    """Escritura Segura con Saneamiento de Transacción."""
    start_time = time.time()

    if not engine:
        return False

    safe_params = {k: (None if (isinstance(v, str) and v.strip() == "") else v)
                   for k, v in (params or {}).items()}

    try:
        with engine.begin() as conn:
            result = conn.execute(text(query), safe_params)
            duration = (time.time() - start_time) * 1000
            DBInspector.log(f"🚀 Commit OK | Afectadas: {result.rowcount}", "SUCCESS", duration)
            return True
    except Exception as e:
        if show_error:
            DBInspector.log(f"🔥 FALLO EN ESCRITURA: {e}", "ERROR")
        return False

