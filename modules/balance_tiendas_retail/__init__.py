# =============================================================================
# MÓDULO: Retail — importación Excel (staging Supabase)
# UBICACIÓN: modules/balance_tiendas_retail/__init__.py
# DESCRIPCIÓN: Excel VTA SM hoja st+vt+RC → registro_st_vt_rc_reposicion; pilares para filtros/imágenes.
# =============================================================================

from .ui import render_balance_tiendas_retail

MODULE_INFO = {
    "key":            "balance_tiendas",
    "label":          "Retail (st+vt+RC)",
    "icon":           "🏪",
    "allowed_roles":  ["ADMIN", "USER", "DIRECTOR", "ROOT"],
    "render_fn":      "modules.balance_tiendas_retail.ui.render_balance_tiendas_retail",
    "needs_engine":   True,
    "order":          2.1,
}

__all__ = ["render_balance_tiendas_retail", "MODULE_INFO"]
