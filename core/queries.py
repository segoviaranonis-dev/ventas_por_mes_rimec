"""
SISTEMA: RIMEC Business Intelligence — core/queries.py v74.0.0
Consulta v_ventas_pivot y aplica objetivo_pct en Python.
"""

import streamlit as st
import pandas as pd
import numpy as np
from .database import get_dataframe, DBInspector
from core.constants import ALIAS_CURRENT_VALUE, ALIAS_TARGET_VALUE, ALIAS_VARIATION, MES_MAP


def _in(col, key, values, conditions, params):
    """Agrega condición IN al WHERE y carga los parámetros."""
    placeholders = [f":{key}_{i}" for i in range(len(values))]
    conditions.append(f"{col} IN ({', '.join(placeholders)})")
    for i, v in enumerate(values):
        params[f"{key}_{i}"] = v


class QueryCenter:

    @staticmethod
    def get_main_sales_query(filters):
        conditions, params = [], {}

        # Meses
        mes_ids = [MES_MAP[m] for m in filters.get('meses', []) if m in MES_MAP]
        if mes_ids and len(mes_ids) < 12:
            _in("mes_idx", "mes", mes_ids, conditions, params)

        # Departamento / tipo
        depto = str(filters.get('departamento', '') or '').strip().upper()
        if depto and depto not in ("TODOS", "GLOBAL", "ALL", ""):
            conditions.append("tipo = :depto")
            params['depto'] = depto

        # Categorías (0 = TODOS → omitir)
        cat_ids = [int(c) for c in filters.get('categoria_ids', []) if c and int(c) != 0]
        if cat_ids:
            _in("id_categoria", "cat", cat_ids, conditions, params)

        # Código de cliente exacto
        id_exacto = str(filters.get('id_cliente_exacto') or '').strip()
        if id_exacto:
            conditions.append("codigo_cliente = :id_exacto")
            params['id_exacto'] = id_exacto

        # Entidades (vendedores, marcas, cadenas, clientes)
        for key, col in [('vendedores','vendedor'), ('marcas','marca'),
                         ('cadenas','cadena'), ('clientes','cliente')]:
            vals = [str(x).strip() for x in filters.get(key, [])
                    if x and str(x).upper() not in ("TODOS", "")]
            if vals:
                _in(col, key, vals, conditions, params)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        try:
            df = get_dataframe(f"SELECT * FROM v_ventas_pivot{where}", params)
            if df is None or df.empty:
                return pd.DataFrame()

            # Objetivo y variación (parámetro dinámico — no puede vivir en la BD)
            df['monto_25'] = pd.to_numeric(df['monto_25'], errors='coerce').fillna(0.0)
            df['monto_26'] = pd.to_numeric(df['monto_26'], errors='coerce').fillna(0.0)
            mult = 1 + (filters.get('objetivo_pct', 20) / 100)
            df[ALIAS_CURRENT_VALUE] = df['monto_26']
            df[ALIAS_TARGET_VALUE]  = df['monto_25'] * mult
            df[ALIAS_VARIATION]     = np.where(
                df[ALIAS_TARGET_VALUE] > 0,
                (df[ALIAS_CURRENT_VALUE] - df[ALIAS_TARGET_VALUE]) / df[ALIAS_TARGET_VALUE],
                np.where(df[ALIAS_CURRENT_VALUE] > 0, np.nan, 0.0)
            )
            # Columnas de cantidad (misma lógica que montos)
            if 'cant_25' in df.columns and 'cant_26' in df.columns:
                df['cant_25'] = pd.to_numeric(df['cant_25'], errors='coerce').fillna(0.0)
                df['cant_26'] = pd.to_numeric(df['cant_26'], errors='coerce').fillna(0.0)
                df['Cant. Obj']   = df['cant_25'] * mult
                df['Cant. 2026']  = df['cant_26']
                df['Cant. V. %']  = np.where(
                    df['Cant. Obj'] > 0,
                    (df['Cant. 2026'] - df['Cant. Obj']) / df['Cant. Obj'],
                    np.where(df['Cant. 2026'] > 0, np.nan, 0.0)
                )

            # Limpieza mínima de texto para AgGrid
            for col in ['tipo', 'marca', 'cliente', 'vendedor', 'cadena']:
                if col in df.columns:
                    df[col] = (df[col].astype(str).str.strip().str.upper()
                               .replace(['NAN','NONE','NULL','NONETYPE','<NA>',''], 'S/I'))

            DBInspector.log(f"✅ [MOTOR] v74 OK: {len(df)} filas", "SUCCESS")
            st.session_state.raw_universe = df
            return df

        except Exception as e:
            DBInspector.log(f"🔥 [FATAL-SQL] {str(e)}", "ERROR")
            return pd.DataFrame()
