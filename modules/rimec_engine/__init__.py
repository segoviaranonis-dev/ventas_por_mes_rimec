MODULE_INFO = {
    "key":           "rimec_engine",
    "label":         "Motor de Precios",
    "icon":          "⚙️",
    "allowed_roles": ["ADMIN", "DIRECTOR", "ROOT"],
    "render_fn":     "modules.rimec_engine.ui.render_rimec_engine",
    "needs_engine":  False,
    "order":         13,
}

__all__ = ["MODULE_INFO"]
