# =============================================================================
# MÓDULO: Diagnóstico de Red
# UBICACIÓN: modules/system_status/__init__.py
# DESCRIPCIÓN: Declaración del módulo para el Registry NEXUS.
# =============================================================================

MODULE_INFO = {
    "key":          "diagnostics",
    "label":        "Diagnóstico de Red",
    "icon":         "⚙️",
    "allowed_roles": ["ADMIN", "ROOT"],
    "render_fn":    "modules.system_status.ui.render_system_status",
    "needs_engine": False,
    "order":        11,
}

__all__ = ["MODULE_INFO"]
