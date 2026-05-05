# =============================================================================
# SISTEMA: RIMEC Business Intelligence - NEXUS CORE
# UBICACIÓN: core/base_module.py
# VERSION: 1.0.0
# DESCRIPCIÓN: Contrato base que todo módulo del sistema debe cumplir.
#              Define la interfaz mínima para que el Registry y el Navigator
#              puedan operar con cualquier módulo sin conocer su implementación.
# =============================================================================


class BaseModule:
    """
    Contrato de Módulo NEXUS.

    Todo módulo del sistema DEBE declarar estos atributos en su __init__.py
    como MODULE_INFO dict. El Registry los lee y el Navigator los enruta.

    Atributos requeridos:
        key          (str)  — Identificador único. Ej: "sales", "inventory"
        label        (str)  — Nombre visible en el menú. Ej: "Inteligencia de Ventas"
        icon         (str)  — Emoji o ícono. Ej: "📊"
        allowed_roles(list) — Roles con acceso. Ej: ["ADMIN", "USER"]
        render_fn    (str)  — Ruta a la función de render. Ej: "modules.sales_report.ui.render_sales_interface"
        order        (int)  — Posición en el menú (menor = más arriba)

    Atributos opcionales:
        needs_engine (bool) — Si render_fn necesita el engine de DB. Default: False
        sidebar_fn   (str)  — Ruta a la función de controles en sidebar. Default: None
    """

    REQUIRED_KEYS = {"key", "label", "icon", "allowed_roles", "render_fn", "order"}

    @classmethod
    def validate(cls, module_info: dict) -> bool:
        """
        Valida que un MODULE_INFO tenga todos los campos obligatorios.
        El Registry llama esto al registrar cada módulo.
        """
        missing = cls.REQUIRED_KEYS - set(module_info.keys())
        if missing:
            raise ValueError(
                f"[REGISTRY] Módulo '{module_info.get('key', '?')}' "
                f"le faltan los campos: {missing}. "
                f"Revisa su __init__.py."
            )
        return True
