MODULE_INFO = {
    "key":           "pedido_web",
    "label":         "Pedidos Web",
    "icon":          "🛒",
    "allowed_roles": ["ADMIN", "ROOT"],
    "render_fn":     "modules.pedido_web.ui.render_pedido_web",
    "sidebar_fn":    "modules.pedido_web.sidebar.render_sidebar",
    "needs_engine":  False,
    "order":         10,
}

__all__ = ["MODULE_INFO"]
