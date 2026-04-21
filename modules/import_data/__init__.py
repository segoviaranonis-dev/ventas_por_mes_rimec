# =============================================================================
# MÓDULO: Motor de Importación
# UBICACIÓN: modules/import_data/__init__.py
# DESCRIPCIÓN: Declaración del módulo para el Registry NEXUS.
# =============================================================================

MODULE_INFO = {
    "key":          "import",
    "label":        "Motor de Importación",
    "icon":         "📥",
    "allowed_roles": ["ADMIN", "DIRECTOR", "ROOT"],
    "render_fn":    "modules.import_data.ui.render_import_interface",
    "needs_engine": True,   # este módulo recibe el engine de DB
    "order":        10,
}

__all__ = ["MODULE_INFO"]
