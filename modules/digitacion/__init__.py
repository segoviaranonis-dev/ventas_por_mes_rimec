from .ui import render_digitacion

MODULE_INFO = {
    "key":           "digitacion",
    "label":         "Digitación",
    "icon":          "⌨️",
    "allowed_roles": ["ADMIN", "ROOT", "DIRECTOR"],
    "render_fn":     "modules.digitacion.ui.render_digitacion",
    "sidebar_fn":    None,
    "needs_engine":  False,
    "order":         4,
}

__all__ = ["render_digitacion", "MODULE_INFO"]
