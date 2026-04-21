MODULE_INFO = {
    "key":           "deposito",
    "label":         "Depósito",
    "icon":          "🏗️",
    "allowed_roles": ["ADMIN", "ROOT"],
    "render_fn":     "modules.deposito.ui.render_deposito",
    "needs_engine":  False,
    "order":         6,
}

__all__ = ["MODULE_INFO"]
