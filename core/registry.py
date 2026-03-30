# =============================================================================
# SISTEMA: RIMEC Business Intelligence - NEXUS CORE
# UBICACIÓN: core/registry.py
# VERSION: 1.0.0
# DESCRIPCIÓN: Registro Central de Módulos.
#              Punto único donde todos los módulos se declaran.
#              El Navigator y el Centinela de Seguridad leen de aquí.
#
#              PARA AGREGAR UN NUEVO MÓDULO:
#              1. Crear modules/nuevo_modulo/__init__.py con MODULE_INFO
#              2. Agregar UNA línea aquí: _register("modules.nuevo_modulo")
#              ¡Eso es todo! Navigator y RBAC se actualizan automáticamente.
# =============================================================================

import importlib
from core.base_module import BaseModule

# ─────────────────────────────────────────────────────────────────────────────
# TABLA DE MÓDULOS REGISTRADOS
# ─────────────────────────────────────────────────────────────────────────────
_registry: dict[str, dict] = {}


def _register(module_package: str) -> None:
    """
    Lee el MODULE_INFO de un paquete de módulo y lo agrega al registro.
    Lanza ValueError si el MODULE_INFO es inválido (campo faltante).
    """
    try:
        pkg = importlib.import_module(module_package)
        info = getattr(pkg, "MODULE_INFO", None)
        if info is None:
            raise AttributeError(
                f"El paquete '{module_package}' no tiene MODULE_INFO definido en su __init__.py"
            )
        BaseModule.validate(info)
        _registry[info["key"]] = info
    except Exception as e:
        # Log sin romper el arranque — el módulo aparece como inaccesible
        print(f"⚠️  [REGISTRY] No se pudo registrar '{module_package}': {e}")


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRO DE MÓDULOS ACTIVOS
# Para agregar el módulo 47: una sola línea aquí.
# ─────────────────────────────────────────────────────────────────────────────
_register("modules.home")
_register("modules.sales_report")
_register("modules.import_data")
_register("modules.system_status")


# ─────────────────────────────────────────────────────────────────────────────
# API PÚBLICA DEL REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

def get_all() -> list[dict]:
    """Retorna todos los módulos registrados, ordenados por 'order'."""
    return sorted(_registry.values(), key=lambda m: m.get("order", 99))


def get(key: str) -> dict | None:
    """Retorna el MODULE_INFO de un módulo por su key."""
    return _registry.get(key)


def get_nav_options(user_role: str) -> dict[str, str]:
    """
    Retorna el menú de navegación filtrado por rol.
    Formato: {"📊 Inteligencia de Ventas": "sales", ...}
    El Navigator lo pasa directamente al st.radio().
    """
    opts = {}
    for info in get_all():
        if user_role.upper() in [r.upper() for r in info.get("allowed_roles", [])]:
            label = f"{info['icon']} {info['label']}"
            opts[label] = info["key"]
    return opts


def get_allowed_roles(key: str) -> list[str]:
    """
    Retorna los roles permitidos para un módulo.
    El Centinela de Seguridad (aduana_de_seguridad) usa esto.
    """
    info = _registry.get(key)
    if not info:
        return ["ADMIN"]  # Módulo desconocido: acceso mínimo
    return info.get("allowed_roles", ["ADMIN"])


def render(key: str, **kwargs) -> None:
    """
    Enruta la ejecución al render_fn del módulo indicado.
    Importa dinámicamente para aislar errores entre módulos.
    """
    info = _registry.get(key)
    if not info:
        import streamlit as st
        st.error(f"🚨 Módulo '{key}' no encontrado en el Registro NEXUS.")
        return

    render_path = info.get("render_fn", "")
    needs_engine = info.get("needs_engine", False)

    try:
        module_path, fn_name = render_path.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        fn = getattr(mod, fn_name)

        if needs_engine:
            from core.database import engine
            fn(engine, **kwargs)
        else:
            fn(**kwargs)

    except Exception as e:
        import streamlit as st
        import traceback
        st.error(f"🚨 Error al renderizar módulo '{key}': {e}")
        with st.expander("Detalle técnico"):
            st.code(traceback.format_exc())
