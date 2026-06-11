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
NIVEL_DIOS_ROL_ID = 1
NIVEL_DIOS_CATEGORIA = "DIOS"


def _verificar_password_hash(password: str, password_hash: str) -> tuple[bool, bool]:
    """Retorna (ok, needs_rehash). Soporta hashes legacy con \\n al final."""
    import bcrypt

    pwd = (password or "").strip()
    if not pwd or not password_hash:
        return False, False
    h = password_hash.encode("utf-8") if isinstance(password_hash, str) else password_hash
    if bcrypt.checkpw(pwd.encode("utf-8"), h):
        return True, False
    if bcrypt.checkpw(f"{pwd}\n".encode("utf-8"), h):
        return True, True
    return False, False


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
            print(f"[ALERT] [AUTH-SEC] Bloqueo activado tras {intentos} intentos fallidos.")

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
            print(f"[BLOCKED] [AUTH-SEC] Login bloqueado. Tiempo restante: {segundos}s")
            return "blocked", minutos

        user_clean = str(username_input).strip()
        pass_clean = str(password or "").strip()

        if not user_clean or not pass_clean:
            AuthManager._registrar_fallo()
            return False

        print(f"\n[KEY] [AUTH-MIC] >>> INICIANDO PROTOCOLO DE ACCESO")
        print(f"[SEARCH] [AUTH-MIC] Evaluando analista: '{user_clean}'")

        # SECURITY: Query actualizada para bcrypt (incluye password_hash, rol_id)
        query = """
            SELECT id_usuario, descp_usuario, categoria, password, password_hash, rol_id
            FROM public.usuario_v2
            WHERE LOWER(TRIM(descp_usuario)) = LOWER(TRIM(:usuario))
            LIMIT 1
        """
        params = {"usuario": user_clean}

        try:
            import bcrypt

            # Ejecución via Motor Central
            df = get_dataframe(query, params=params)

            if df is None or df.empty:
                print(f"[WARN] [AUTH-MIC] RECHAZO: Usuario '{user_clean}' no encontrado.")
                AuthManager._registrar_fallo()
                return False

            user_data = df.iloc[0]
            password_hash = user_data.get('password_hash')
            password_plain = user_data.get('password')

            # SECURITY: Verificar con bcrypt si existe hash
            if password_hash:
                ok, needs_rehash = _verificar_password_hash(pass_clean, str(password_hash))
                if not ok:
                    print(f"[WARN] [AUTH-MIC] RECHAZO: Contraseña incorrecta para '{user_clean}'.")
                    AuthManager._registrar_fallo()
                    return False
                if needs_rehash:
                    hash_new = bcrypt.hashpw(pass_clean.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                    from core.database import engine
                    from sqlalchemy import text
                    with engine.begin() as conn:
                        conn.execute(
                            text("UPDATE usuario_v2 SET password_hash = :h WHERE id_usuario = :id"),
                            {"h": hash_new, "id": user_data["id_usuario"]},
                        )
                    print(f"[WARN] [AUTH-MIC] Hash reparado (sin \\n) para '{user_clean}'")
            # FALLBACK temporal: Si no hay hash, verificar contra texto plano
            elif password_plain and str(password_plain).strip() == pass_clean:
                print(f"[WARN] [AUTH-MIC] Usuario '{user_clean}' usando password legacy - actualizando...")
                hash_new = bcrypt.hashpw(pass_clean.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                from core.database import engine
                from sqlalchemy import text
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE usuario_v2 SET password_hash = :h WHERE id_usuario = :id"),
                        {"h": hash_new, "id": user_data["id_usuario"]},
                    )
            else:
                print(f"[WARN] [AUTH-MIC] RECHAZO: Contraseña incorrecta para '{user_clean}'.")
                AuthManager._registrar_fallo()
                return False

            # Extracción de metadata
            user_data = df.iloc[0]
            raw_role = str(user_data["categoria"]).upper().strip()
            rol_id = int(user_data.get("rol_id") or 0)

            # --- MAPEO DE PODER (Sincronización con Aduana) ---
            role_map = {
                "DIRECTOR": "ADMIN",
                "ROOT": "ADMIN",
                "ADMINISTRADOR": "ADMIN",
                "GERENTE": "ADMIN",
            }

            final_role = role_map.get(raw_role, raw_role)
            nivel_dios = rol_id == NIVEL_DIOS_ROL_ID and raw_role == NIVEL_DIOS_CATEGORIA
            bypass = final_role == "ADMIN" or nivel_dios

            # Inyección en el Estado Global (La llave maestra)
            st.session_state.user = {
                "id": user_data["id_usuario"],
                "name": user_data["descp_usuario"],
                "role": final_role,
                "raw_role": raw_role,
                "rol_id": rol_id,
                "nivel_dios": nivel_dios,
                "auth_time": pd.Timestamp.now(),
                "bypass": bypass,
            }

            AuthManager._resetear_intentos()
            tag = "NIVEL-DIOS" if nivel_dios else final_role
            print(f"[OK] [AUTH-MIC] ¡ACCESO CONCEDIDO! Rango: {tag}")
            print(f"[LOCK] [AUTH-MIC] Sesión inyectada para {user_data['descp_usuario']}.")
            return True

        except Exception as e:
            print(f"[ALERT] [AUTH-MIC] FALLO TÉCNICO EN LOGIN: {str(e)}")
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
            return st.session_state.user.get("role", "GUEST")
        return "GUEST"

    @staticmethod
    def is_nivel_dios() -> bool:
        """rol_id=1 + categoria=DIOS — acceso superlativo sin restricciones."""
        if not AuthManager.is_authenticated():
            return False
        u = st.session_state.user
        if u.get("nivel_dios"):
            return True
        raw = str(u.get("raw_role") or u.get("role") or "").upper().strip()
        if raw != NIVEL_DIOS_CATEGORIA:
            return False
        rid = int(u.get("rol_id") or 0)
        # Sesiones legacy sin rol_id: confiar en categoria DIOS
        return rid == 0 or rid == NIVEL_DIOS_ROL_ID

    @staticmethod
    def has_full_access() -> bool:
        """ADMIN legacy, Nivel Dios o DIOS — pase libre a todos los módulos."""
        if not AuthManager.is_authenticated():
            return False
        u = st.session_state.user
        if u.get("bypass") or AuthManager.is_nivel_dios():
            return True
        role = str(u.get("role", "")).upper()
        return role in ("ADMIN", "DIRECTOR", "ROOT", NIVEL_DIOS_CATEGORIA)

    @staticmethod
    def logout():
        """Cierre de sesión con purga selectiva de memoria."""
        if 'user' in st.session_state:
            u_name = st.session_state.user.get('name', 'Desconocido')
            print(f"\n[BYE] [AUTH-MIC] EVACUANDO SISTEMA: Usuario {u_name}")

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