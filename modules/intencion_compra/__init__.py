# =============================================================================
# MÓDULO: Intención de Compra
# UBICACIÓN: modules/intencion_compra/__init__.py
# DESCRIPCIÓN: Registro de cabecera financiera de intenciones de compra.
#              Alta gerencia: define cuotas por marca y valida límite de crédito.
#              NO contiene datos de producto (material, color, línea, referencia).
#              Precede al módulo de Pedido Proveedor en el ciclo de abastecimiento.
# =============================================================================

from .ui import render_intencion_compra

MODULE_INFO = {
    "key":           "intencion_compra",
    "label":         "Intención de Compra",
    "icon":          "📋",
    "allowed_roles": ["ADMIN", "ROOT"],
    "render_fn":     "modules.intencion_compra.ui.render_intencion_compra",
    "sidebar_fn":    "modules.intencion_compra.sidebar.render_sidebar",
    "needs_engine":  False,
    "order":         3,
}

__all__ = ["render_intencion_compra", "MODULE_INFO"]
