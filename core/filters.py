"""
SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
UBICACIÓN: core/filters.py
VERSION: 91.0.0 (DYNAMIC CATEGORIES - DB DRIVEN)
DESCRIPCIÓN: Gestión de estado de filtros. Categorías cargadas desde categoria_v2.
             Sin microfonía debug en producción.
"""

import streamlit as st
from datetime import datetime
import time
import copy
from .database import get_dataframe, DBInspector
from core.constants import MESES_LISTA


class FilterManager:
    """Gestión de estado de filtros. Draft → Commit → SQL."""

    # ── CATEGORÍAS DINÁMICAS ──────────────────────────────────────────────────

    @staticmethod
    @st.cache_data(ttl=3600)
    def _fetch_categories() -> dict:
        """Carga {nombre: id} desde categoria_v2. Fallback hardcodeado si falla BD."""
        try:
            df = get_dataframe(
                "SELECT id_categoria, TRIM(descp_categoria) AS nombre "
                "FROM categoria_v2 ORDER BY id_categoria"
            )
            if df is not None and not df.empty:
                result = {"TODOS": 0}
                for _, row in df.iterrows():
                    result[str(row['nombre']).title()] = int(row['id_categoria'])
                return result
        except Exception as e:
            DBInspector.log(f"[FILTER] Error cargando categorías: {e}", "ERROR")
        return {"TODOS": 0, "Stock": 1, "Pre Venta": 2, "Programado": 3}

    @staticmethod
    def get_categoria_map() -> dict:
        """Retorna el mapa {nombre: id} desde master_options o BD."""
        return st.session_state.get('master_options', {}).get(
            'categorias_map', FilterManager._fetch_categories()
        )

    # ── TIPOS (DEPARTAMENTOS) ─────────────────────────────────────────────────

    @staticmethod
    @st.cache_data(ttl=3600)
    def _fetch_master_types() -> list:
        try:
            df = get_dataframe("SELECT DISTINCT descp_tipo FROM tipo_v2 ORDER BY descp_tipo")
            if df is not None and not df.empty:
                res = sorted([str(x).strip() for x in df['descp_tipo'].unique()])
                if "TODOS" not in res:
                    res.insert(0, "TODOS")
                return res
        except Exception as e:
            DBInspector.log(f"[FILTER] Error cargando tipos: {e}", "ERROR")
        return ["TODOS", "CALZADOS", "TEXTIL"]

    # ── INICIALIZACIÓN ────────────────────────────────────────────────────────

    @staticmethod
    def _load_master_options():
        # Invalida caché si el formato es antiguo (sin categorias_map)
        if st.session_state.get('master_options', {}).get('categorias_map') is None:
            st.session_state.pop('master_options', None)

        if 'master_options' not in st.session_state:
            tipos    = FilterManager._fetch_master_types()
            cat_map  = FilterManager._fetch_categories()
            st.session_state.master_options = {
                "departamentos":  tipos,
                "categorias_map": cat_map,
                "categorias":     list(cat_map.keys()),
            }

    @staticmethod
    def initialize_filters():
        if 'user' not in st.session_state:
            return
        if 'filters' not in st.session_state:
            t = time.time()
            DBInspector.log("[FILTER-INIT] Inicializando estado...", "V2-TRACE")
            if 'meses_key_tracker' not in st.session_state:
                st.session_state.meses_key_tracker = 0
            FilterManager._load_master_options()
            st.session_state.filters = {
                "objetivo_pct":     20.0,
                "departamento":     "CALZADOS",
                "categoria_ids":    [3],        # ID 3 = Programado
                "meses":            MESES_LISTA[:6],
                "cadenas":          [],
                "clientes":         [],
                "vendedores":       [],
                "marcas":           [],
                "id_cliente_exacto": None,
                "must_reload":      True,
                "last_sync":        datetime.now().strftime("%H:%M:%S"),
            }
            st.session_state.filter_draft = copy.deepcopy(st.session_state.filters)
            DBInspector.log(f"[FILTER-INIT] Listo en {time.time()-t:.4f}s", "SUCCESS")

    # ── METADATA PARA PDF ─────────────────────────────────────────────────────

    @staticmethod
    def get_report_metadata() -> dict:
        f       = FilterManager.get_all_committed()
        cat_map = FilterManager.get_categoria_map()
        rev_map = {v: k for k, v in cat_map.items()}

        cat_names   = [rev_map.get(cid, f"ID:{cid}") for cid in f.get('categoria_ids', [])]
        cat_str     = ", ".join(cat_names) if cat_names else "TODAS"
        meses       = f.get('meses', [])
        periodo_str = (f"{meses[0]} - {meses[-1]}" if len(meses) >= 6
                       else ", ".join(m[:3] for m in meses) if meses else "N/A")

        return {
            "porcentaje":   f"{f.get('objetivo_pct', 0):,.2f}%",
            "depto":        str(f.get('departamento', 'TODOS')).upper(),
            "cat":          cat_str.upper(),
            "periodo":      periodo_str.upper(),
            "objetivo_puro": float(f.get('objetivo_pct', 0)) / 100,
        }

    # ── UNIVERSO UI ───────────────────────────────────────────────────────────

    @staticmethod
    def get_sales_ui_universe(df_raw) -> dict:
        maestros = st.session_state.get('master_options', {})

        def clean_list(serie, force_item=None):
            if serie is None:
                return []
            res = sorted([str(x).strip() for x in serie.dropna().unique()
                          if str(x).strip() not in ("", "None", "nan", "NaN", "CLIENTE S/I")])
            if force_item and force_item not in res:
                res.insert(0, force_item)
            return res

        base = {
            "departamentos": maestros.get("departamentos", ["TODOS", "CALZADOS"]),
            "categorias":    maestros.get("categorias",    ["TODOS"]),
            "marcas": [], "cadenas": [], "clientes": [], "vendedores": [],
        }
        if df_raw is None or df_raw.empty:
            return base

        base.update({
            "marcas":     clean_list(df_raw.get('marca')),
            "vendedores": clean_list(df_raw.get('vendedor')),
            "cadenas":    clean_list(df_raw.get('cadena'), force_item="S/C"),
            "clientes":   clean_list(df_raw.get('cliente')),
        })
        return base

    # ── CRUD DE ESTADO ────────────────────────────────────────────────────────

    @staticmethod
    def update_draft(key, value):
        FilterManager.initialize_filters()
        if key == "categoria_ids":
            cat_map = FilterManager.get_categoria_map()
            value   = [cat_map.get(v, v) if isinstance(v, str) else v for v in value]
        if 'filter_draft' in st.session_state:
            st.session_state.filter_draft[key] = value

    @staticmethod
    def update_meses_shortcut(meses_list):
        FilterManager.update_draft("meses", meses_list)
        if 'meses_key_tracker' in st.session_state:
            st.session_state.meses_key_tracker += 1
        FilterManager.commit_filters()

    @staticmethod
    def commit_filters():
        FilterManager.initialize_filters()
        st.session_state.filters = copy.deepcopy(st.session_state.filter_draft)
        st.session_state.filters["must_reload"] = True
        st.session_state.filters["last_sync"]   = datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def reset_all_filters():
        DBInspector.log("[FILTER] Reinicio maestro.", "AVISO")
        defaults = {
            "objetivo_pct": 20.0, "departamento": "CALZADOS",
            "categoria_ids": [3], "meses": MESES_LISTA[:6],
            "cadenas": [], "clientes": [], "vendedores": [],
            "marcas": [], "id_cliente_exacto": None,
        }
        for k, v in defaults.items():
            st.session_state.filter_draft[k] = v
        st.session_state.meses_key_tracker += 1
        FilterManager.commit_filters()

    @staticmethod
    def set_reload_state(state: bool):
        FilterManager.initialize_filters()
        if 'filters' in st.session_state:
            st.session_state.filters["must_reload"] = state

    @staticmethod
    def get_draft(key, default=None):
        FilterManager.initialize_filters()
        return st.session_state.filter_draft.get(key, default)

    @staticmethod
    def get_all_committed() -> dict:
        FilterManager.initialize_filters()
        return copy.deepcopy(st.session_state.filters)

    @staticmethod
    def should_reload() -> bool:
        FilterManager.initialize_filters()
        return st.session_state.filters.get("must_reload", True)
