MODULE_INFO = {
    "key":           "compra_web",
    "label":         "Compra Web",
    "icon":          "🛒",
    "allowed_roles": ["ADMIN", "ROOT"],
    "render_fn":     "modules.compra_web.ui.render_compra_web",
    "sidebar_fn":    "modules.compra_web.sidebar.render_sidebar",
    "needs_engine":  False,
    "order":         8,
}

__all__ = ["MODULE_INFO"]
