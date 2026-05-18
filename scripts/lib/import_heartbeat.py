"""
Latido en consola para imports largos (cada N segundos).
Usado por scripts de Excel y por Streamlit (Motor → Admin líneas).
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any


def start_import_heartbeat(
    status_fn: Callable[[], str],
    *,
    interval_sec: float = 60,
) -> tuple[threading.Event, threading.Thread]:
    """
    Arranca un hilo que imprime estado cada ``interval_sec`` segundos.

    Returns:
        (stop_event, thread) — pasar ambos a ``stop_import_heartbeat``.
    """
    stop = threading.Event()
    tick = {"n": 0}

    def _loop() -> None:
        while not stop.wait(timeout=interval_sec):
            tick["n"] += 1
            try:
                msg = status_fn() or ""
            except Exception as exc:  # noqa: BLE001
                msg = f"(error leyendo estado: {exc})"
            ts = datetime.now().strftime("%H:%M:%S")
            print(
                f"[{ts}] … sigo vivo (cada {int(interval_sec)}s, tick {tick['n']}) — {msg}",
                flush=True,
            )

    thread = threading.Thread(target=_loop, name="import-heartbeat", daemon=True)
    thread.start()
    print(f"Latido activo: mensaje cada {int(interval_sec)}s.", flush=True)
    return stop, thread


def stop_import_heartbeat(
    stop_event: threading.Event,
    thread: threading.Thread,
    *,
    timeout: float = 2.0,
) -> None:
    """Detiene el latido y espera brevemente al hilo."""
    stop_event.set()
    thread.join(timeout=timeout)
