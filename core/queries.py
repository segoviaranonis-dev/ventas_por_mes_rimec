"""
SISTEMA: RIMEC Business Intelligence
MODULO: core/queries.py
VERSION: 73.0.0 (PIVOT-VIEW - MATEMÁTICAS EN BASE DE DATOS)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Motor de consultas contra la vista v_ventas_pivot.
              v73.0.0: La BD entrega monto_26 y monto_25 pre-pivoteados.
              Python solo aplica objetivo_pct (parámetro dinámico de usuario)
              y calcula ALIAS_TARGET_VALUE / ALIAS_VARIATION.
"""

import streamlit as st
from .database import get_dataframe, DBInspector
from core.constants import ALIAS_CURRENT_VALUE, ALIAS_TARGET_VALUE, ALIAS_VARIATION
import pandas as pd
import numpy as np


class QueryCenter:
    """
    Motor v73.0.0: Consulta v_ventas_pivot.
    La BD hace el JOIN 7 tablas + pivot año. Python aplica objetivo y variación.
    """

    @staticmethod
    def get_main_sales_query(filters):
        DBInspector.log("🚀 [MOTOR-SQL] Ignición v73 - Pivot View Activa.", "V2-TRACE")

        conditions = []
        params = {}

        # --- 1. CONSTRUCCIÓN DE FILTROS ---
        meses_sel = filters.get('meses', [])
        if meses_sel:
            mes_map = {
                "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4,
                "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
                "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
            }
            mes_ids = [mes_map[m] for m in meses_sel if m in mes_map]
            if mes_ids and len(mes_ids) < 12:
                placeholders = [f":mes_{i}" for i in range(len(mes_ids))]
                conditions.append(f"mes_idx IN ({', '.join(placeholders)})")
                for i, v in enumerate(mes_ids):
                    params[f"mes_{i}"] = v

        tipo_val = filters.get('departamento', "TODOS")
        if tipo_val and str(tipo_val).upper() not in ["TODOS", "GLOBAL", "ALL", ""]:
            conditions.append("tipo = :depto")
            params['depto'] = str(tipo_val)

        # Categorías (IDs numéricos; 0 = TODOS → se omite)
        cat_ids = filters.get('categoria_ids', [])
        if not isinstance(cat_ids, list):
            cat_ids = [cat_ids]
        cat_ids = [int(c) for c in cat_ids if c and int(c) != 0]
        if cat_ids:
            placeholders = [f":cat_{i}" for i in range(len(cat_ids))]
            conditions.append(f"id_categoria IN ({', '.join(placeholders)})")
            for i, v in enumerate(cat_ids):
                params[f"cat_{i}"] = v

        # Código de cliente exacto (busca por codigo_cliente)
        id_exacto = str(filters.get('id_cliente_exacto') or '').strip()
        if id_exacto:
            conditions.append("codigo_cliente = :id_exacto")
            params['id_exacto'] = id_exacto

        # Filtros de entidades — columnas directas de la vista
        entity_map = {
            'vendedores': 'vendedor',
            'marcas':     'marca',
            'cadenas':    'cadena',
            'clientes':   'cliente',
        }
        for key, col in entity_map.items():
            val_list = filters.get(key, [])
            if not isinstance(val_list, list):
                val_list = [val_list]
            clean_vals = [str(x).strip() for x in val_list
                          if x and str(x).upper() not in ["TODOS", ""]]
            if clean_vals:
                placeholders = [f":{key}_{i}" for i in range(len(clean_vals))]
                conditions.append(f"{col} IN ({', '.join(placeholders)})")
                for i, v in enumerate(clean_vals):
                    params[f"{key}_{i}"] = v

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # --- 2. EJECUCIÓN SQL (vista pre-pivoteada) ---
        query = f"SELECT * FROM v_ventas_pivot{where_clause}"

        try:
            df = get_dataframe(query, params)

            if df is None or df.empty:
                return pd.DataFrame()

            # --- 3. OBJETIVO Y VARIACIÓN (parámetro dinámico de usuario) ---
            df['monto_25'] = pd.to_numeric(df['monto_25'], errors='coerce').fillna(0.0)
            df['monto_26'] = pd.to_numeric(df['monto_26'], errors='coerce').fillna(0.0)

            obj_pct      = filters.get('objetivo_pct', 20)
            multiplicador = 1 + (obj_pct / 100)

            df[ALIAS_CURRENT_VALUE] = df['monto_26']
            df[ALIAS_TARGET_VALUE]  = df['monto_25'] * multiplicador
            df[ALIAS_VARIATION]     = np.where(
                df[ALIAS_TARGET_VALUE] > 0,
                (df[ALIAS_CURRENT_VALUE] - df[ALIAS_TARGET_VALUE]) / df[ALIAS_TARGET_VALUE],
                np.where(df[ALIAS_CURRENT_VALUE] > 0, 1.0, 0.0)
            )

            # --- 4. LIMPIEZA MÍNIMA PARA AGGRID ---
            # Texto: strip + uppercase (la BD ya hace TRIM pero protegemos)
            for col in ['tipo', 'marca', 'cliente', 'vendedor', 'cadena']:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip().str.upper()
                    df[col] = df[col].replace(
                        ['NAN', 'NONE', 'NULL', 'NONETYPE', '<NA>', ''], 'S/I'
                    )

            DBInspector.log(
                f"✅ [MOTOR-READY] v73 OK: {len(df)} filas | obj={obj_pct}%",
                "SUCCESS"
            )
            st.session_state.raw_universe = df
            return df

        except Exception as e:
            DBInspector.log(f"🔥 [FATAL-SQL] Colapso Motor v73: {str(e)}", "ERROR")
            return pd.DataFrame()
