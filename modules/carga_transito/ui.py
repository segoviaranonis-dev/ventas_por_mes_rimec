# =============================================================================
# MÓDULO: Carga Stock Tránsito
# ARCHIVO: modules/carga_transito/ui.py
# DESCRIPCIÓN: UI para carga masiva de stock en tránsito desde Proforma Beira Rio.
# =============================================================================

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from modules.carga_transito.logic import (
    parse_proforma_beira_rio,
    crear_pp_con_proforma,
    get_pps_en_transito,
    get_detalle_pp,
    get_resumen_5_pilares,
)


def _fmt_gs(n) -> str:
    try:
        return f"Gs. {int(n):,}".replace(",", ".")
    except Exception:
        return "—"


def _fmt_usd(n) -> str:
    try:
        return f"USD {float(n):,.2f}"
    except Exception:
        return "—"


def render_carga_transito():
    st.markdown("## 🚢 Carga Stock en Tránsito")
    st.caption("Importar proforma Beira Rio → PP con 5 Pilares → Listo para reservas")

    tab_cargar, tab_ver = st.tabs(["📥 Cargar Proforma", "📋 Stock en Tránsito"])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB CARGAR PROFORMA
    # ══════════════════════════════════════════════════════════════════════════
    with tab_cargar:
        st.markdown("### Paso 1: Subir Proforma")
        
        uploaded_file = st.file_uploader(
            "Fatura Proforma Beira Rio (Excel)",
            type=["xlsx", "xls"],
            help="Archivo Excel con formato estándar de Fatura Proforma Beira Rio"
        )
        
        if uploaded_file:
            # Parsear proforma
            with st.spinner("Leyendo proforma..."):
                df, total_pares, error = parse_proforma_beira_rio(uploaded_file.read())
            
            if error:
                st.error(f"❌ Error: {error}")
                return
            
            st.success(f"✅ Proforma leída: {len(df)} artículos · {total_pares:,} pares")
            
            # Mostrar preview
            st.markdown("### Paso 2: Verificar datos")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Artículos", f"{len(df):,}")
            col2.metric("Pares", f"{total_pares:,}")
            col3.metric("Marcas", df["brand"].nunique())
            col4.metric("Líneas", df["linea_cod"].nunique())
            
            # Preview de los primeros registros
            with st.expander("👁️ Preview de artículos", expanded=True):
                df_preview = df[[
                    "style_code", "linea_cod", "ref_cod", "brand",
                    "material", "color", "boxes", "pairs", "unit_fob"
                ]].head(20).copy()
                df_preview.columns = [
                    "Style", "Línea", "Ref", "Marca",
                    "Material", "Color", "Cajas", "Pares", "FOB"
                ]
                st.dataframe(df_preview, use_container_width=True, hide_index=True)
            
            # Formulario de carga
            st.markdown("### Paso 3: Configurar PP")
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                proforma_nro = st.text_input(
                    "Número de Proforma",
                    value="",
                    placeholder="Ej: PF-2026-0001"
                )
                
                fecha_eta = st.date_input(
                    "Fecha ETA (llegada estimada)",
                    value=date.today() + timedelta(days=90),
                    min_value=date.today(),
                )
            
            with col_b:
                st.markdown("**Descuentos comerciales (%)**")
                col_d1, col_d2 = st.columns(2)
                col_d3, col_d4 = st.columns(2)
                
                with col_d1:
                    d1 = st.number_input("D1", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                with col_d2:
                    d2 = st.number_input("D2", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                with col_d3:
                    d3 = st.number_input("D3", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                with col_d4:
                    d4 = st.number_input("D4", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
            
            # Resumen antes de cargar
            total_fob = df["amount_fob"].sum()
            st.markdown("---")
            
            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("Total FOB", _fmt_usd(total_fob))
            col_r2.metric("Descuento total", f"{d1 + d2 + d3 + d4:.1f}%")
            col_r3.metric("Fecha ETA", fecha_eta.strftime("%d/%m/%Y"))
            
            # Botón de carga
            st.markdown("---")
            
            if st.button("🚀 CREAR PP Y CARGAR STOCK", type="primary", use_container_width=True):
                if not proforma_nro.strip():
                    st.warning("⚠️ Ingresa el número de proforma")
                    return
                
                with st.spinner("Creando PP y cargando stock..."):
                    detalle = df.to_dict("records")
                    ok, msg, pp_id = crear_pp_con_proforma(
                        proforma=proforma_nro,
                        fecha_eta=fecha_eta,
                        descuento_1=d1,
                        descuento_2=d2,
                        descuento_3=d3,
                        descuento_4=d4,
                        detalle_rows=detalle,
                    )
                
                if ok:
                    st.success(f"✅ {msg}")
                    st.balloons()
                    
                    # Mostrar resumen de 5 Pilares
                    resumen = get_resumen_5_pilares(pp_id)
                    if resumen:
                        st.markdown("### 📊 Resumen 5 Pilares")
                        c1, c2, c3, c4, c5 = st.columns(5)
                        c1.metric("Líneas", resumen["lineas"])
                        c2.metric("Referencias", resumen["referencias"])
                        c3.metric("Materiales", resumen["materiales"])
                        c4.metric("Colores", resumen["colores"])
                        c5.metric("Gradas", resumen["gradas"])
                    
                    st.info(f"🎯 PP {pp_id} listo para recibir reservas. Primera factura: **{pp_id}-PV001**")
                else:
                    st.error(f"❌ {msg}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB VER STOCK EN TRÁNSITO
    # ══════════════════════════════════════════════════════════════════════════
    with tab_ver:
        st.markdown("### PPs en Tránsito")
        
        df_pps = get_pps_en_transito()
        
        if df_pps is None or df_pps.empty:
            st.info("No hay PPs en tránsito actualmente.", icon="🚢")
            return
        
        # Resumen global
        total_pares_transito = int(df_pps["total_pares"].sum())
        total_reservado = int(df_pps["pares_reservados"].sum())
        total_disponible = int(df_pps["saldo_disponible"].sum())
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("PPs en Tránsito", len(df_pps))
        col2.metric("Total Pares", f"{total_pares_transito:,}")
        col3.metric("Reservados", f"{total_reservado:,}")
        col4.metric("Disponible", f"{total_disponible:,}")
        
        st.markdown("---")
        
        # Lista de PPs
        for _, pp in df_pps.iterrows():
            pp_id = int(pp["id"])
            nro_pp = pp["nro_pp"]
            proforma = pp["proforma"] or "—"
            proveedor = pp["proveedor"] or "Beira Rio"
            eta = pp["eta"]
            total = int(pp["total_pares"])
            reservados = int(pp["pares_reservados"])
            disponible = int(pp["saldo_disponible"])
            n_skus = int(pp["n_skus"])
            n_fis = int(pp["n_facturas"])
            
            # Calcular porcentaje de ejecución
            pct = (reservados / total * 100) if total > 0 else 0
            
            with st.expander(
                f"📦 **{nro_pp}** · {proforma} · {total:,} pares · "
                f"**{disponible:,} disponibles** ({100-pct:.0f}%)",
                expanded=False
            ):
                # Métricas
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("ETA", eta.strftime("%d/%m/%Y") if eta else "—")
                c2.metric("SKUs", n_skus)
                c3.metric("Reservados", f"{reservados:,}")
                c4.metric("Disponible", f"{disponible:,}")
                c5.metric("Facturas", n_fis)
                
                # Barra de progreso
                st.progress(pct / 100, text=f"Ejecución: {pct:.1f}%")
                
                # Resumen 5 Pilares
                resumen = get_resumen_5_pilares(pp_id)
                if resumen:
                    st.caption(
                        f"5 Pilares: {resumen['lineas']} líneas · "
                        f"{resumen['referencias']} refs · "
                        f"{resumen['materiales']} materiales · "
                        f"{resumen['colores']} colores · "
                        f"{resumen['gradas']} gradas"
                    )
                
                # Detalle de SKUs (opcional)
                if st.checkbox(f"Ver detalle SKUs", key=f"det_{pp_id}"):
                    df_det = get_detalle_pp(pp_id)
                    if df_det is not None and not df_det.empty:
                        st.dataframe(
                            df_det[[
                                "marca", "linea", "referencia", "material",
                                "color", "cajas", "pares_inicial", "reservados", "saldo"
                            ]],
                            use_container_width=True,
                            hide_index=True
                        )
                
                # Info de próxima factura
                next_fi = f"{pp_id}-PV{n_fis + 1:03d}"
                st.info(f"🎯 Próxima factura disponible: **{next_fi}**")
