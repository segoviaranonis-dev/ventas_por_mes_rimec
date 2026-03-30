# =============================================================================
# MÓDULO: Inteligencia de Ventas
# UBICACIÓN: modules/sales_report/__init__.py
# DESCRIPCIÓN: Declaración del módulo para el Registry NEXUS.
# =============================================================================

MODULE_INFO = {
    "key":          "sales",
    "label":        "Inteligencia de Ventas",
    "icon":         "📊",
    "allowed_roles": ["ADMIN", "USER", "DIRECTOR", "ROOT"],
    "render_fn":    "modules.sales_report.ui.render_sales_interface",
    "needs_engine": False,
    "order":        2,
}

__all__ = ["MODULE_INFO"]
