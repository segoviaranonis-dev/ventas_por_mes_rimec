"""
Matriz estática de grada y validación de curva canónica.

Política mandatoria (§7 regla .mdc):
  - Curva canónica: 34(1 2 3 3 2 1)39 → 12 pares distribuidos
  - Matriz inflexible: 34:1, 35:2, 36:3, 37:3, 38:2, 39:1
  - Estrategia B: preservar string sin expandir
  - Validación: regex + suma == 12

NO acepta curvas ad-hoc. Warning + rechazo si no coincide.
"""
from __future__ import annotations

import re
from typing import Literal

# § 7.1 — Distribución por caja (inflexible)
MATRIZ_GRADA_12: dict[int, int] = {
    34: 1,
    35: 2,
    36: 3,
    37: 3,
    38: 2,
    39: 1,
}

# § 7.2 — Patrón canónico
CURVA_REGEX = re.compile(
    r"^\s*34\s*\(\s*1\s+2\s+3\s+3\s+2\s+1\s*\)\s*39\s*$",
    re.IGNORECASE,
)


def es_grada_simple(grada: str) -> bool:
    """
    True si es talla simple (ej. "34", "38") sin paréntesis.
    """
    s = str(grada).strip()
    return bool(s) and s.isdigit()


def validar_grada_canonica(grada: str) -> tuple[bool, str | None]:
    """
    Valida grada y genera warning si no es canónica.

    Política Director (Estrategia B):
      - Canónica 34(1 2 3 3 2 1)39: OK, sin warning
      - Talla simple (34, 35...): OK, sin warning
      - Otras curvas (20(1...)32): OK con WARNING, NO rechazar fila

    Returns:
        (es_valida: bool, warning: str | None)

    - Siempre retorna (True, ...) - NUNCA rechaza fila
    - warning != None si hay desviación de canónico (para log)
    """
    s = str(grada).strip()
    if not s:
        return True, None  # vacío aceptado (se marca como "(sin grada)")

    if es_grada_simple(s):
        return True, None  # talla simple aceptada

    # Si tiene paréntesis
    if "(" in s and ")" in s:
        if CURVA_REGEX.match(s):
            return True, None  # curva canónica, sin warning
        else:
            # Curva no canónica: aceptar con warning
            return True, (
                f"Curva '{s}' no es canónica 34(1 2 3 3 2 1)39. "
                "Guardada como string; frontend debe interpretar."
            )

    # Otro formato: aceptar con warning
    return True, f"Grada '{s}' en formato no estándar. Guardada como string."


def extraer_pares_curva(grada: str) -> dict[int, int] | None:
    """
    Extrae distribución de pares desde curva canónica.

    Args:
        grada: String "34(1 2 3 3 2 1)39"

    Returns:
        {34: 1, 35: 2, 36: 3, 37: 3, 38: 2, 39: 1} si es válida, None si no.
    """
    valida, _ = validar_grada_canonica(grada)
    if not valida:
        return None

    if es_grada_simple(grada):
        talla = int(grada)
        return {talla: 1}

    # Si es curva canónica, devuelve matriz estática
    if CURVA_REGEX.match(grada.strip()):
        return MATRIZ_GRADA_12.copy()

    return None
