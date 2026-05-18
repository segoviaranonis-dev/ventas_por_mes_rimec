"""
Feedback visual para operaciones largas del Motor de Precios (Streamlit).
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Iterator

import streamlit as st

AvanzarFn = Callable[[float, str], None]


def cache_lineas_proveedor(proveedor_id: int) -> list[tuple[str, int]]:
    """Cache en sesión del pilar líneas (evita 1.451 filas en cada rerun)."""
    from modules.rimec_engine.logic import get_lineas_proveedor

    key = f"_cache_lineas_prov_{proveedor_id}"
    if key not in st.session_state:
        st.session_state[key] = get_lineas_proveedor(proveedor_id)
    return st.session_state[key]


def cache_pilar_codigos(proveedor_id: int) -> list[str]:
    from modules.rimec_engine.biblioteca_maestro import cargar_pilar_lineas

    key = f"_cache_pilar_cod_{proveedor_id}"
    if key not in st.session_state:
        st.session_state[key] = cargar_pilar_lineas(proveedor_id)
    return st.session_state[key]


def invalidar_cache_proveedor(proveedor_id: int) -> None:
    st.session_state.pop(f"_cache_lineas_prov_{proveedor_id}", None)
    st.session_state.pop(f"_cache_pilar_cod_{proveedor_id}", None)
    st.session_state.pop(f"_cache_pilar_datos_{proveedor_id}", None)


@contextmanager
def proceso_largo(
    titulo: str,
    detalle: str = "",
    *,
    aviso_espera: str | None = None,
) -> Iterator[AvanzarFn]:
    """
    Panel + barra de progreso mientras corre una operación pesada.

    Uso:
        with proceso_largo("Aplicando biblioteca", "Copiando casos al listado…") as avanzar:
            avanzar(0.1, "Leyendo biblioteca…")
            ...
            avanzar(1.0, "Completado")
    """
    inicio = time.time()
    aviso = aviso_espera or (
        "La base de datos puede tardar **30–60 segundos**. "
        "No cierres ni recargues la pestaña hasta que termine."
    )
    placeholder = st.empty()

    with placeholder.container():
        st.markdown(
            f'<div style="padding:1.1rem 1.25rem;margin:0.5rem 0 1rem 0;'
            f'border:1px solid rgba(212,175,55,0.45);border-radius:14px;'
            f'background:rgba(15,23,42,0.92);">'
            f'<p style="color:#D4AF37;font-weight:700;font-size:1.05rem;margin:0;">'
            f'⏳ {titulo}</p>'
            f'<p style="color:#94a3b8;font-size:0.88rem;margin:0.4rem 0 0.6rem 0;">{detalle}</p>'
            f'<p style="color:#64748b;font-size:0.78rem;margin:0 0 0.85rem 0;">{aviso}</p>'
            "</div>",
            unsafe_allow_html=True,
        )
        bar = st.progress(0.0, text="Iniciando…")
        meta = st.empty()

    def avanzar(pct: float, texto: str = "") -> None:
        p = max(0.0, min(1.0, float(pct)))
        label = texto or f"{int(p * 100)} %"
        bar.progress(p, text=label)
        seg = int(time.time() - inicio)
        meta.caption(f"⏱️ {seg} s transcurridos · {label}")

    try:
        yield avanzar
    finally:
        avanzar(1.0, "Finalizando…")
        time.sleep(0.15)
        placeholder.empty()


def ejecutar_con_progreso(
    titulo: str,
    detalle: str,
    pasos: list[tuple[str, Callable[[], None]]],
) -> None:
    """Ejecuta una lista de (etiqueta, callable) mostrando progreso."""
    n = max(len(pasos), 1)
    with proceso_largo(titulo, detalle) as avanzar:
        for i, (label, fn) in enumerate(pasos):
            avanzar((i + 0.05) / n, label)
            fn()
        avanzar(1.0, "Listo")
