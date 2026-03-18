# Ubicación: C:\Users\hecto\Documents\Prg_locales\I_R_G\modules\import_data\audit.py
# VERSIÓN: 45.0.0 - Auditoría Profunda de Tipos y Restricciones

import streamlit as st # pyre-ignore
import pandas as pd # pyre-ignore
from core.database import get_dataframe

class DataAuditor:
    """Herramienta de diagnóstico para verificar la estructura real de la DB."""

    @staticmethod
    def get_detailed_schema(table_name):
        """
        Consulta el esquema técnico: columna, tipo de dato y si es identidad.
        Crucial para detectar desajustes entre bigint y text.
        """
        query = """
            SELECT
                column_name AS "Columna",
                data_type AS "Tipo de Dato",
                is_nullable AS "Nulable",
                column_default AS "Default / Identity"
            FROM information_schema.columns
            WHERE table_name = :table
            ORDER BY ordinal_position
        """
        return get_dataframe(query, {"table": table_name})

    @staticmethod
    def get_table_constraints(table_name):
        """Detecta si la tabla tiene Foreign Keys (Líneas de conexión)."""
        query = """
            SELECT
                kcu.column_name AS "Columna",
                rel_tco.table_name AS "Tabla Referenciada"
            FROM information_schema.table_constraints tco
            JOIN information_schema.key_column_usage kcu
              ON tco.constraint_name = kcu.constraint_name
            JOIN information_schema.referential_constraints rco
              ON tco.constraint_name = rco.constraint_name
            JOIN information_schema.table_constraints rel_tco
              ON rco.unique_constraint_name = rel_tco.constraint_name
            WHERE tco.table_name = :table
        """
        return get_dataframe(query, {"table": table_name})

    @staticmethod
    def run_full_audit():
        """Muestra en pantalla el ADN técnico de la base de datos."""
        st.subheader("🕵️ Auditoría Técnica de Estructura")

        # Lista expandida para cubrir el Catálogo y Ventas
        tables = [
            'marca', 'tipo', 'categoria', 'producto',
            'cliente', 'vendedor', 'registro_ventas_general'
        ]

        for table in tables:
            with st.expander(f"📊 Tabla: {table.upper()}", expanded=False):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown("**Estructura de Columnas:**")
                    df_schema = DataAuditor.get_detailed_schema(table)
                    if not df_schema.empty:
                        st.dataframe(df_schema, use_container_width=True, hide_index=True)
                    else:
                        st.warning(f"No se encontró la tabla '{table}' en el esquema público.")

                with col2:
                    st.markdown("**Vínculos (Foreign Keys):**")
                    df_links = DataAuditor.get_table_constraints(table)
                    if not df_links.empty:
                        st.success(f"✅ Conectada a: {', '.join(df_links['Tabla Referenciada'].tolist())}")
                        st.table(df_links)
                    else:
                        st.error("⚠️ Tabla Aislada (Sin Foreign Keys)")

        st.info("💡 Consejo: Si el Tipo de Dato es 'text' y debería ser 'bigint', las conexiones fallarán.")

