#!/usr/bin/env python3
"""
Vacía solo eventos de precios (listados). NO toca pilares ni biblioteca maestra.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from modules.rimec_engine.logic import purgar_solo_eventos_precio  # noqa: E402


def main() -> None:
    print("Purga segura — solo datos transaccionales de listados de precio")
    print("BORRA: precio_evento, casos, precio_lista, contenedor, auditoria, staging")
    print("CONSERVA: linea, referencia, material, color, biblioteca_precio\n")
    ok, stats = purgar_solo_eventos_precio()
    if not ok:
        print("ERROR:", stats.get("error", "desconocido"))
        sys.exit(1)
    print("OK — listo para Intento 3")
    print(f"  Listados eliminados:     {stats.get('eventos_eliminados', 0)}")
    print(f"  Casos de evento:         {stats.get('casos_evento_eliminados', 0)}")
    print(f"  SKUs en precio_lista:    {stats.get('skus_eliminados', 0)}")
    print(f"  Líneas en contenedor:    {stats.get('lineas_contenedor_eliminadas', 0)}")
    print(f"  Filas staging:           {stats.get('staging_eliminados', 0)}")
    print(f"  Listados restantes:      {stats.get('eventos_restantes', 0)}  (debe ser 0)")
    print(f"  Pilares linea (intactos): {stats.get('linea_pilares', 0):,}")
    print(f"  Pilares referencia:       {stats.get('referencia_pilares', 0):,}")
    print("\nSiguiente: ot/GUIA_INTENTO3_SUPABASE.md")


if __name__ == "__main__":
    main()
