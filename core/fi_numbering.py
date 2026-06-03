"""
core/fi_numbering.py - Numeración unificada de FI

SISTEMA HÍBRIDO (Claude + MAMACHA):
- Columna física: pv_global (robusta, auditable, inmutable)
- Vista compatible: v_factura_interna_preventa.numero_preventa_global
- Funciones helper: Lee primero de pv_global, fallback a otros campos
"""


def fi_numero_visible(fi: dict) -> str:
    """Número visible: global si existe, legacy como fallback."""
    pv_global = fi.get("pv_global")
    if pv_global:
        return f"PV{pv_global:06d}"
    
    return (
        fi.get("numero_preventa_global")
        or fi.get("nro_preventa")
        or fi.get("nro_factura")
        or "—"
    )


def fi_numero_legacy(fi: dict) -> str:
    """Número histórico usado por documentos_ref/traspasos."""
    return (
        fi.get("nro_factura_legacy")
        or fi.get("nro_factura")
        or "—"
    )
