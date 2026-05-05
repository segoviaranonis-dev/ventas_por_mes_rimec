# =============================================================================
# NEXUS - LOGIC v94.5.4 [PREMIUM - TELEMETRY SYNC]
# Ubicación: modules/import_data/logic.py
# Descripción: Mapeo estricto a Supabase y eliminación de ruidos.
#              Sincronizado con la nueva firma de DBInspector (3 argumentos).
# =============================================================================

import pandas as pd
import numpy as np
from sqlalchemy import text
from core.database import DBInspector
import time

# --- [SECCIÓN VENTAS V2] ---
def procesar_ventas_especial_v2(engine, df):
    """Procesamiento con Escudo de Integridad basado en estructura real."""
    if df.empty:
        return 0

    t_start = time.perf_counter()

    try:
        # 1. Saneamiento de Fechas e IDs (Bigint)
        # dayfirst=True para evitar confusiones de formato regional
        df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True).dt.date
        fecha_min = df['fecha'].min()

        # Columnas según tabla Supabase - Blindaje contra caracteres no numéricos
        cols_bigint = ['id_cliente', 'id_marca', 'id_tipo', 'id_vendedor', 'id_categoria']
        for col in cols_bigint:
            if col in df.columns:
                # Limpiamos cualquier carácter que no sea número antes de convertir
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'\D', '', regex=True), errors='coerce')

        # Eliminamos filas que no tengan los IDs vitales (Integridad Referencial)
        df = df.dropna(subset=['id_cliente', 'id_marca', 'id_vendedor'])

        # 2. Escudo Referencial (Anti-3150 / Filtro de Clientes Existentes)
        with engine.connect() as conn:
            valid_ids = pd.read_sql("SELECT id_cliente FROM cliente_v2", conn)['id_cliente'].unique()
        df = df[df['id_cliente'].isin(valid_ids)]

        if df.empty:
            DBInspector.log("Pipeline abortado: No hay clientes válidos tras Escudo Referencial", "AVISO")
            return 0

        # 3. Inserción Atómica
        with engine.begin() as conn:
            # Borrado preventivo para evitar duplicidad en la misma ventana de tiempo
            conn.execute(text("DELETE FROM registro_ventas_general_v2 WHERE fecha >= :f"), {"f": fecha_min})

            # Identificamos columnas a ignorar (SERIAL / Autoincrementales de la DB)
            cols_ignore = ['id_registro', 'id_venta', 'created_at']
            final_cols = [c for c in df.columns if c in [
                'fecha', 'id_cliente', 'id_vendedor', 'id_marca', 'id_tipo',
                'id_categoria', 'id_sucursal', 'cantidad', 'monto'
            ]] # Lista explícita según tu esquema real de Supabase

            # Inyección masiva con chunking para estabilidad
            df[final_cols].to_sql(
                'registro_ventas_general_v2',
                conn,
                if_exists='append',
                index=False,
                method='multi',
                chunksize=1000
            )

            dur = (time.perf_counter() - t_start) * 1000
            # Sincronizado: 3 argumentos (msg, level, duration)
            DBInspector.log(f"Inyectadas {len(df)} ventas (V2) en registro_ventas_general_v2", "SUCCESS", dur)
            return len(df)

    except Exception as e:
        DBInspector.log(f"Fallo Inserción Ventas: {str(e)}", "ERROR")
        raise e

# --- [SECCIÓN MAESTROS - BLINDAJE DE COLUMNAS] ---
def importar_maestro_generico(engine, df, tabla, pk):
    """
    Mapea columnas del Excel a la estructura real de Supabase para evitar errores de INSERT.
    """
    t_start = time.perf_counter()
    if df.empty:
        return 0

    # --- MAPEO INTELIGENTE DE SINÓNIMOS ---
    mapeo_columnas = {
        'cadena_v2': {
            'id_cadena': ['id_cadena', 'ID_CADENA', 'ID CADENA', 'cadena'],
            'descp_cadena': ['descp_cadena', 'DESCRIPCION', 'NOMBRE']
        },
        'cliente_v2': {
            'id_cliente': ['id_cliente', 'ID_CLIENTE'],
            'id_cadena': ['id_cadena', 'ID_CADENA'],
            'razon_social': ['razon_social', 'RAZON SOCIAL']
        }
    }

    if tabla in mapeo_columnas:
        for col_real, sinonimos in mapeo_columnas[tabla].items():
            for s in sinonimos:
                if s in df.columns:
                    df = df.rename(columns={s: col_real})

    # Filtrar solo columnas que no sean basura (como las que crea Excel vacías)
    columnas_validas = [c for c in df.columns if not str(c).startswith('Unnamed')]
    df_limpio = df[columnas_validas].copy()

    if df_limpio.empty:
        DBInspector.log(f"Error: No hay columnas válidas para {tabla}", "ERROR")
        return 0

    # Ejecución del Upsert
    try:
        with engine.begin() as conn:
            # Creamos tabla temporal de tránsito
            df_limpio.to_sql('temp_import_nexus', conn, if_exists='replace', index=False)

            cols_str = ", ".join([f'"{c}"' for c in df_limpio.columns])
            pk_list = [pk] if isinstance(pk, str) else pk
            pk_clause = ", ".join([f'"{p}"' for p in pk_list])

            # ON CONFLICT DO NOTHING para maestros (evita errores de duplicidad)
            query = text(f"""
                INSERT INTO {tabla} ({cols_str})
                SELECT {cols_str} FROM temp_import_nexus
                ON CONFLICT ({pk_clause}) DO NOTHING;
            """)

            conn.execute(query)
            conn.execute(text("DROP TABLE IF EXISTS temp_import_nexus;"))

            dur = (time.perf_counter() - t_start) * 1000
            DBInspector.log(f"Sincronización Maestro {tabla} completada", "SUCCESS", dur)
            return len(df_limpio)

    except Exception as e:
        DBInspector.log(f"Error SQL en Maestro {tabla}: {str(e)}", "ERROR")
        return 0

def reset_ventas_sequence(engine):
    """Sincroniza la secuencia de la base de datos para evitar saltos de ID."""
    t_start = time.perf_counter()
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                SELECT setval('registro_ventas_v2_id_seq',
                COALESCE((SELECT MAX(id_venta) FROM registro_ventas_general_v2), 1));
            """))
        dur = (time.perf_counter() - t_start) * 1000
        DBInspector.log("Secuencia de Ventas sincronizada", "MANTENIMIENTO", dur)
    except Exception as e:
        DBInspector.log(f"No se pudo resetear secuencia: {str(e)}", "AVISO")