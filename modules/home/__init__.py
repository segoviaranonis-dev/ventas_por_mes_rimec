# =============================================================================
# MÓDULO: Hub Central (Home)
# UBICACIÓN: modules/home/__init__.py
# DESCRIPCIÓN: Declaración del módulo para el Registry NEXUS.
# =============================================================================

from .ui import render_home

MODULE_INFO = {
    "key":          "home",
    "label":        "Hub Central",
    "icon":         "🏠",
    "allowed_roles": ["ADMIN", "USER", "VIEWER", "DIRECTOR", "ROOT"],
    "render_fn":    "modules.home.ui.render_home",
    "needs_engine": False,
    "order":        1,
}

__all__ = ["render_home", "MODULE_INFO"]
