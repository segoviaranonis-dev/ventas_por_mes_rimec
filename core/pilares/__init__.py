"""
Motor compartido de pilares — OT-PILARES-LEYES-IMPORTACION-001

Tres fuentes de nutrición (Listado, Proforma, Retail) comparten este motor
para mutar pilares con reglas mandatorias:

- Idempotencia: mismo input → mismo id
- Regla no inversa: nunca vaciar descripción existente
- Herencia jerárquica: línea nueva hereda género/marca/estilo/tipo_1
- Matriz estática grada: validación 34(1 2 3 3 2 1)39

API pública:
    - upsert_linea(), upsert_referencia(), upsert_material(), upsert_color()
    - aplicar_herencia_linea()
    - validar_grada_canonica()
    - MATRIZ_GRADA_12
"""

from .upsert import (
    upsert_linea,
    upsert_referencia,
    upsert_material,
    upsert_color,
)

from .herencia import aplicar_herencia_linea

from .grada import (
    MATRIZ_GRADA_12,
    validar_grada_canonica,
    es_grada_simple,
)

from .enriquecimiento import aplicar_enriquecimiento_no_inverso

__all__ = [
    "upsert_linea",
    "upsert_referencia",
    "upsert_material",
    "upsert_color",
    "aplicar_herencia_linea",
    "MATRIZ_GRADA_12",
    "validar_grada_canonica",
    "es_grada_simple",
    "aplicar_enriquecimiento_no_inverso",
]
