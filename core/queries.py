"""
SISTEMA: RIMEC Business Intelligence
MODULO: core/queries.py
VERSION: 72.0.0 (GLOBAL-CONTROL / SQL-NEUTRALIZER)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Motor de consultas de alto rendimiento con neutralización de filtros.
              Permite visión "TODOS" mediante la omisión táctica de predicados SQL.
"""

import streamlit as st
from .database import get_dataframe, DBInspector
from .data_sanitizer import DataSanitizer
from core.settings import settings
import pandas as pd
import numpy as np
import time

class QueryCenter:
    """
    Motor v72.0.0: RIMEC - The Speed of Light.
    Misión: Ejecución de consultas con capacidad de visión global (TODOS).
    """

    @staticmethod
    def get_main_sales_query(filters):
        t_init = time.time()
        DBInspector.log("🚀 [MOTOR-SQL] Ignición v72.0.0 - Protocolo Global Activo.", "V2-TRACE")

        conditions = []
        params = {}

        # --- 1. CONSTRUCCIÓN DE FILTROS (Neutralización Táctica) ---
        
        # A. Horizonte Temporal
        meses_sel = filters.get('meses', [])
        if meses_sel:
            mes_map = {
                "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
                "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
            }
            mes_ids = [mes_map[m] for m in meses_sel if m in mes_map]
            if mes_ids and len(mes_ids) < 12: # Si son 12, es "Año Completo", neutralizamos para velocidad
                placeholders = [f":mes_{i}" for i in range(len(mes_ids))]
                conditions.append(f"EXTRACT(MONTH FROM v.fecha)::INTEGER IN ({', '.join(placeholders)})")
                for i, v in enumerate(mes_ids): params[f"mes_{i}"] = v

        # B. Neutralización de Departamento (Visión Global)
        tipo_val = filters.get('departamento', "TODOS")
        if tipo_val and str(tipo_val).upper() not in ["TODOS", "GLOBAL", "ALL", ""]:
            conditions.append("t.descp_tipo = :depto")
            params['depto'] = str(tipo_val)
            DBInspector.log(f"🎯 Filtro Depto: {tipo_val}", "V2-TRACE")
        else:
            DBInspector.log("🌐 Visión Global: Departamento Neutralizado.", "SUCCESS")

        # C. Neutralización de Categoría (IDs)
        cat_ids = filters.get('categoria_ids', [])
        # Filtramos '0' (que representa TODOS)
        clean_cat_ids = [str(x).strip() for x in cat_ids if str(x).strip() and str(x).strip() != "0"]
        if clean_cat_ids:
            placeholders = [f":cat_{i}" for i in range(len(clean_cat_ids))]
            conditions.append(f"v.id_categoria::TEXT IN ({', '.join(placeholders)})")
            for i, v in enumerate(clean_cat_ids): params[f"cat_{i}"] = v
        else:
            DBInspector.log("🌐 Visión Global: Categorías Neutralizadas.", "SUCCESS")

        # D. Entidades Dinámicas (Marcas, Cadenas, Vendedores, Clientes)
        mapping = {
            'vendedores': 'ven.descp_vendedor',
            'marcas': 'm.descp_marca',
            'cadenas': 'cad.descp_cadena',
            'clientes': 'c.descp_cliente'
        }
        for key, db_col in mapping.items():
            val_list = filters.get(key, [])
            if not isinstance(val_list, list): val_list = [val_list]
            # Si el filtro contiene "TODOS" o está vacío, no agregamos la condición
            clean_vals = [str(x).strip() for x in val_list if x and str(x).upper() not in ["TODOS", ""]]
            if clean_vals:
                placeholders = [f":{key}_{i}" for i in range(len(clean_vals))]
                conditions.append(f"{db_col} IN ({', '.join(placeholders)})")
                for i, v in enumerate(clean_vals): params[f"{key}_{i}"] = v

        # E. ID Cliente Exacto
        id_cliente = filters.get('id_cliente_exacto')
        if id_cliente and str(id_cliente).strip():
            params['id_cli_ex'] = str(id_cliente).strip()
            conditions.append("v.id_cliente::TEXT = :id_cli_ex")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # --- 2. EJECUCIÓN SQL (Arquitectura de Unión) ---
        query = f"""
            SELECT
                v.fecha,
                COALESCE(v.monto, 0) as monto,
                COALESCE(v.cantidad, 0) as cantidad,
                EXTRACT(YEAR FROM v.fecha)::INTEGER as anio,
                EXTRACT(MONTH FROM v.fecha)::INTEGER as mes_idx,
                TRIM(t.descp_tipo) as tipo,
                TRIM(m.descp_marca) as marca,
                TRIM(c.descp_cliente) as cliente,
                TRIM(ven.descp_vendedor) as vendedor,
                COALESCE(TRIM(cad.descp_cadena), 'S/C') as cadena,
                v.id_cliente::TEXT as codigo_cliente
            FROM registro_ventas_general_v2 v
            JOIN tipo_v2 t ON v.id_tipo = t.id_tipo
            JOIN marca_v2 m ON v.id_marca = m.id_marca
            JOIN cliente_v2 c ON v.id_cliente = c.id_cliente
            JOIN vendedor_v2 ven ON v.id_vendedor = ven.id_vendedor
            LEFT JOIN cliente_cadena_v2 cc ON v.id_cliente = cc.id_cliente
            LEFT JOIN cadena_v2 cad ON cc.id_cadena = cad.id_cadena
            {where_clause}
        """

        try:
            t_sql = time.time()
            df = get_dataframe(query, params)
            
            if df is None or df.empty:
                DBInspector.log("⚠️ [MOTOR-SQL] La combinación de filtros no devolvió datos.", "WARNING")
                return pd.DataFrame()

            sql_lat = time.time() - t_sql

            # --- 3. CÁLCULOS VECTORIZADOS (Inteligencia de Negocio) ---
            t_math = time.time()

            # Máscaras de alta velocidad
            is_2025 = (df['anio'] == 2025)
            is_2026 = (df['anio'] == 2026)

            # Segregación de valores
            df['monto_25'] = np.where(is_2025, df['monto'], 0.0)
            df['cant_25'] = np.where(is_2025, df['cantidad'], 0.0)
            df['monto_26'] = np.where(is_2026, df['monto'], 0.0)
            df['cant_26'] = np.where(is_2026, df['cantidad'], 0.0)

            # Inyección de Objetivo Dinámico
            obj_pct = filters.get('objetivo_pct', 20)
            multiplicador = 1 + (obj_pct / 100)
            df['monto_obj'] = df['monto_25'] * multiplicador
            df['cant_obj'] = (df['cant_25'] * multiplicador).round(0)

            # Identificador Maestro (Cadena o Cliente)
            df['identificador'] = np.where(df['cadena'] != 'S/C', df['cadena'], df['cliente'])

            math_lat = time.time() - t_math

            # --- 4. SANEAMIENTO FINAL ---
            df = DataSanitizer.clean_data(df, module="sales")
            
            total_lat = time.time() - t_init
            DBInspector.log(f"✅ [MOTOR-READY] {len(df)} registros | SQL: {sql_lat:.2f}s | Math: {math_lat:.4f}s", "SUCCESS")

            # Publicación para Cascada UI
            st.session_state.raw_universe = df

            return df

        except Exception as e:
            DBInspector.log(f"🔥 [FATAL-SQL] Error en Motor v72.0.0: {str(e)}", "ERROR")
            return pd.DataFrame()