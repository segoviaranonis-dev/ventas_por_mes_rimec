# =============================================================================
# SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
# MODULO: main.py (EL ORQUESTADOR MAESTRO)
# VERSION: 100.3.0 (IRONCORE - MEMORY PURGE & DATA INTEGRITY)
# UBICACIÓN: main.py
# DESCRIPCIÓN: Punto de entrada único con Barrera de Acceso AuthManager.
#                Garantiza la jerarquía de acceso RBAC sincronizada con usuario_v2.
#                v100.3.0: Fase V - Memory Purge. Limpieza de sales_package para
#                evitar persistencia de datos entre contextos de análisis.
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

# Banner de inicio en terminal
try:
    banner = settings.get_terminal_banner() if hasattr(settings, 'get_terminal_banner') else f"\n{'='*60}\n RIMEC v{settings.VERSION}\n{'='*60}\n"
    print(banner.encode('utf-8', errors='replace').decode('cp1252', errors='replace'))
except Exception:
    pass

# 3. CONFIGURACIÓN DE RUTAS (Orquestación de Directorios Tácticos)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(BASE_DIR, "core")
MODULES_DIR = os.path.join(BASE_DIR, "modules")

# Aseguramos que Python reconozca la estructura de carpetas adjunta
for path in [BASE_DIR, CORE_DIR, MODULES_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ─────────────────────────────────────────────────────────────────────────────
# [EDICIÓN QUIRÚRGICA: PURGA DE MEMORIA TÁCTICA]
# ─────────────────────────────────────────────────────────────────────────────
# Este protocolo fuerza al intérprete a olvidar versiones antiguas y limpia
# el estado de la sesión para evitar datos fantasma de ventas.
def _purga_memoria_nexus():
    # Purga de módulos de Python
    modulos_criticos = [
        'modules.sales_report.logic',
        'modules.sales_report.ui'
    ]
    for m in modulos_criticos:
        if m in sys.modules:
            del sys.modules[m]
            print(f"🧹 [PURGE] Memoria liberada para módulo: {m}")

    # EJECUCIÓN QUIRÚRGICA: Limpieza de sales_package en Session State
    if 'sales_package' in st.session_state:
        del st.session_state['sales_package']
        print("🧹 [PURGE] sales_package eliminado para integridad de datos.")

if 'sistema_inicializado' not in st.session_state:
    _purga_memoria_nexus()
    st.session_state.sistema_inicializado = True
# ─────────────────────────────────────────────────────────────────────────────

# 4. IMPORTACIONES CORE (Sincronización de Componentes)
try:
    from core.auth import AuthManager, _MAX_INTENTOS
    from core.styles import apply_ui_theme
    from core.navigation import render_sidebar, render_page_content
    import core.registry as registry  # Registro central de módulos

    print(f"[CORE-SYNC] Sinapsis de componentes Obsidian completada.")
except ImportError as e:
    print(f"🚨 [FATAL-NEXUS] Error en acoplamiento de componentes: {e}")
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

    # MATRIZ DE PERMISOS — leída desde el Registry (no hardcodeada aquí)
    permitidos = registry.get_allowed_roles(modulo_key)

    if role in permitidos:
        return True

    # [IRONCORE-TELEMETRY] Registro asíncrono de intento de acceso no autorizado
    msg_alerta = f"Intento de acceso denegado: {st.session_state.user.get('name')} -> Sector {modulo_key}"
    if hasattr(settings, 'safe_log_async'):
        settings.safe_log_async(msg_alerta, level="WARNING")

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
                resultado = AuthManager.login(user_input, pass_input)
                if resultado == True:
                    st.success("Acceso concedido. Sincronizando...")
                    if hasattr(settings, 'safe_log_async'):
                        settings.safe_log_async(f"Login exitoso: {user_input}")
                    time.sleep(0.5)
                    st.rerun()
                elif isinstance(resultado, tuple) and resultado[0] == "blocked":
                    minutos = resultado[1]
                    st.error(f"🔒 Demasiados intentos fallidos. Intenta nuevamente en {minutos} minuto(s).")
                else:
                    intentos = st.session_state.get("_auth_intentos", 0)
                    restantes = _MAX_INTENTOS - intentos
                    if restantes > 0:
                        st.error(f"Credenciales inválidas. Te quedan {restantes} intento(s).")
                    else:
                        st.error("🔒 Cuenta bloqueada temporalmente. Intenta en 15 minutos.")

def main():
    """Motor de Orquestación Principal v100.3.0"""
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

            if hasattr(settings, 'safe_log_async'):
                settings.safe_log_async(f"CRASH en {modulo_key}: {err_msg}", level="CRITICAL")

            st.error("### ⚠️ Anomalía Detectada en el Sector de Interfaz")
            # Solo ADMIN ve el stack trace — nunca exponerlo a roles bajos
            if st.session_state.get("user", {}).get("role") == "ADMIN":
                with st.expander("🔍 Caja Negra (Análisis Técnico)"):
                    st.code(stack)

            if st.button("🧹 Purgar Memoria y Reiniciar"):
                # Purga manual forzada en caso de colapso
                _purga_memoria_nexus()
                AuthManager.logout()
                st.rerun()
    else:
        st.error(f"🚫 **Acceso Denegado:** Tu rango ({AuthManager.get_role()}) no permite el acceso al sector {modulo_key.upper()}.")

    # --- [FASE 4: LATIDO DEL SISTEMA (HEARTBEAT)] ---
    duracion = time.time() - t_start
    u_name = st.session_state.user['name']

    sys.stdout.write(f"\r[HEARTBEAT] {duracion:.4f}s | Sector: {modulo_key.upper()} | Operador: {u_name}")
    sys.stdout.flush()

if __name__ == "__main__":
    main()

# -----------------------------------------------------------------------------
# [EXECUTION-CONFIRMED] Se han aplicado los cambios de la TABLA DE EJECUCIÓN QUIRÚRGICA sobre el script main.py
# -----------------------------------------------------------------------------