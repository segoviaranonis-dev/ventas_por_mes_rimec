#!/usr/bin/env python3
"""
Arranque formal — Motor de Precios RIMEC (un solo camino).

Uso:
  python scripts/arranque_formal_motor_precios.py              # checklist (solo lectura)
  python scripts/arranque_formal_motor_precios.py --reset      # Fase A: migración 039 equivalente
  python scripts/arranque_formal_motor_precios.py --post-evento  # tras Paso 3 en la app

Requiere: DATABASE_URL o .streamlit/secrets.toml [postgres]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from decouple import UndefinedValueError, config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

PROVEEDOR_ID = 654
LINEA_TEST = 1487
PROMO_LINEAS_ESPERADAS = [
    "60011", "4938", "4945", "5353", "1487", "3113", "2580", "25005", "2864",
]

TABLAS_EVENTO = (
    "precio_auditoria",
    "precio_evento_linea_excepcion",
    "precio_lista",
    "precio_evento_caso",
    "precio_evento",
)


def _db_url() -> str:
    try:
        url = config("DATABASE_URL")
        if url:
            return url
    except UndefinedValueError:
        pass
    p = ROOT / ".streamlit" / "secrets.toml"
    if p.is_file():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        with p.open("rb") as f:
            pg = tomllib.load(f).get("postgres")
        if isinstance(pg, dict):
            user = pg.get("user") or pg.get("username")
            pwd = pg.get("password")
            host = pg.get("host", "localhost")
            port = pg.get("port", 5432)
            db = pg.get("database") or pg.get("dbname")
            if user and pwd and db:
                return (
                    f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(pwd)}"
                    f"@{host}:{port}/{db}"
                )
    raise SystemExit("Definí DATABASE_URL o .streamlit/secrets.toml [postgres]")


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _fail(msg: str) -> None:
    print(f"  [STOP] {msg}")


def _warn(msg: str) -> None:
    print(f"  [AVISO] {msg}")


def _section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def fase_a_conteos(conn) -> dict[str, int]:
    rows = conn.execute(
        text(
            """
            SELECT 'precio_evento' AS tabla, COUNT(*)::int AS n FROM public.precio_evento
            UNION ALL SELECT 'precio_evento_caso', COUNT(*)::int FROM public.precio_evento_caso
            UNION ALL SELECT 'precio_evento_linea_excepcion', COUNT(*)::int
                FROM public.precio_evento_linea_excepcion
            UNION ALL SELECT 'precio_lista', COUNT(*)::int FROM public.precio_lista
            """
        )
    ).mappings().all()
    return {r["tabla"]: int(r["n"]) for r in rows}


def aplicar_reset(engine) -> None:
    _section("FASE A — RESET (equivalente migración 039)")
    with engine.begin() as conn:
        n_ic = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.intencion_compra "
                "WHERE precio_evento_id IS NOT NULL"
            )
        ).scalar()
        n_icp = conn.execute(
            text(
                "SELECT COUNT(*) FROM public.intencion_compra_pedido "
                "WHERE precio_evento_id IS NOT NULL"
            )
        ).scalar()
        print(f"  IC con precio_evento_id:  {n_ic}")
        print(f"  ICP con precio_evento_id: {n_icp}")

        conn.execute(
            text(
                "UPDATE public.intencion_compra SET precio_evento_id = NULL "
                "WHERE precio_evento_id IS NOT NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE public.intencion_compra_pedido SET precio_evento_id = NULL "
                "WHERE precio_evento_id IS NOT NULL"
            )
        )
        tbls = ", ".join(f"public.{t}" for t in TABLAS_EVENTO)
        conn.execute(text(f"TRUNCATE TABLE {tbls} RESTART IDENTITY CASCADE"))
        # Biblioteca: solo DELETE (TRUNCATE CASCADE borraba linea por FK caso_id).
        conn.execute(text("DELETE FROM public.caso_precio_biblioteca"))
        conn.execute(
            text(
                "SELECT setval(pg_get_serial_sequence("
                "'public.caso_precio_biblioteca', 'id'), 1, false)"
            )
        )
        _ok("Eventos vacíos + biblioteca DELETE (pilares NO se tocan)")

    with engine.connect() as conn:
        conteos = fase_a_conteos(conn)
        for t, n in conteos.items():
            print(f"  {t}: {n}")
        bib = conn.execute(
            text("SELECT COUNT(*) FROM public.caso_precio_biblioteca WHERE activo = true")
        ).scalar()
        legacy = conn.execute(
            text("SELECT COUNT(*) FROM public.linea WHERE caso_id IS NOT NULL")
        ).scalar()
        print(f"  caso_precio_biblioteca (activos): {bib}")
        print(f"  linea con caso_id (debe 0):       {legacy}")


def fase_biblioteca_legacy(conn) -> bool:
    _section("FASE B — BIBLIOTECA LEGACY (debe estar vacía)")
    n = conn.execute(
        text("SELECT COUNT(*) FROM public.caso_precio_biblioteca")
    ).scalar()
    if n and int(n) > 0:
        _fail(
            f"caso_precio_biblioteca tiene {n} fila(s). "
            "Ejecutá: python scripts/arranque_formal_motor_precios.py --reset"
        )
        return False
    _ok("Biblioteca vacía — casos se definen en Paso 2 de cada listado")
    _warn(
        f"Línea {LINEA_TEST}: definila en Paso 2 al crear PROMOCIONALES "
        "(líneas específicas), no en biblioteca."
    )
    return True


def fase_linea_pilar(conn) -> bool:
    _section(f"PILAR — línea {LINEA_TEST}")
    row = conn.execute(
        text(
            """
            SELECT id, codigo_proveedor, caso_id, activo
            FROM public.linea
            WHERE proveedor_id = :p AND codigo_proveedor = :c
            """
        ),
        {"p": PROVEEDOR_ID, "c": LINEA_TEST},
    ).mappings().fetchone()

    if not row:
        _warn(
            f"Línea {LINEA_TEST} no está en el pilar (proveedor {PROVEEDOR_ID}). "
            "Si la usás en la matriz, el Excel o el alta en Admin Líneas la creará; "
            "las excepciones por línea requieren que exista antes del Paso 3."
        )
        return True

    print(
        f"  id={row['id']} codigo={row['codigo_proveedor']} "
        f"caso_id={row['caso_id']} activo={row['activo']}"
    )
    if row["caso_id"] is not None:
        _warn("linea.caso_id debería ser NULL (ejecutar 038 si persiste legacy).")
    else:
        _ok("linea.caso_id NULL (arquitectura correcta)")
    return True


def fase_post_evento(conn) -> bool:
    _section("FASE D — POST EVENTO (después de Paso 3 en la app)")
    ev = conn.execute(
        text(
            """
            SELECT id, nombre_evento, estado, created_at
            FROM public.precio_evento
            ORDER BY id DESC
            LIMIT 3
            """
        )
    ).mappings().all()

    if not ev:
        _fail("No hay precio_evento. Completar Motor: Excel → Paso 3 → cerrar.")
        return False

    print("  Últimos eventos:")
    for e in ev:
        print(f"    id={e['id']} | {e['nombre_evento']} | {e['estado']} | {e['created_at']}")

    eid = int(ev[0]["id"])
    exc = conn.execute(
        text(
            """
            SELECT pe.id, pe.nombre_evento, pec.nombre_caso, l.codigo_proveedor
            FROM public.precio_evento_linea_excepcion pele
            JOIN public.linea l ON l.id = pele.linea_id
            JOIN public.precio_evento_caso pec ON pec.id = pele.caso_id
            JOIN public.precio_evento pe ON pe.id = pec.evento_id
            WHERE l.codigo_proveedor = :c
            ORDER BY pe.id DESC
            """
        ),
        {"c": LINEA_TEST},
    ).mappings().all()

    if not exc:
        _fail(
            f"Sin excepción para línea {LINEA_TEST}. "
            "¿Paso 3 ejecutado? ¿Caso con lineas en biblioteca?"
        )
    else:
        for r in exc:
            _ok(
                f"evento {r['id']} ({r['nombre_evento']}) → "
                f"caso «{r['nombre_caso']}» línea {r['codigo_proveedor']}"
            )

    n_skus = conn.execute(
        text(
            """
            SELECT COUNT(*)::int
            FROM public.precio_lista pl
            JOIN public.linea l ON l.id = pl.linea_id
            WHERE pl.evento_id = :e AND l.codigo_proveedor = :c
            """
        ),
        {"e": eid, "c": LINEA_TEST},
    ).scalar()
    print(f"  SKUs precio_lista (evento {eid}, línea {LINEA_TEST}): {n_skus}")
    if n_skus == 0:
        _fail("precio_lista sin SKUs para esa línea en el último evento.")
        return False
    _ok(f"{n_skus} SKUs con precio en evento {eid}")

    n_exc_total = conn.execute(
        text("SELECT COUNT(*) FROM public.precio_evento_linea_excepcion")
    ).scalar()
    print(f"  Total excepciones en BD: {n_exc_total}")
    return bool(exc) and n_skus > 0


class _Tee:
    """Escribe a consola y a archivo de log."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("w", encoding="utf-8")

    def write(self, s: str) -> None:
        sys.__stdout__.write(s)
        self._file.write(s)

    def flush(self) -> None:
        sys.__stdout__.flush()
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Checklist arranque formal Motor de Precios")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Aplicar reset 039 (TRUNCATE eventos + RESTART IDENTITY)",
    )
    parser.add_argument(
        "--post-evento",
        action="store_true",
        help="Validar tras cerrar primer evento (Fase D)",
    )
    args = parser.parse_args()

    log_path = ROOT / "scripts" / "arranque_formal_ultimo.log"
    tee = _Tee(log_path)
    sys.stdout = tee  # type: ignore[assignment]
    print(f"Log: {log_path}")

    engine = create_engine(_db_url())
    bloqueos = 0

    if args.reset:
        aplicar_reset(engine)

    _section("FASE A — TABLERO EN CERO")
    with engine.connect() as conn:
        conteos = fase_a_conteos(conn)
        for t, n in conteos.items():
            mark = "OK" if n == 0 else "STOP"
            print(f"  [{mark}] {t}: {n}")
            if n != 0:
                bloqueos += 1

        if bloqueos:
            _fail("Ejecutar: python scripts/arranque_formal_motor_precios.py --reset")
        else:
            _ok("Tablero en cero — próximo precio_evento.id será 1")

        if not args.post_evento:
            if not fase_linea_pilar(conn):
                bloqueos += 1
            if not fase_biblioteca_legacy(conn):
                bloqueos += 1
        else:
            if not fase_post_evento(conn):
                bloqueos += 1

    _section("VEREDICTO")
    if bloqueos:
        print("  RESULTADO: NO LISTO — corregir ítems [STOP] arriba.")
        print("  Camino: --reset → Motor Paso 0-2 (matriz del listado) → Paso 3-5")
        rc = 1
    elif args.post_evento:
        print("  RESULTADO: APROBADO — primer listado validado.")
        print("  Siguiente: asignar precio_evento_id en Intención de Compra.")
        rc = 0
    else:
        print("  RESULTADO: APROBADO PARA CARGAR PRIMER LISTADO EN LA APP.")
        print("  Siguiente:")
        print("    1. Motor: Excel → Paso 2 (matriz casos + línea 1487) → Paso 3 → cerrar")
        print("    3. python scripts/arranque_formal_motor_precios.py --post-evento")
        rc = 0
    tee.close()
    sys.stdout = sys.__stdout__
    return rc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit as e:
        raise
    except Exception as exc:
        log_path = ROOT / "scripts" / "arranque_formal_ultimo.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"\n[ERROR FATAL] {exc}\n")
        raise
