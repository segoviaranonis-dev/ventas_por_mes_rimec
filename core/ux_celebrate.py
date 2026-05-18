"""
Feedback positivo en UI Streamlit tras escrituras exitosas en BD.

Usar en: Motor de Precios, Pedido Proveedor, Aprobaciones, importaciones en app.
"""
from __future__ import annotations

import streamlit as st

# Evitar globos en cada micro-guardado; solo hitos importantes.
_HITOS_BALLOONS = frozenset({
    "import_completa",
    "import_excel",
    "evento_cerrado",
    "listado_cerrado",
    "aprobacion",
    "preventa",
    "factura_creada",
    "modulo_handoff",
    "purge_reset",
})


def celebrate_save(
    mensaje: str,
    *,
    contexto: str = "guardado",
    modulo: str | None = None,
    toast: bool = True,
    balloons: bool | None = None,
    emoji: str = "✅",
) -> None:
    """
    Celebración estándar tras persistir en BD con éxito.

    - toast: aviso breve (siempre que toast=True)
    - balloons: globos en hitos grandes (auto si contexto está en _HITOS_BALLOONS)
    """
    pref = f"[{modulo}] " if modulo else ""
    texto = f"{emoji} {pref}{mensaje}".strip()
    if toast:
        try:
            st.toast(texto, icon="🎉")
        except Exception:
            pass
    st.success(texto)
    usar_globos = balloons if balloons is not None else contexto in _HITOS_BALLOONS
    if usar_globos:
        st.balloons()


def celebrate_step(
    paso: str,
    mensaje: str,
    *,
    modulo: str,
    handoff: str | None = None,
) -> None:
    """Paso completado dentro de un flujo (motor, PP, aprobaciones)."""
    ctx = "modulo_handoff" if handoff else "paso"
    if handoff:
        mensaje = f"{mensaje} → {handoff}"
    celebrate_save(
        mensaje,
        contexto=ctx,
        modulo=modulo,
        toast=True,
        balloons=bool(handoff),
    )


def celebrate_import_done(mensaje: str, *, modulo: str = "Import") -> None:
    celebrate_save(
        mensaje,
        contexto="import_completa",
        modulo=modulo,
        toast=True,
        balloons=True,
    )
