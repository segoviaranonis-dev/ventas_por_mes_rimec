MODULE_INFO = {
    "key":           "web_precio_caso",
    "label":         "Diccionario Web",
    "icon":          "🌐",
    "allowed_roles": ["ADMIN", "DIRECTOR", "ROOT"],
    "render_fn":     "modules.web_precio_caso.ui.render_web_precio_caso",
    "needs_engine":  False,
    "order":         13.5,
}

__all__ = ["MODULE_INFO"]
