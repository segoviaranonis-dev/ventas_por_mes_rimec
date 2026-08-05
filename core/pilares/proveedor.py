"""Mapeo tipo_v2 → proveedor_importacion.id (triplete catálogo)."""

from __future__ import annotations

PROVEEDOR_ID_CALZADO = 654
PROVEEDOR_ID_CONFECCIONES = 638

TIPO_V2_CALZADO = 1
TIPO_V2_CONFECCIONES = 2


def proveedor_id_from_tipo_v2(tipo_v2_id: int) -> int:
    if int(tipo_v2_id) == TIPO_V2_CONFECCIONES:
        return PROVEEDOR_ID_CONFECCIONES
    return PROVEEDOR_ID_CALZADO
