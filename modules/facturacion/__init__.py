MODULE_INFO = {
    "key":           "facturacion",
    "label":         "Facturación",
    "icon":          "🧾",
    "allowed_roles": ["ADMIN", "ROOT"],
    "render_fn":     "modules.facturacion.ui.render_facturacion",
    "sidebar_fn":    "modules.facturacion.sidebar.render_sidebar",
    "needs_engine":  False,
    "order":         7,
}

__all__ = ["MODULE_INFO"]
