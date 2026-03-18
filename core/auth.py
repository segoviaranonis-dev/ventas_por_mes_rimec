# =============================================================================
# NEXUS - AUTH MANAGER v3.1 [TITANIUM SHIELD]
# Ubicación: core/auth.py
# Descripción: Motor de Seguridad RBAC sincronizado con usuario_v2.
#              Normalización de rangos para compatibilidad con Aduana Core.
# =============================================================================

import streamlit as st
import pandas as pd
from core.database import get_dataframe

class AuthManager:
    """
    Motor de Seguridad RIMEC v3.1: RBAC con Auditoría de Terminal Activa.
    Optimizado para validación relámpago y compatibilidad con el esquema v2.
    """

    @staticmethod
    def login(username_input, password):
        """Valida credenciales en usuario_v2 con mapeo de privilegios."""
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
                return False

            # Extracción de metadata
            user_data = df.iloc[0]
            raw_role = str(user_data['categoria']).upper().strip()

            # --- MAPEO DE PODER (Sincronización con Aduana) ---
            # Si el rol en DB es DIRECTOR o ROOT, lo normalizamos a ADMIN
            # para que el main.py no bloquee el acceso a los sectores críticos.
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
                "raw_role": raw_role, # Guardamos el original por auditoría
                "auth_time": pd.Timestamp.now(),
                "bypass": True if final_role == "ADMIN" else False
            }

            print(f"✅ [AUTH-MIC] ¡ACCESO CONCEDIDO! Rango: {final_role}")
            print(f"🔐 [AUTH-MIC] Sesión inyectada para {user_data['descp_usuario']}.")
            return True

        except Exception as e:
            print(f"🚨 [AUTH-MIC] FALLO TÉCNICO EN LOGIN: {str(e)}")
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

            st.rerun()