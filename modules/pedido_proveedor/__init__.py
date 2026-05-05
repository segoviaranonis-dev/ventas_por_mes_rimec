# =============================================================================
# MÓDULO: Pedido Proveedor
# UBICACIÓN: modules/pedido_proveedor/__init__.py
# DESCRIPCIÓN: Declaración del módulo para el Registry NEXUS.
#
#  Operado por: Digitación / Administración.
#  Vincula una Intención de Compra a un número de proforma.
#  Procesa el F9 para registrar el detalle de artículos (línea, referencia,
#  material, color, gradación) por primera vez en el ciclo.
#  Valida que los pares cargados no excedan el saldo aprobado en la IC.
#
#  Número de registro: PP-YYYY-XXXX (ej: PP-2026-0001)
# =============================================================================

MODULE_INFO = {
    "key":           "pedido_proveedor",
    "label":         "Pedido Proveedor",
    "icon":          "📦",
    "allowed_roles": ["ADMIN", "ROOT"],
    "render_fn":     "modules.pedido_proveedor.ui.render_pedido_proveedor",
    "sidebar_fn":    "modules.pedido_proveedor.sidebar.render_sidebar",
    "needs_engine":  False,
    "order":         4,
}

__all__ = ["MODULE_INFO"]
