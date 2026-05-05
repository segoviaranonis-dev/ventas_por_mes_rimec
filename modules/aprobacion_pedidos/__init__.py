MODULE_INFO = {
    "key":         "aprobacion_pedidos",
    "label":       "Aprobación de Pedidos",
    "icon":        "✅",
    "description": "Pedidos RIMEC mayorista — verificar, dividir por PP+Marca+Caso y autorizar.",
    "order":       4.5,
    "render_fn":   "modules.aprobacion_pedidos.ui.render_aprobacion",
    "allowed_roles": ["ADMIN", "ROOT", "DIRECTOR"],
}
