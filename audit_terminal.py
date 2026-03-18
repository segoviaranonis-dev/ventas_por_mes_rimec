import pandas as pd
import numpy as np
from core.database import get_dataframe
import sqlalchemy as sa
from core.database import get_engine # Necesitamos el engine para bypass de limpieza

def ejecutar_auditoria_postgresql():
    print("\n" + "="*70)
    print("🏗️  EXTRACCIÓN DE PLANOS: INFRAESTRUCTURA DE LA CIUDAD RIMEC")
    print("="*70)

    # 1. Obtener todas las tablas
    query_tablas = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """

    try:
        # Usamos el engine directamente para evitar que la limpieza de database.py rompa la auditoría
        engine = get_engine()
        with engine.connect() as conn:
            tablas = pd.read_sql(query_tablas, conn)

            if tablas.empty:
                print("❌ No se encontraron tablas.")
                return

            for tabla in tablas['table_name'].tolist():
                print(f"\n[ 📐 TABLA: {tabla.upper()} ]")

                # 2. Consultar Estructura Técnica
                query_columnas = f"""
                    SELECT
                        column_name AS campo,
                        data_type AS tipo,
                        is_nullable AS nulo,
                        character_maximum_length AS largo_max
                    FROM information_schema.columns
                    WHERE table_name = '{tabla}'
                    ORDER BY ordinal_position;
                """
                df_cols = pd.read_sql(query_columnas, conn)
                print(df_cols.to_string(index=False))

                # 3. Muestra de Datos Reales (Casting Visual)
                query_sample = f"SELECT * FROM {tabla} LIMIT 1;"
                df_sample = pd.read_sql(query_sample, conn)

                if not df_sample.empty:
                    print("\n--- Registro de Muestra ---")
                    for col in df_sample.columns:
                        val = df_sample[col].iloc[0]
                        tipo_real = type(val).__name__
                        print(f"{col:25} | Valor: {val} | Tipo: {tipo_real}")
                else:
                    print("\n--- Tabla vacía (Sin datos de muestra) ---")

                print("-" * 70)

    except Exception as e:
        print(f"❌ ERROR EN LA EXTRACCIÓN: {e}")

    print("\n" + "="*70)
    print("✅ PLANOS CARGADOS EN MEMORIA")
    print("="*70 + "\n")

if __name__ == "__main__":
    ejecutar_auditoria_postgresql()