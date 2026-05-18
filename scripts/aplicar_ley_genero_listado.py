"""
Aplica Ley de Género → linea.genero_id desde un precio_evento cerrado.

Uso:
  python scripts/aplicar_ley_genero_listado.py
  python scripts/aplicar_ley_genero_listado.py --evento 1
"""
from __future__ import annotations

import argparse

from core.database import get_dataframe
from modules.rimec_engine.ley_genero import aplicar_ley_genero_desde_evento


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--evento", type=int, default=None, help="precio_evento.id")
    args = p.parse_args()

    eid = args.evento
    if eid is None:
        df = get_dataframe(
            """SELECT id, nombre_evento FROM precio_evento
               WHERE estado = 'cerrado' ORDER BY created_at DESC LIMIT 1"""
        )
        if df is None or df.empty:
            print("No hay listado cerrado.")
            return
        eid = int(df.iloc[0]["id"])
        print(f"Evento: {df.iloc[0]['nombre_evento']} (id={eid})")

    res = aplicar_ley_genero_desde_evento(eid)
    print(f"Líneas actualizadas con genero_id FK: {res.get('lineas', 0)} / {res.get('total', 0)}")
    if res.get("sin_fk"):
        print("Marcas sin FK en genero:", ", ".join(res["sin_fk"]))


if __name__ == "__main__":
    main()
