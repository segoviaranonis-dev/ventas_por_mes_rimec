MODULE_INFO = {
    "key":           "compra_legal",
    "label":         "Compra",
    "icon":          "🏭",
    "allowed_roles": ["ADMIN", "ROOT"],
    "render_fn":     "modules.compra_legal.ui.render_compra_legal",
    "sidebar_fn":    "modules.compra_legal.sidebar.render_sidebar",
    "needs_engine":  False,
    "order":         5,
}

__all__ = ["MODULE_INFO"]
