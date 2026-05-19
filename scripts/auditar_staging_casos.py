"""
Auditoría precio_lista_staging vs precio_evento_caso (fallo silencioso Paso 3 SQL).

Uso:
  cd control_central
  .\\venv\\Scripts\\python.exe scripts\\auditar_staging_casos.py --evento 9
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from core.database import engine, get_dataframe


def auditar(evento_id: int) -> int:
    print("=" * 72)
    print(f"AUDITORÍA STAGING — evento_id={evento_id}")
    print("=" * 72)

    ev = get_dataframe(
        "SELECT id, nombre_evento, estado FROM precio_evento WHERE id = :eid",
        {"eid": evento_id},
    )
    if ev is None or ev.empty:
        print(f"ERROR: precio_evento {evento_id} no existe.")
        return 1
    print(f"Evento: {ev.iloc[0]['nombre_evento']} | estado={ev.iloc[0]['estado']}")

    with engine.connect() as conn:
        n_staging = conn.execute(
            text("SELECT COUNT(*) FROM precio_lista_staging WHERE evento_id = :eid"),
            {"eid": evento_id},
        ).scalar()
        n_pl = conn.execute(
            text("SELECT COUNT(*) FROM precio_lista WHERE evento_id = :eid"),
            {"eid": evento_id},
        ).scalar()
        print(f"\nFilas en precio_lista_staging: {n_staging}")
        print(f"Filas en precio_lista (evento):   {n_pl}")

        casos_evento = conn.execute(
            text(
                """SELECT id, nombre_caso FROM precio_evento_caso
                   WHERE evento_id = :eid ORDER BY id"""
            ),
            {"eid": evento_id},
        ).fetchall()
        print(f"\nCasos en precio_evento_caso ({len(casos_evento)}):")
        for cid, nom in casos_evento:
            print(f"  id={cid}  {nom}")

        if not n_staging:
            print(
                "\nStaging vacío. Ejecutá Paso 3 y repetí ANTES de limpiar, "
                "o mirá logs [DEBUG-SQL] en terminal Streamlit."
            )
            return 0

        print("\n--- Staging por caso_id ---")
        rows = conn.execute(
            text(
                """SELECT s.caso_id,
                          COUNT(*) AS n,
                          c.id IS NOT NULL AS caso_existe,
                          c.evento_id AS caso_evento,
                          c.nombre_caso
                   FROM precio_lista_staging s
                   LEFT JOIN precio_evento_caso c ON s.caso_id = c.id
                   WHERE s.evento_id = :eid
                   GROUP BY s.caso_id, c.id, c.evento_id, c.nombre_caso
                   ORDER BY s.caso_id"""
            ),
            {"eid": evento_id},
        ).fetchall()

        invalidos = []
        for caso_id, n, existe, caso_ev, nombre in rows:
            flag = "OK"
            if not existe:
                flag = "INVÁLIDO — no existe en precio_evento_caso"
                invalidos.append(caso_id)
            elif caso_ev is not None and int(caso_ev) != int(evento_id):
                flag = f"OTRO EVENTO (caso en evento {caso_ev})"
                invalidos.append(caso_id)
            print(f"  caso_id={caso_id} n={n} [{flag}] {nombre or ''}")

        join_count = conn.execute(
            text(
                """SELECT COUNT(*) FROM precio_lista_staging s
                   INNER JOIN precio_evento_caso c ON s.caso_id = c.id
                   WHERE s.evento_id = :eid"""
            ),
            {"eid": evento_id},
        ).scalar()
        print(f"\nFilas que pasan INNER JOIN (053b): {join_count}")
        if join_count == 0 and n_staging > 0:
            print(
                "DIAGNÓSTICO: la función SQL insertará 0 filas — "
                "caso_id en staging no coincide con precio_evento_caso."
            )
            return 2
        if invalidos:
            print(f"\n caso_id problemáticos: {invalidos}")
            return 2

        print("\nOK: staging alineado con casos del evento.")
        return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Auditar staging vs precio_evento_caso")
    p.add_argument("--evento", type=int, default=9, help="precio_evento.id (default 9)")
    args = p.parse_args()
    raise SystemExit(auditar(args.evento))


if __name__ == "__main__":
    main()
