MODULE_INFO = {
    "key":           "deposito_web",
    "label":         "Depósito Web",
    "icon":          "🌐",
    "allowed_roles": ["ADMIN", "ROOT"],
    "render_fn":     "modules.deposito_web.ui.render_deposito_web",
    "needs_engine":  False,
    "order":         9,
}

__all__ = ["MODULE_INFO"]
