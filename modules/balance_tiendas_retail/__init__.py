# =============================================================================
# MÓDULO: Retail — importación Excel (staging Supabase)
# =============================================================================

MODULE_INFO = {
    "key":            "balance_tiendas",
    "label":          "Retail (st+vt+RC)",
    "icon":           "🏪",
    "allowed_roles":  ["ADMIN", "USER", "DIRECTOR", "ROOT"],
    "render_fn":      "modules.balance_tiendas_retail.ui.render_balance_tiendas_retail",
    "needs_engine":   True,
    "order":          2.1,
}


def render_balance_tiendas_retail(engine, **kwargs):
    from .ui import render_balance_tiendas_retail as _render
    return _render(engine, **kwargs)


__all__ = ["render_balance_tiendas_retail", "MODULE_INFO"]
