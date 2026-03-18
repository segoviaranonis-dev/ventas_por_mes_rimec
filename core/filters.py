"""
SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
UBICACIÓN: core/filters.py
VERSION: 90.5.2 (DEBUG + HOTFIX: RELOAD STATE)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Aduana de Integridad con Protocolo de Neutralización Total.
             Microfonía integrada para rastrear la fuga de datos hacia el PDF.
             Corrección de atributo faltante set_reload_state.
"""

import streamlit as st
from datetime import datetime
import pandas as pd
import time
from .database import get_dataframe, DBInspector
import copy

class FilterManager:
    """
    Motor de Gestión de Estado NEXUS CORE v72.
    Controla la persistencia, la neutralización de predicados y el reinicio maestro.
    """

    CATEGORIA_MAP = {
        "TODOS": 0,
        "Stock": 1,
        "Compra Previa": 2,
        "Programado": 3
    }

    # Inversión de mapa para traducción humana de IDs
    CATEGORIA_REV_MAP = {v: k for k, v in CATEGORIA_MAP.items()}

    @staticmethod
    def initialize_filters():
        """Inicializa el entorno con sensores de presencia y parámetros de fábrica."""
        if 'user' not in st.session_state:
            return

        if 'filters' not in st.session_state:
            t_init = time.time()
            DBInspector.log("[FILTER-INIT] Desplegando Chasis v72 - MODO GLOBAL...", "V2-TRACE")

            if 'meses_key_tracker' not in st.session_state:
                st.session_state.meses_key_tracker = 0

            # 1. Carga de Opciones Maestras
            FilterManager._load_master_options()

            # 2. Configuración de Inicio (Garantía de Negocio: Calzados/Programado)
            st.session_state.filters = {
                "objetivo_pct": 20.0,
                "departamento": "CALZADOS",
                "categoria_ids": [3], # ID 3 = Programado
                "meses": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio"],
                "cadenas": [],
                "clientes": [],
                "vendedores": [],
                "marcas": [],
                "id_cliente_exacto": None,
                "must_reload": True,
                "last_sync": datetime.now().strftime("%H:%M:%S")
            }

            st.session_state.filter_draft = copy.deepcopy(st.session_state.filters)
            DBInspector.log(f"[FILTER-INIT] Estado inicial inyectado en {time.time()-t_init:.4f}s", "SUCCESS")

    @staticmethod
    def get_report_metadata():
        """
        🎯 MÉTODO DE CONEXIÓN: Prepara el diccionario meta_info para el ReportEngine.
        """
        # --- MICROFONÍA DE ENTRADA ---
        print("\n" + "═"*60)
        print("🎤 [DEBUG-PDF] CAPTURANDO ESTADO ACTUAL PARA GENERAR PDF...")
        
        f = FilterManager.get_all_committed()
        
        # Log del estado crudo capturado
        print(f"📦 ESTADO EN SESSION_STATE (COMMITTED): {f}")

        # 1. Traducción de Categorías (ID -> Texto)
        cat_names = [FilterManager.CATEGORIA_REV_MAP.get(cid, f"ID:{cid}") for cid in f.get('categoria_ids', [])]
        cat_str = ", ".join(cat_names) if cat_names else "TODAS"
        print(f"🏷️ CATEGORÍAS TRADUCIDAS: {cat_str}")

        # 2. Formateo de Periodo (Meses)
        meses = f.get('meses', [])
        if not meses:
            periodo_str = "N/A"
        elif len(meses) >= 6:
            periodo_str = f"{meses[0]} - {meses[-1]}"
        else:
            periodo_str = ", ".join([m[:3] for m in meses])
        print(f"📅 PERIODO FORMATEADO: {periodo_str}")

        # 3. Empaquetado Final
        meta_info = {
            "porcentaje": f"{f.get('objetivo_pct', 0):,.2f}%",
            "depto": str(f.get('departamento', 'TODOS')).upper(),
            "cat": cat_str.upper(),
            "periodo": periodo_str.upper(),
            "objetivo_puro": float(f.get('objetivo_pct', 0)) / 100 
        }

        # --- MICROFONÍA DE SALIDA ---
        print("🚀 DATOS LISTOS PARA EL MOTOR PDF:")
        for k, v in meta_info.items():
            print(f"   ➤ {k}: {v}")
        print("═"*60 + "\n")

        return meta_info

    @staticmethod
    def set_reload_state(state: bool):
        """🔧 HOTFIX: Permite al sistema marcar si los datos requieren nueva consulta SQL."""
        FilterManager.initialize_filters()
        if 'filters' in st.session_state:
            st.session_state.filters["must_reload"] = state

    @staticmethod
    def reset_all_filters():
        """🔄 PROTOCOLO DE REINICIO MAESTRO"""
        DBInspector.log("[RESET-MAESTRO] Ejecutando purga...", "AVISO")
        
        factory_settings = {
            "objetivo_pct": 20.0,
            "departamento": "CALZADOS",
            "categoria_ids": [3],
            "meses": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio"],
            "cadenas": [],
            "clientes": [],
            "vendedores": [],
            "marcas": [],
            "id_cliente_exacto": None
        }
        
        for key, value in factory_settings.items():
            st.session_state.filter_draft[key] = value
        
        st.session_state.meses_key_tracker += 1
        FilterManager.commit_filters()

    @staticmethod
    @st.cache_data(ttl=3600)
    def _fetch_master_types():
        try:
            query = "SELECT DISTINCT descp_tipo FROM tipo_v2 ORDER BY descp_tipo"
            df_tipos = get_dataframe(query)
            if df_tipos is not None and not df_tipos.empty:
                res = sorted([str(x).strip() for x in df_tipos['descp_tipo'].unique()])
                if "TODOS" not in res:
                    res.insert(0, "TODOS")
                return res
        except Exception as e:
            DBInspector.log(f"[DB-FETCH-ERROR] {str(e)}", "ERROR")
        return ["TODOS", "CALZADOS", "TEXTIL"]

    @staticmethod
    def _load_master_options():
        if 'master_options' not in st.session_state:
            tipos = FilterManager._fetch_master_types()
            st.session_state.master_options = {
                "departamentos": tipos,
                "categorias": list(FilterManager.CATEGORIA_MAP.keys())
            }

    @staticmethod
    def get_sales_ui_universe(df_raw):
        maestros = st.session_state.get('master_options', {})
        if df_raw is None or df_raw.empty:
            return {
                "departamentos": maestros.get("departamentos", ["TODOS", "CALZADOS"]),
                "categorias": maestros.get("categorias", ["TODOS", "Programado", "Stock", "Compra Previa"]),
                "marcas": [], "cadenas": [], "clientes": [], "vendedores": []
            }

        def clean_list(serie, force_item=None):
            if serie is None: return []
            res = sorted([str(x).strip() for x in serie.dropna().unique() 
                         if str(x).strip() not in ["", "None", "nan", "CLIENTE S/I", "nan", "NaN"]])
            if force_item and force_item not in res:
                res.insert(0, force_item)
            return res

        return {
            "departamentos": maestros.get("departamentos"),
            "categorias": maestros.get("categorias"),
            "marcas": clean_list(df_raw.get('marca')),
            "vendedores": clean_list(df_raw.get('vendedor')),
            "cadenas": clean_list(df_raw.get('cadena'), force_item="S/C"),
            "clientes": clean_list(df_raw.get('cliente'))
        }

    @staticmethod
    def update_meses_shortcut(meses_list):
        FilterManager.update_draft("meses", meses_list)
        if 'meses_key_tracker' in st.session_state:
            st.session_state.meses_key_tracker += 1
        FilterManager.commit_filters()

    @staticmethod
    def update_draft(key, value):
        FilterManager.initialize_filters()
        if key == "categoria_ids":
            value = [FilterManager.CATEGORIA_MAP.get(v, v) if isinstance(v, str) else v for v in value]
        
        if 'filter_draft' in st.session_state:
            st.session_state.filter_draft[key] = value

    @staticmethod
    def commit_filters():
        FilterManager.initialize_filters()
        st.session_state.filters = copy.deepcopy(st.session_state.filter_draft)
        st.session_state.filters["must_reload"] = True
        st.session_state.filters["last_sync"] = datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def get_draft(key, default=None):
        FilterManager.initialize_filters()
        return st.session_state.filter_draft.get(key, default)

    @staticmethod
    def get_all_committed():
        FilterManager.initialize_filters()
        return copy.deepcopy(st.session_state.filters)

    @staticmethod
    def should_reload():
        FilterManager.initialize_filters()
        return st.session_state.filters.get("must_reload", True)