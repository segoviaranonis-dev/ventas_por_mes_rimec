# =============================================================================
# NEXUS - AUTH MANAGER v3.1 [TITANIUM SHIELD]
# Ubicación: core/auth.py
# Descripción: Motor de Seguridad RBAC sincronizado con usuario_v2.
#              Normalización de rangos para compatibilidad con Aduana Core.
# =============================================================================

import streamlit as st
import pandas as pd
import time
from core.database import get_dataframe

_MAX_INTENTOS  = 5
_BLOQUEO_SEG   = 900   # 15 minutos

class AuthManager:
    """
    Motor de Seguridad RIMEC v3.2: RBAC con Rate-Limiting y Auditoría.
    """

    @staticmethod
    def _check_rate_limit() -> tuple[bool, int]:
        """
        Devuelve (bloqueado, segundos_restantes).
        Usa session_state para persistir el estado por sesión de browser.
        """
        now = time.time()
        bloqueo_hasta = st.session_state.get("_auth_bloqueo_hasta", 0)

        if bloqueo_hasta > now:
            return True, int(bloqueo_hasta - now)
        if bloqueo_hasta > 0 and bloqueo_hasta <= now:
            # Período de bloqueo expiró — resetear
            st.session_state["_auth_intentos"]      = 0
            st.session_state["_auth_bloqueo_hasta"] = 0
        return False, 0

    @staticmethod
    def _registrar_fallo():
        """Incrementa contador de intentos fallidos. Activa bloqueo al llegar al límite."""
        intentos = st.session_state.get("_auth_intentos", 0) + 1
        st.session_state["_auth_intentos"] = intentos
        if intentos >= _MAX_INTENTOS:
            st.session_state["_auth_bloqueo_hasta"] = time.time() + _BLOQUEO_SEG
            print(f"🚨 [AUTH-SEC] Bloqueo activado tras {intentos} intentos fallidos.")

    @staticmethod
    def _resetear_intentos():
        st.session_state["_auth_intentos"]      = 0
        st.session_state["_auth_bloqueo_hasta"] = 0

    @staticmethod
    def login(username_input, password):
        """Valida credenciales en usuario_v2 con mapeo de privilegios y rate limiting."""
        # ── RATE LIMIT ────────────────────────────────────────────────────────
        bloqueado, segundos = AuthManager._check_rate_limit()
        if bloqueado:
            minutos = segundos // 60
            print(f"🚫 [AUTH-SEC] Login bloqueado. Tiempo restante: {segundos}s")
            return "blocked", minutos

        user_clean = str(username_input).strip()

        print(f"\n🔑 [AUTH-MIC] >>> INICIANDO PROTOCOLO DE ACCESO")
        print(f"🔎 [AUTH-MIC] Evaluando analista: '{user_clean}'")

        # QUERY ACTUALIZADA: Apuntando a la estructura real de Supabase (usuario_v2)
        query = """
            SELECT id_usuario, descp_usuario, categoria
            FROM usuario_v2
            WHERE descp_usuario = :usuario
            AND password = :pass
            LIMIT 1
        """
        params = {"usuario": user_clean, "pass": password}

        try:
            # Ejecución via Motor Central
            df = get_dataframe(query, params=params)

            if df is None or df.empty:
                print(f"⚠️ [AUTH-MIC] RECHAZO: Credenciales inválidas para '{user_clean}'.")
                AuthManager._registrar_fallo()
                return False

            # Extracción de metadata
            user_data = df.iloc[0]
            raw_role = str(user_data['categoria']).upper().strip()

            # --- MAPEO DE PODER (Sincronización con Aduana) ---
            role_map = {
                "DIRECTOR": "ADMIN",
                "ROOT": "ADMIN",
                "ADMINISTRADOR": "ADMIN",
                "GERENTE": "ADMIN"
            }

            final_role = role_map.get(raw_role, raw_role)

            # Inyección en el Estado Global (La llave maestra)
            st.session_state.user = {
                "id": user_data['id_usuario'],
                "name": user_data['descp_usuario'],
                "role": final_role,
                "raw_role": raw_role,
                "auth_time": pd.Timestamp.now(),
                "bypass": True if final_role == "ADMIN" else False
            }

            AuthManager._resetear_intentos()
            print(f"✅ [AUTH-MIC] ¡ACCESO CONCEDIDO! Rango: {final_role}")
            print(f"🔐 [AUTH-MIC] Sesión inyectada para {user_data['descp_usuario']}.")
            return True

        except Exception as e:
            print(f"🚨 [AUTH-MIC] FALLO TÉCNICO EN LOGIN: {str(e)}")
            AuthManager._registrar_fallo()
            return False

    @staticmethod
    def is_authenticated():
        """Micrófono de estado de sesión."""
        return 'user' in st.session_state

    @staticmethod
    def get_role():
        """Devuelve el rol normalizado activo o GUEST si no hay sesión."""
        if AuthManager.is_authenticated():
            return st.session_state.user.get('role', 'GUEST')
        return 'GUEST'

    @staticmethod
    def logout():
        """Cierre de sesión con purga selectiva de memoria."""
        if 'user' in st.session_state:
            u_name = st.session_state.user.get('name', 'Desconocido')
            print(f"\n👋 [AUTH-MIC] EVACUANDO SISTEMA: Usuario {u_name}")

            # Limpiamos datos del usuario, pero NO el engine de la DB
            keys_to_clear = [
                'user', 'raw_universe', 'sales_package',
                'initialized', 'filters', 'filter_draft',
                'piso_actual'
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]

            # Módulo Balance tiendas: índice de imágenes locales (solo sesión)
            for key in list(st.session_state.keys()):
                if isinstance(key, str) and key.startswith("retail_"):
                    del st.session_state[key]

            st.rerun()