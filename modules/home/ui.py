# =============================================================================
# SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
# UBICACIÓN: C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main\modules\home\ui.py
# VERSION: 94.5.2 (TOTAL SYNC - DOCUMENTATION UPDATED)
# AUTOR: Héctor & Gemini AI
# DESCRIPCIÓN: Pantalla de inicio de alta fidelidad.
#              Sincronizado con el Navigator v94.4.0 (Function naming fix).
# =============================================================================

import streamlit as st
import time
from core.database import get_engine, DBInspector
from core.settings import settings
# Se integra card_metric para blindar los KPIs
from core.styles import header_section, StatusFactory, card_metric

def render_home():
    """
    Renderiza la recepción del sistema.
    IMPORTANTE: Se renombra de 'render_home_interface' a 'render_home'
    para cumplir con la llamada del orquestador core/navigation.py
    """

    # 🎙️ MICROFONÍA: Registro de entrada al Command Center
    start_time = time.time()
    DBInspector.log(f"🛰️ {settings.LOG_PREFIX} Accediendo al Command Center", "UI-ORCHESTRATOR")

    # --- 1. EXTRACCIÓN DE IDENTIDAD (ADN CENTRAL) ---
    sys_name = getattr(settings, 'SYSTEM_NAME', 'NEXUS CORE')
    tagline = getattr(settings, 'TAGLINE', 'Business Intelligence System')
    edition = getattr(settings, 'EDITION', 'Standard')
    version = getattr(settings, 'VERSION', '94.5.1')

    # --- 2. CABECERA DINÁMICA (Visual Saneado) ---
    header_section(
        sys_name,
        f"{tagline} | v{version}"
    )

    # --- 3. ORQUESTACIÓN DE ESTADO Y ENLACE ---
    try:
        engine = get_engine()
        latency = (time.time() - start_time) * 1000

        if engine:
            # 🎙️ MICROFONÍA: Salud del Cerebro
            DBInspector.log(f"🧠 Cerebro Central vinculado en {latency:.2f}ms", "SUCCESS")
            StatusFactory.alert("success", f"Enlace con {settings.COMPANY_NAME} activo (Latencia: {latency:.1f}ms).")

            with st.container():
                # --- GUÍA DE OPERACIONES (Texto Blindado por styles.py) ---
                st.markdown(f"""
                ### 🏗️ Estado de la Operación: {edition}
                Hemos consolidado la infraestructura **Titanium-Shield**. Actualmente el sistema opera con **Cifrado de Capa 7** y la dualidad visual **Purity & Flow**.

                **Protocolo de Navegación Nexus:**
                1. **Panel Lateral:** Utilice el elevador para navegar por las divisiones tácticas.
                2. **📥 Data Ingestion:** Procese los archivos antes del cierre de ciclo.
                3. **📊 Sales Intelligence:** Motor de análisis con exportación PDF de alta fidelidad.
                4. **⚙️ Core Diagnosis:** Monitoreo de logs y salud de base de datos.
                """)

                # --- KPIs DE INFRAESTRUCTURA (Saneados con card_metric) ---
                st.divider()
                col1, col2, col3 = st.columns(3)

                with col1:
                    # Sustitución de st.metric por componente blindado
                    card_metric("Módulos Activos", "5", "Saludable")
                    st.write(f"**Sync:** {settings.LOG_PREFIX}")

                with col2:
                    card_metric("Ecosistema", "Quantum-Cloud", f"Node: {edition}")
                    st.write(f"**Engine:** PostgreSQL")

                with col3:
                    card_metric("Seguridad", f"v{version}", "2026 Titanium Active")
                    st.write("**Shield:** Active")

                # --- DETALLES TÉCNICOS ---
                st.divider()
                with st.expander(f"ℹ️ Especificaciones Técnicas de {sys_name}"):
                    st.markdown(f"""
                    **{settings.COMPANY_NAME} Business Intelligence - Nexus Edition**

                    - **Visual:** AgGrid Engine con `UI_CONFIG` centralizado.
                    - **Lógica de Datos:** Variación Blindada con `_safe_variacion`.
                    - **Piano Geometry:** Arquitectura de niveles con bordes dinámicos.
                    - **Agnosticismo:** Desacoplamiento total de strings y estilos.
                    """)
        else:
            DBInspector.log("❌ Fallo de enlace central", "CRITICAL")
            StatusFactory.alert("error", "Fallo crítico: El cerebro central no responde.")
            st.warning("Verifique la conexión con el servidor o el archivo de secretos.")

    except Exception as e:
        # 🎙️ MICROFONÍA: Captura de colapso
        DBInspector.log(f"💥 COLAPSO EN INTERFAZ HOME: {str(e)}", "CRITICAL")
        StatusFactory.alert("error", f"Colapso en la infraestructura: {str(e)}")

        import traceback
        with st.expander("🔍 Caja Negra (Debug Trace)"):
            st.code(traceback.format_exc())

    # 🎙️ MICROFONÍA: Fin de renderizado
    DBInspector.log(f"🏁 UI Home Renderizado completado", "V2-TRACE")