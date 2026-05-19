"""
Paso 3 — capa de visualización reactiva (Streamlit).
Separada del pipeline de negocio (paso3_pipeline.py).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import streamlit as st

TickFn = Callable[["Paso3Metrics"], None]


@dataclass
class Paso3Metrics:
    fase: str = "inicio"
    subfase: str = ""
    caso_actual: str = ""
    caso_idx: int = 0
    casos_total: int = 0
    skus_caso: int = 0
    skus_preparados: int = 0
    skus_total: int = 0
    omitidos: int = 0
    staging_acum: int = 0
    filas_caso: int = 0
    validos_caso: int = 0
    logs: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"{ts}  {msg}")
        if len(self.logs) > 40:
            self.logs = self.logs[-40:]


class Paso3LivePanel:
    """Contenedores st.empty() — actualización sin spinner global."""

    def __init__(self) -> None:
        st.markdown("#### Motor en ejecución")
        self._heartbeat = st.empty()
        self._fase = st.empty()
        self._metrics = st.empty()
        self._log = st.empty()
        self._t0 = time.perf_counter()

    def tick(self, metrics: Paso3Metrics) -> None:
        elapsed = time.perf_counter() - self._t0
        self._heartbeat.caption(
            f"Canal activo · {elapsed:.1f}s · última fase: **{metrics.fase}**"
        )
        caso_txt = (
            f" · caso **{metrics.caso_actual}** ({metrics.caso_idx}/{metrics.casos_total})"
            if metrics.caso_actual
            else ""
        )
        sub = f" — _{metrics.subfase}_" if metrics.subfase else ""
        self._fase.markdown(f"**{metrics.fase}**{caso_txt}{sub}")

        pct = (
            int(100 * metrics.skus_preparados / metrics.skus_total)
            if metrics.skus_total
            else 0
        )
        self._metrics.markdown(
            f"| Métrica | Valor |\n|---|---|\n"
            f"| SKUs preparados | **{metrics.skus_preparados:,}** / {metrics.skus_total:,} ({pct}%) |\n"
            f"| Staging acumulado | **{metrics.staging_acum:,}** |\n"
            f"| Omitidos (pilares) | **{metrics.omitidos:,}** |\n"
            f"| Último caso (filas) | **{metrics.filas_caso:,}** "
            f"({metrics.validos_caso:,} válidos / {metrics.skus_caso:,} SKUs) |"
        )
        self._log.code("\n".join(metrics.logs[-14:]) or "(esperando eventos…)")


def make_tick(panel: Paso3LivePanel) -> TickFn:
    def _tick(m: Paso3Metrics) -> None:
        panel.tick(m)

    return _tick
