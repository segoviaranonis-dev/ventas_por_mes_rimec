# =============================================================================
# NEXUS - UI v94.5.3 [V2 TELEMETRY & STABILITY FIX - OBSIDIAN READY]
# Ubicación: modules/import_data/ui.py
# Descripción: Central de Mando con Auditoría de Latencia y Prevención de Bloqueo.
#              Sincronizado con la nueva firma de DBInspector (msg, level, duration).
# =============================================================================

import streamlit as st
import pandas as pd
from sqlalchemy import text, inspect
import datetime
import time
from core.database import DBInspector

def render_import_interface(engine):
    """
    Despliega la interfaz de carga de datos sincronizada con el motor central.
    """
    # 1. ESTILOS DE INTERFAZ
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            border-radius: 5px;
            height: 3em;
            background-color: #007bff;
            color: white;
            font-weight: bold;
        }
        .stAlert { border-radius: 10px; }
        </style>
        """, unsafe_allow_html=True)

    st.title("🛰️ NEXUS - CENTRAL DE MANDO V2")
    st.caption("Infraestructura Ciudad RIMEC | Telemetría de Latencia Crítica Activa")

    def get_table_columns(tabla):
        """Inspección de esquema en tiempo real."""
        inspector = inspect(engine)
        return [col['name'] for col in inspector.get_columns(tabla)]

    def upsert_grupo_general(df, tabla, pk):
        """Lógica de Upsert Atómica preservada e integrada con telemetría."""
        t_start = time.perf_counter()

        # 1. Saneamiento de Estructura
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df.columns = [c.strip() for c in df.columns]
        db_cols = get_table_columns(tabla)
        valid_cols = [c for c in df.columns if c in db_cols]
        df = df[valid_cols].copy()

        # 2. Sincronización de Tipos V2
        for col in df.columns:
            if (col.startswith('id_') and col != 'id_producto') or col in ['linea', 'cod_material', 'cod_color', 'cant_caja', 'cant_compra', 'cant_venta']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        pk_list = [pk] if isinstance(pk, str) else pk

        # 3. Transacción Atómica con Auditoría
        try:
            with engine.begin() as conn:
                t_sql = time.perf_counter()
                df.to_sql('temp_import_nexus', conn, if_exists='replace', index=False)

                cols_to_update = [c for c in df.columns if c not in pk_list]
                col_names = ", ".join([f'"{c}"' for c in df.columns])
                pk_clause = ", ".join([f'"{p}"' for p in pk_list])

                update_clause = ", ".join([f'"{c}" = EXCLUDED."{c}"' for c in cols_to_update]) if cols_to_update else ""
                conflict_action = f"DO UPDATE SET {update_clause}" if update_clause else "DO NOTHING"

                query = f"INSERT INTO {tabla} ({col_names}) SELECT {col_names} FROM temp_import_nexus ON CONFLICT ({pk_clause}) {conflict_action};"
                conn.execute(text(query))
                conn.execute(text("DROP TABLE IF EXISTS temp_import_nexus;"))

                duracion_sql = (time.perf_counter() - t_sql) * 1000
                DBInspector.log(f"Upsert {tabla} completado en DB", "SUCCESS", duracion_sql)

            total_dur = (time.perf_counter() - t_start) * 1000
            return len(df), total_dur
        except Exception as e:
            DBInspector.log(f"Fallo en Upsert {tabla}: {str(e)}", "ERROR")
            raise e

    # --- MAPEO DE INFRAESTRUCTURA V2 ---
    infra_map = {
        "cadena_v2": "id_cadena", "categoria_v2": "id_categoria", "cliente_v2": "id_cliente",
        "cliente_cadena_v2": ["id_cliente", "id_cadena"], "comision_v2": "id_comision",
        "grupo_v2": "id_grupo", "grupo_estilo_v2": "id_grupo_estilo",
        "listado_de_precio_v2": "id_listado_de_precio", "marca_v2": "id_marca",
        "plazo_v2": "id_plazo", "producto_v2": ["id_producto", "id_proveedor"],
        "proveedor_v2": "id_proveedor", "tipo_v2": "id_tipo", "usuario_v2": "id_usuario",
        "vendedor_v2": "id_vendedor", "vendedor_marca_v2": ["id_vendedor", "id_marca"]
    }

    tabs = st.tabs(["📦 MAESTROS (UPSERT)", "📉 VENTAS (SANEAMIENTO)"])

    with tabs[0]:
        st.header("Sincronización de Tablas Maestras")
        col1, col2 = st.columns([1, 2])
        with col1:
            tabla_op = st.selectbox("Destino", sorted(infra_map.keys()))
            pk_field = infra_map[tabla_op]
        with col2:
            file_gen = st.file_uploader(f"Excel/CSV: {tabla_op}", type=['xlsx', 'csv'])

        if file_gen and st.button(f"🚀 EJECUTAR PIPELINE: {tabla_op.upper()}"):
            try:
                df_gen = pd.read_excel(file_gen) if file_gen.name.endswith('xlsx') else pd.read_csv(file_gen)
                with st.spinner("Sincronizando..."):
                    count, dur = upsert_grupo_general(df_gen, tabla_op, pk_field)
                    st.success(f"✅ {count} registros en {dur:.1f}ms")
                    st.balloons()
            except Exception as e:
                st.error(f"❌ FALLO CRÍTICO: {str(e)}")
                # Corregido: Enviamos el string del error, no el objeto, para evitar conflictos de firma
                DBInspector.log(f"Fallo en Pipeline {tabla_op}: {str(e)}", "ERROR")

    with tabs[1]:
        st.header("Protocolo de Saneamiento Ventas V2")
        file_vta = st.file_uploader("Dataset Registro Ventas V2 (Excel)", type=['xlsx'])

        if file_vta:
            try:
                df_vta = pd.read_excel(file_vta)
                if 'fecha' in df_vta.columns:
                    f_min = pd.to_datetime(df_vta['fecha']).min().date()
                    st.write(f"📅 Fecha de corte detectada: **{f_min}**")

                    if st.button("🔥 INICIAR SANEAMIENTO Y CARGA"):
                        t_v_start = time.perf_counter()
                        try:
                            with st.spinner("Ejecutando protocolo de limpieza..."):
                                df_vta['fecha'] = pd.to_datetime(df_vta['fecha']).dt.date

                                with engine.begin() as conn:
                                    # 1. Borrado Telemetrizado
                                    t_del = time.perf_counter()
                                    conn.execute(text("DELETE FROM registro_ventas_general_v2 WHERE fecha >= :f"), {"f": f_min})
                                    DBInspector.log(f"Limpieza Ventas >= {f_min}", "MANTENIMIENTO", (time.perf_counter()-t_del)*1000)

                                    # 2. Inserción Blindada con Chunking
                                    t_ins = time.perf_counter()
                                    df_vta.to_sql('registro_ventas_general_v2', conn, if_exists='append',
                                                 index=False, method='multi', chunksize=500)
                                    DBInspector.log("Carga de bloques Ventas V2", "SUCCESS", (time.perf_counter()-t_ins)*1000)

                                st.balloons()
                                total_v_dur = (time.perf_counter() - t_v_start) * 1000
                                st.success(f"✅ Saneado desde {f_min}. {len(df_vta)} filas en {total_v_dur:.1f}ms")
                        except Exception as e:
                            DBInspector.log(f"Error Saneamiento Ventas: {str(e)}", "ERROR")
                            st.error(f"❌ ERROR: {str(e)}")
            except Exception as e:
                st.error(f"Error al leer archivo: {str(e)}")

    st.caption(f"NEXUS Pipeline v94.5.3 | {datetime.datetime.now().strftime('%H:%M:%S')}")