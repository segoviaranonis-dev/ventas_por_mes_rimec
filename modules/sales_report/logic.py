"""
SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
UBICACIÓN: modules/sales_report/logic.py
VERSION: 104.0.0 (DISTRIBUIDOR PURO - SIN MATEMÁTICAS)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Distribuidor de datos para AgGrid.
              v104.0.0: Las matemáticas viven en la BD (v_ventas_pivot) y en
              queries.py (objetivo_pct). Este módulo solo agrupa para display
              y construye _path para treeData.
              Contrato de entrada: DataFrame con columnas
                  [tipo, marca, cliente, codigo_cliente, vendedor, cadena,
                   mes_idx, monto_26, monto_25, ALIAS_CURRENT_VALUE,
                   ALIAS_TARGET_VALUE, ALIAS_VARIATION]
"""

import pandas as pd
import numpy as np
import time
from decimal import Decimal
from core.database import DBInspector
from core.constants import (
    ALIAS_CURRENT_VALUE, ALIAS_TARGET_VALUE, ALIAS_VARIATION
)

_MES_NOMBRES = {
    1: 'Enero',     2: 'Febrero',   3: 'Marzo',    4: 'Abril',
    5: 'Mayo',      6: 'Junio',     7: 'Julio',     8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

_CADENA_NULA = {'S/C', 'NONE', 'NAN', 'N/A', '', 'NULL', 'S/I', '---', '-'}
_SEP = '|||'


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _calc_var(df_in, real_col, obj_col):
    """Variación % con blindaje ante división por cero."""
    return np.where(
        df_in[obj_col] > 0,
        (df_in[real_col] - df_in[obj_col]) / df_in[obj_col] * 100,
        np.where(df_in[real_col] > 0, 100.0, 0.0)
    )


def _agg(df, group_cols):
    """Agrupa y suma las columnas de alias. Recalcula variación."""
    df_g = df.groupby(group_cols, as_index=False).agg(**{
        ALIAS_CURRENT_VALUE: (ALIAS_CURRENT_VALUE, 'sum'),
        ALIAS_TARGET_VALUE:  (ALIAS_TARGET_VALUE,  'sum'),
    })
    df_g[ALIAS_VARIATION] = _calc_var(df_g, ALIAS_CURRENT_VALUE, ALIAS_TARGET_VALUE)
    return df_g


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class SalesLogic:

    @staticmethod
    def _mic(msg, level="INFO"):
        DBInspector.log(f"🧠 [LOGIC-CORE] {msg}", level)

    @staticmethod
    def sanitize_for_ui(data):
        """Convierte Decimal → float recursivamente para Streamlit/AgGrid."""
        if isinstance(data, dict):
            return {k: SalesLogic.sanitize_for_ui(v) for k, v in data.items()}
        if isinstance(data, (list, tuple)):
            s = [SalesLogic.sanitize_for_ui(v) for v in data]
            return tuple(s) if isinstance(data, tuple) else s
        if isinstance(data, Decimal):
            return float(data)
        if isinstance(data, pd.DataFrame):
            df = data.loc[:, ~data.columns.duplicated()].copy()
            return df.apply(
                lambda col: col.map(lambda x: float(x) if isinstance(x, Decimal) else x)
            )
        return data

    @staticmethod
    def get_full_analysis_package(raw_data, objetivo=100, meses=None):
        """
        CONTRATO UI v104 — misma estructura que v103:
        {
          'evolucion':  DataFrame,
          'cartera':    {'crecimiento': df, 'decrecimiento': df, 'sin_compra': df},
          'marcas':     (df_ranking, df_detalle),
          'vendedores': (df_ranking, df_detalle),
          'kpis':       {'clientes_26': int, 'atendimiento': float%, 'variacion_total': float%}
        }
        """
        t_start = time.time()

        if raw_data is None or raw_data.empty:
            return None

        df = raw_data.copy()

        # Garantizar tipos numéricos en columnas de alias
        for col in [ALIAS_CURRENT_VALUE, ALIAS_TARGET_VALUE, ALIAS_VARIATION]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            else:
                df[col] = 0.0

        # ── ARTERIA A: EVOLUCIÓN MENSUAL ──────────────────────────────────────
        if 'mes_idx' in df.columns:
            df_evol = _agg(df, ['mes_idx'])
            df_evol['Semestre'] = df_evol['mes_idx'].apply(
                lambda x: '1er SEMESTRE' if int(x) <= 6 else '2do SEMESTRE'
            )
            df_evol['Mes'] = df_evol['mes_idx'].map(_MES_NOMBRES).fillna('S/D')
            df_evol = df_evol.sort_values('mes_idx').drop(columns=['mes_idx'])
            col_order = ['Semestre', 'Mes', ALIAS_TARGET_VALUE, ALIAS_CURRENT_VALUE, ALIAS_VARIATION]
            df_evol = df_evol[[c for c in col_order if c in df_evol.columns]]
        else:
            df_evol = pd.DataFrame(
                columns=['Semestre', 'Mes', ALIAS_CURRENT_VALUE, ALIAS_TARGET_VALUE, ALIAS_VARIATION]
            )

        # ── ARTERIA B: CARTERA (Cadena → Cliente → Marca) ────────────────────
        if 'cliente' in df.columns:
            grp = ['cliente']
            if 'cadena' in df.columns: grp.append('cadena')
            if 'marca'  in df.columns: grp.append('marca')

            df_cli = _agg(df, grp)

            if 'cadena' in df_cli.columns:
                df_cli['Cadena'] = np.where(
                    df_cli['cadena'].str.upper().isin(_CADENA_NULA),
                    df_cli['cliente'], df_cli['cadena']
                )
                df_cli = df_cli.drop(columns=['cadena'])

            rename = {'cliente': 'Cliente'}
            if 'marca' in df_cli.columns: rename['marca'] = 'Marca'
            df_cli.rename(columns=rename, inplace=True)

            def _path_cli(r):
                cadena  = str(r.get('Cadena',  '')).strip()
                cliente = str(r.get('Cliente', '')).strip()
                marca   = str(r.get('Marca',   '')).strip()
                if cadena == cliente:
                    return _SEP.join([cliente, marca]) if marca else cliente
                return _SEP.join([cadena, cliente, marca]) if marca else _SEP.join([cadena, cliente])

            df_cli['_path'] = df_cli.apply(_path_cli, axis=1)

            _cli_cols = ['Cadena', 'Cliente', 'Marca',
                         ALIAS_TARGET_VALUE, ALIAS_CURRENT_VALUE, ALIAS_VARIATION, '_path']
            df_cli = df_cli[[c for c in _cli_cols if c in df_cli.columns]]

            mask_activo     = df_cli[ALIAS_CURRENT_VALUE] > 0
            df_crecimiento  = df_cli[mask_activo & (df_cli[ALIAS_VARIATION] >= 0)].sort_values(
                ALIAS_VARIATION, ascending=False).copy()
            df_decrecimiento = df_cli[mask_activo & (df_cli[ALIAS_VARIATION] < 0)].sort_values(
                ALIAS_VARIATION, ascending=True).copy()
            df_sin_compra   = df_cli[~mask_activo & (df_cli[ALIAS_TARGET_VALUE] > 0)].sort_values(
                ALIAS_TARGET_VALUE, ascending=False).copy()
        else:
            _empty = pd.DataFrame(
                columns=['Cadena', 'Cliente', 'Marca',
                         ALIAS_TARGET_VALUE, ALIAS_CURRENT_VALUE, ALIAS_VARIATION]
            )
            df_crecimiento = df_decrecimiento = df_sin_compra = _empty.copy()

        # ── ARTERIA C: MARCAS ─────────────────────────────────────────────────
        if 'marca' in df.columns:
            df_mar_gen = _agg(df, ['marca'])
            df_mar_gen.rename(columns={'marca': 'Marca'}, inplace=True)
            df_mar_gen = df_mar_gen.sort_values(ALIAS_CURRENT_VALUE, ascending=False)
            _mg_cols = ['Marca', ALIAS_TARGET_VALUE, ALIAS_CURRENT_VALUE, ALIAS_VARIATION]
            df_mar_gen = df_mar_gen[[c for c in _mg_cols if c in df_mar_gen.columns]]

            det_g = ['marca']
            det_r = {'marca': 'Marca'}
            for src, cap in [('cadena', 'Cadena'), ('cliente', 'Cliente'), ('vendedor', 'Vendedor')]:
                if src in df.columns:
                    det_g.append(src)
                    det_r[src] = cap

            df_mar_det = _agg(df, det_g)
            df_mar_det.rename(columns=det_r, inplace=True)

            def _path_mar(r):
                parts = [str(r.get('Marca', '')).strip()]
                cadena = str(r.get('Cadena', '')).strip()
                if cadena and cadena.upper() not in _CADENA_NULA:
                    parts.append(cadena)
                cliente = str(r.get('Cliente', '')).strip()
                if cliente: parts.append(cliente)
                vendedor = str(r.get('Vendedor', '')).strip()
                if vendedor: parts.append(vendedor)
                return _SEP.join(parts)

            df_mar_det['_path'] = df_mar_det.apply(_path_mar, axis=1)
            _md_cols = ['Marca', 'Cadena', 'Cliente', 'Vendedor',
                        ALIAS_TARGET_VALUE, ALIAS_CURRENT_VALUE, ALIAS_VARIATION, '_path']
            df_mar_det = df_mar_det[[c for c in _md_cols if c in df_mar_det.columns]]
        else:
            _empty_m = pd.DataFrame(
                columns=['Marca', ALIAS_TARGET_VALUE, ALIAS_CURRENT_VALUE, ALIAS_VARIATION]
            )
            df_mar_gen = df_mar_det = _empty_m.copy()

        # ── ARTERIA D: VENDEDORES ─────────────────────────────────────────────
        if 'vendedor' in df.columns:
            df_ven_gen = _agg(df, ['vendedor'])
            df_ven_gen.rename(columns={'vendedor': 'Vendedor'}, inplace=True)
            df_ven_gen = df_ven_gen.sort_values(ALIAS_CURRENT_VALUE, ascending=False)
            _vg_cols = ['Vendedor', ALIAS_TARGET_VALUE, ALIAS_CURRENT_VALUE, ALIAS_VARIATION]
            df_ven_gen = df_ven_gen[[c for c in _vg_cols if c in df_ven_gen.columns]]

            det_g_v = ['vendedor']
            det_r_v = {'vendedor': 'Vendedor'}
            for src, cap in [('cadena', 'Cadena'), ('cliente', 'Cliente'), ('marca', 'Marca')]:
                if src in df.columns:
                    det_g_v.append(src)
                    det_r_v[src] = cap
            if 'mes_idx' in df.columns:
                det_g_v.append('mes_idx')

            df_ven_det = _agg(df, det_g_v)
            df_ven_det.rename(columns=det_r_v, inplace=True)
            if 'mes_idx' in df_ven_det.columns:
                df_ven_det['Mes'] = df_ven_det['mes_idx'].map(_MES_NOMBRES).fillna('S/D')
                df_ven_det = df_ven_det.drop(columns=['mes_idx'])

            def _path_ven(r):
                parts = [str(r.get('Vendedor', '')).strip()]
                cadena = str(r.get('Cadena', '')).strip()
                if cadena and cadena.upper() not in _CADENA_NULA:
                    parts.append(cadena)
                cliente = str(r.get('Cliente', '')).strip()
                if cliente: parts.append(cliente)
                marca = str(r.get('Marca', '')).strip()
                if marca: parts.append(marca)
                mes = str(r.get('Mes', '')).strip()
                if mes: parts.append(mes)
                return _SEP.join(parts)

            df_ven_det['_path'] = df_ven_det.apply(_path_ven, axis=1)
            _vd_cols = ['Vendedor', 'Cadena', 'Cliente', 'Marca', 'Mes',
                        ALIAS_TARGET_VALUE, ALIAS_CURRENT_VALUE, ALIAS_VARIATION, '_path']
            df_ven_det = df_ven_det[[c for c in _vd_cols if c in df_ven_det.columns]]
        else:
            _empty_v = pd.DataFrame(
                columns=['Vendedor', ALIAS_TARGET_VALUE, ALIAS_CURRENT_VALUE, ALIAS_VARIATION]
            )
            df_ven_gen = df_ven_det = _empty_v.copy()

        # ── KPIs ──────────────────────────────────────────────────────────────
        # Cuenta clientes únicos con actividad en cada año
        if 'cliente' in df.columns:
            clientes_26 = int(df[df[ALIAS_CURRENT_VALUE] > 0]['cliente'].nunique())
            clientes_25 = int(df[df['monto_25'] > 0]['cliente'].nunique())
        else:
            clientes_26 = clientes_25 = 0

        atendimiento    = (clientes_26 / clientes_25 * 100) if clientes_25 > 0 else 0.0
        total_real      = float(df[ALIAS_CURRENT_VALUE].sum())
        total_obj       = float(df[ALIAS_TARGET_VALUE].sum())
        variacion_total = (
            (total_real - total_obj) / total_obj * 100
            if total_obj > 0 else (100.0 if total_real > 0 else 0.0)
        )

        # ── PAQUETE FINAL ──────────────────────────────────────────────────────
        package = {
            'evolucion': df_evol,
            'cartera': {
                'crecimiento':   df_crecimiento,
                'decrecimiento': df_decrecimiento,
                'sin_compra':    df_sin_compra,
            },
            'marcas':     (df_mar_gen, df_mar_det),
            'vendedores': (df_ven_gen, df_ven_det),
            'kpis': {
                'clientes_26':    clientes_26,
                'atendimiento':   atendimiento,
                'variacion_total': variacion_total,
            },
            'metadata': {
                'timestamp':    t_start,
                'status':       'MULTI-ARTERIA-COMPLETE',
                'registros':    len(df),
                'piano_engine': 'v4-pivot-view',
            }
        }

        SalesLogic._mic(
            f"v104 OK | {total_real:.0f} | Clientes: {clientes_26}/{clientes_25} "
            f"({atendimiento:.1f}%) | Var: {variacion_total:+.1f}%"
        )
        return SalesLogic.sanitize_for_ui(package)

# -----------------------------------------------------------------------------
# [EXECUTION-CONFIRMED] v104.0.0 - Distribuidor puro. Matemáticas en la BD.
# -----------------------------------------------------------------------------
