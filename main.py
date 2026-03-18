# =============================================================================
# SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
# MODULO: main.py (EL ORQUESTADOR MAESTRO)
# VERSION: 95.0.2 (SECURITY ENFORCED - ROLE SYNC READY)
# UBICACIÓN: main.py
# DESCRIPCIÓN: Punto de entrada único con Barrera de Acceso AuthManager.
#              Garantiza la jerarquía de acceso RBAC sincronizada con usuario_v2.
# =============================================================================

import streamlit as st
import sys
import os
import time
import traceback

# 1. CONFIGURACIÓN DE PÁGINA (Identidad Visual NEXUS CORE)
st.set_page_config(
    page_title="RIMEC | NEXUS CORE",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. IMPORTACIÓN DEL CORAZÓN (Settings)
try:
    from core.settings import settings
except ImportError:
    print("\n🚨 [FATAL] ARCHIVO settings.py NO DETECTADO. EL EDIFICIO COLAPSA.")
    sys.exit(1)

# 🎙️ MICROFONÍA: Banner de inicio en terminal
if hasattr(settings, 'get_terminal_banner'):
    print(settings.get_terminal_banner())
else:
    print(f"\n{'='*60}\n RIMEC • NEXUS CORE v{settings.VERSION}\n{'='*60}\n")

# 3. CONFIGURACIÓN DE RUTAS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 4. IMPORTACIONES CORE (Sincronización de Componentes)
try:
    from core.auth import AuthManager
    from core.styles import apply_ui_theme
    from core.database import DBInspector
    from core.navigation import render_sidebar, render_page_content
    print(f"🧬 {settings.LOG_PREFIX} [CORE-SYNC] Sinapsis de componentes Obsidian completada.")
except ImportError as e:
    print(f"🚨 [FATAL-NEXUS] Error en acoplamiento: {e}")
    st.error(f"Fallo crítico en la estructura del sistema: {e}")
    st.stop()

def aduana_de_seguridad(modulo_key):
    """
    El Centinela de Nexus: Verifica jerarquía de acceso RBAC.
    """
    if not AuthManager.is_authenticated():
        return False

    role = AuthManager.get_role() # Ya viene normalizado por el nuevo AuthManager

    # PRIVILEGIOS TOTALES: ADMIN, DIRECTOR y ROOT tienen pase libre total.
    if role in ["ADMIN", "DIRECTOR", "ROOT"] or st.session_state.user.get('bypass'):
        return True

    # MATRIZ DE PERMISOS PARA OTROS ROLES
    permisos = {
        "home": ["ADMIN", "USER", "VIEWER", "DIRECTOR", "ROOT"],
        "sales": ["ADMIN", "USER", "DIRECTOR", "ROOT"],
        "import": ["ADMIN", "DIRECTOR", "ROOT"],
        "diagnostics": ["ADMIN", "ROOT"]
    }

    permitidos = permisos.get(modulo_key, ["ADMIN"])

    if role in permitidos:
        return True

    print(f"🚫 {settings.LOG_PREFIX} [ADUANA] Acceso Denegado a {st.session_state.user.get('name')} (Rol: {role}) en {modulo_key}")
    return False

def render_login_screen():
    """Pantalla de Acceso Perimetral RIMEC."""
    apply_ui_theme()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🔐 Acceso NEXUS CORE")
        st.caption("Introduce tus credenciales de analista para abrir el túnel de datos.")

        with st.form("login_form"):
            user_input = st.text_input("Usuario", placeholder="Analista...")
            pass_input = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("INICIAR PROTOCOLO DE ACCESO")

            if submit:
                # El login ahora apunta a la tabla usuario_v2
                if AuthManager.login(user_input, pass_input):
                    st.success("Acceso concedido. Sincronizando...")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Credenciales inválidas. Acceso denegado.")

def main():
    """Motor de Orquestación Principal v95.0.2"""
    t_start = time.time()

    # --- [FASE 0: CONTROL DE ACCESO PERIMETRAL] ---
    if not AuthManager.is_authenticated():
        render_login_screen()
        return

    # --- [FASE 1: ADN VISUAL OBSIDIAN] ---
    apply_ui_theme()

    # --- [FASE 2: NAVEGACIÓN (SIDEBAR)] ---
    modulo_key = render_sidebar()

    # --- [FASE 3: RENDERIZADO DE CONTENIDO] ---
    if aduana_de_seguridad(modulo_key):
        try:
            render_page_content(modulo_key)
        except Exception as e:
            err_msg = str(e)
            stack = traceback.format_exc()
            print(f"🚨 {settings.LOG_PREFIX} [EXC-FATAL] Colapso en {modulo_key}: {err_msg}")

            st.error("### ⚠️ Anomalía Detectada en el Sector de Interfaz")
            with st.expander("🔍 Caja Negra (Análisis Técnico)"):
                st.code(stack)

            if st.button("🧹 Purgar Memoria y Reiniciar"):
                AuthManager.logout()
    else:
        st.error(f"🚫 **Acceso Denegado:** Tu rango ({AuthManager.get_role()}) no permite el acceso al sector {modulo_key.upper()}.")

    # --- [FASE 4: LATIDO DEL SISTEMA (HEARTBEAT)] ---
    duracion = time.time() - t_start
    u_name = st.session_state.user['name']
    # Log de terminal con el sector actual
    sys.stdout.write(f"\r💓 {settings.LOG_PREFIX} [HEARTBEAT] {duracion:.4f}s | Sector: {modulo_key.upper()} | Operador: {u_name}")
    sys.stdout.flush()

if __name__ == "__main__":
    main()