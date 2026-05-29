#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODULO: Diagnóstico de Stock Bloqueado
Herramienta de administración para rastrear pares bloqueados por FIs huérfanas
"""
import streamlit as st
import pandas as pd
from core.database import get_dataframe
from modules.aprobacion_pedidos.logic import anular_fi

st.set_page_config(page_title="Diagnóstico Stock", page_icon="🔍", layout="wide")

st.markdown("# 🔍 Diagnóstico de Stock Bloqueado")
st.markdown("Rastreo de pares bloqueados por Facturas Internas huérfanas")
st.divider()

# Input: número de PP
pp_numero = st.text_input("Número de PP (ej: PP-2026-0010):", value="PP-2026-0010")

if st.button("🔍 Analizar", type="primary"):
    # 1. Buscar PP
    df_pp = get_dataframe("""
        SELECT
            id,
            numero_registro,
            estado,
            quincena_arribo_id
        FROM pedido_proveedor
        WHERE numero_registro = :pp_nro
    """, {"pp_nro": pp_numero})

    if df_pp is None or df_pp.empty:
        st.error(f"❌ PP {pp_numero} no encontrado")
        st.stop()

    pp_id = int(df_pp['id'].iloc[0])
    st.success(f"✅ PP encontrado: ID {pp_id}")

    # 2. Resumen de stock
    df_stock = get_dataframe("""
        SELECT
            COUNT(*) as articulos,
            SUM(cantidad_pares) as total_pares,
            SUM(COALESCE(pares_vendidos, 0)) as pares_vendidos,
            SUM(cantidad_pares - COALESCE(pares_vendidos, 0)) as saldo_disponible
        FROM pedido_proveedor_detalle
        WHERE pedido_proveedor_id = :pp_id
    """, {"pp_id": pp_id})

    if df_stock is not None and not df_stock.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Artículos", int(df_stock['articulos'].iloc[0]))
        col2.metric("Pares Totales", int(df_stock['total_pares'].iloc[0]))
        col3.metric("🔒 Bloqueados", int(df_stock['pares_vendidos'].iloc[0]))
        col4.metric("✅ Disponibles", int(df_stock['saldo_disponible'].iloc[0]))

    st.divider()

    # 3. Facturas Internas
    st.markdown("### 📦 Facturas Internas del PP")

    df_fi = get_dataframe("""
        SELECT
            fi.id as fi_id,
            fi.nro_factura,
            fi.estado,
            fi.marca,
            fi.caso,
            fi.total_pares,
            fi.pedido_id,
            pvr.nro_pedido,
            pvr.estado as pedido_estado,
            fi.created_at
        FROM factura_interna fi
        LEFT JOIN pedido_venta_rimec pvr ON pvr.id = fi.pedido_id
        WHERE fi.pp_id = :pp_id
        ORDER BY fi.id
    """, {"pp_id": pp_id})

    if df_fi is None or df_fi.empty:
        st.info("No hay facturas internas para este PP")
        st.stop()

    # Mostrar tabla de FIs
    st.dataframe(df_fi, use_container_width=True)

    # 4. Análisis de FIs problemáticas
    st.divider()
    st.markdown("### ⚠️ Análisis de Inconsistencias")

    reservadas = df_fi[df_fi['estado'] == 'RESERVADA']

    if reservadas.empty:
        st.success("✅ No hay FIs en estado RESERVADA bloqueando stock")
    else:
        st.warning(f"⚠️ {len(reservadas)} FI(s) en estado RESERVADA bloqueando stock")

        for _, fi_row in reservadas.iterrows():
            with st.expander(f"🔸 {fi_row['nro_factura']} - {fi_row['total_pares']} pares bloqueados", expanded=True):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.write(f"**Estado:** {fi_row['estado']}")
                    st.write(f"**Marca:** {fi_row['marca']}")
                    st.write(f"**Caso:** {fi_row['caso']}")
                    st.write(f"**Pares bloqueados:** {fi_row['total_pares']}")

                    if fi_row['pedido_id']:
                        st.write(f"**Pedido:** {fi_row['nro_pedido']} (Estado: {fi_row['pedido_estado']})")

                        if fi_row['pedido_estado'] == 'RECHAZADO':
                            st.error("❌ PROBLEMA: El pedido fue RECHAZADO pero la FI sigue RESERVADA")
                    else:
                        st.error("❌ PROBLEMA: FI huérfana sin pedido asociado")

                    # Mostrar items de la FI
                    df_items = get_dataframe("""
                        SELECT
                            fid.pares,
                            fid.cajas,
                            fid.linea_snapshot
                        FROM factura_interna_detalle fid
                        WHERE fid.factura_id = :fi_id
                    """, {"fi_id": int(fi_row['fi_id'])})

                    if df_items is not None and not df_items.empty:
                        st.write(f"**Items:** {len(df_items)} artículos")

                with col2:
                    st.markdown("#### 🔧 Acciones")

                    if st.button(f"❌ Anular FI", key=f"anular_{fi_row['fi_id']}", type="primary"):
                        motivo = "Stock bloqueado - pedido rechazado/huérfano"
                        ok, msg = anular_fi(int(fi_row['fi_id']), motivo=motivo)

                        if ok:
                            st.success(f"✅ {msg}")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(f"❌ Error: {msg}")

    # 5. Artículos con stock bloqueado
    st.divider()
    st.markdown("### 📊 Artículos con Stock Bloqueado")

    df_bloqueados = get_dataframe("""
        SELECT
            id as ppd_id,
            linea,
            referencia,
            material_code,
            color_code,
            cantidad_pares as total,
            COALESCE(pares_vendidos, 0) as bloqueados,
            cantidad_pares - COALESCE(pares_vendidos, 0) as disponibles
        FROM pedido_proveedor_detalle
        WHERE pedido_proveedor_id = :pp_id
          AND COALESCE(pares_vendidos, 0) > 0
        ORDER BY pares_vendidos DESC
    """, {"pp_id": pp_id})

    if df_bloqueados is not None and not df_bloqueados.empty:
        st.dataframe(df_bloqueados, use_container_width=True)
        st.caption(f"Total bloqueado: {df_bloqueados['bloqueados'].sum()} pares")
    else:
        st.success("✅ No hay artículos con stock bloqueado")

if __name__ == "__main__":
    st.sidebar.markdown("### 🛠️ Herramienta de Diagnóstico")
    st.sidebar.markdown("""
    Esta herramienta te permite:
    - Ver el estado de stock de un PP
    - Identificar FIs huérfanas bloqueando stock
    - Anular FIs problemáticas directamente
    - Liberar stock bloqueado
    """)
