def fi_numero_visible(fi: dict) -> str:
    """Numero visible de preventa/FI: global si existe, legacy como fallback."""
    return (
        fi.get("numero_preventa_global")
        or fi.get("nro_preventa")
        or fi.get("nro_factura")
        or "—"
    )


def fi_numero_legacy(fi: dict) -> str:
    """Numero historico usado por documentos_ref/traspasos."""
    return fi.get("nro_factura_legacy") or fi.get("nro_factura") or "—"
