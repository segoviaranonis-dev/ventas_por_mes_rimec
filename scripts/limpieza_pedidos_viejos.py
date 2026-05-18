"""
Limpieza QUIRÚRGICA de pedidos viejos en `pedido_venta_rimec`.

Borra pedidos específicos (por número o por fecha de corte) revirtiendo su
impacto en el sistema. NO toca catálogos ni reinicia secuencias.

Por cada pedido a borrar hace:
  1. Identifica las FIs asociadas (vía `pedido_id` si existe; fallback por
     ventana de timestamp ±10s en `created_at`).
  2. Por cada FI: revierte el stock usando la función BD `revertir_stock_fi`
     si existe; si no, hace el UPDATE manual `pares_vendidos -= pares`.
  3. Borra `factura_interna_detalle`, luego `factura_interna`.
  4. Borra `pedido_venta_rimec`.
  5. Todo en una sola transacción atómica por pedido.

Uso:
    # PREVIEW (siempre primero)
    python scripts/limpieza_pedidos_viejos.py --dry-run \
        --nros PVR-2026-868197,PVR-2026-449523,PVR-2026-162435,PVR-2026-908669

    # EJECUCIÓN
    python scripts/limpieza_pedidos_viejos.py \
        --nros PVR-2026-868197,PVR-2026-449523,PVR-2026-162435,PVR-2026-908669

    # Por fecha (todos los pedidos creados ANTES del cutoff, ej. limpia historia previa)
    python scripts/limpieza_pedidos_viejos.py --before 2026-05-08 --dry-run

    # Mantener específicos (en caso de --before)
    python scripts/limpieza_pedidos_viejos.py --before 2026-05-08 \
        --keep PVR-2026-086029
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from urllib.parse import quote_plus

from sqlalchemy import create_engine, text as sqlt

try:
    from core.database import engine as _engine_streamlit, get_dataframe
except Exception:
    _engine_streamlit = None
    get_dataframe = None  # type: ignore


def _db_url() -> str:
    try:
        from decouple import config

        u = config("DATABASE_URL")
        if u:
            return u
    except Exception:
        pass
    p = pathlib.Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"
    if p.is_file():
        import tomllib

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
    raise SystemExit("DATABASE_URL o .streamlit/secrets.toml [postgres]")


def _engine():
    if _engine_streamlit is not None:
        return _engine_streamlit
    return create_engine(_db_url(), pool_pre_ping=True)


def _read_sql(query: str, params: dict | None = None):
    eng = _engine()
    if get_dataframe is not None and _engine_streamlit is not None:
        return get_dataframe(query, params)
    import pandas as pd

    with eng.connect() as conn:
        return pd.read_sql(sqlt(query), conn, params=params or {})


# ─────────────────────────────────────────────────────────────────────────────
# Util presentación
# ─────────────────────────────────────────────────────────────────────────────

def C(code: str, txt: str, *, use: bool = True) -> str:
    return f"\033[{code}m{txt}\033[0m" if use else txt


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def revertir_stock_fi_disponible() -> bool:
    """Devuelve True si la función SQL `revertir_stock_fi` existe en BD."""
    df = _read_sql("""
        SELECT 1 FROM pg_proc WHERE proname = 'revertir_stock_fi' LIMIT 1
    """)
    return df is not None and not df.empty


def fis_de_pedido(pedido_id: int) -> list[dict]:
    """Trae las FIs de un pedido (FK pedido_id + fallback timestamp)."""
    df = _read_sql("""
        SELECT
          fi.id, fi.nro_factura, fi.pp_id, fi.estado,
          fi.marca, fi.caso, fi.total_pares, fi.total_monto,
          fi.created_at
        FROM public.factura_interna fi
        WHERE
              fi.pedido_id = :pid
           OR (
                fi.pedido_id IS NULL
                AND ABS(EXTRACT(EPOCH FROM (
                  fi.created_at -
                  (SELECT created_at FROM public.pedido_venta_rimec WHERE id = :pid)
                ))) < 10
              )
        ORDER BY fi.id
    """, {"pid": pedido_id})
    return df.to_dict("records") if df is not None and not df.empty else []


def detalle_de_fi(fi_id: int) -> list[dict]:
    df = _read_sql("""
        SELECT id, ppd_id, pares
        FROM public.factura_interna_detalle
        WHERE factura_id = :fi
    """, {"fi": fi_id})
    return df.to_dict("records") if df is not None and not df.empty else []


def listar_pedidos_objetivo(args) -> list[dict]:
    """Resuelve la lista final de pedidos a borrar."""
    nros: set[str] = set()
    keep: set[str] = set([x.strip() for x in (args.keep or "").split(",") if x.strip()])

    if args.todos:
        df_all = _read_sql("""
            SELECT nro_pedido FROM public.pedido_venta_rimec ORDER BY id
        """)
        if df_all is not None and not df_all.empty:
            nros.update(df_all["nro_pedido"].astype(str).tolist())

    if args.nros:
        for x in args.nros.split(","):
            if x.strip():
                nros.add(x.strip())

    if args.before:
        try:
            cutoff = datetime.strptime(args.before, "%Y-%m-%d")
        except ValueError:
            raise SystemExit(f"--before inválido: {args.before!r}, use YYYY-MM-DD")
        df = _read_sql("""
            SELECT nro_pedido FROM public.pedido_venta_rimec
            WHERE created_at < :cutoff
            ORDER BY id
        """, {"cutoff": cutoff})
        if df is not None and not df.empty:
            nros.update(df["nro_pedido"].tolist())

    nros -= keep
    if not nros:
        return []

    df = _read_sql("""
        SELECT id, nro_pedido, estado, cliente_id, total_pares, total_monto, created_at
        FROM public.pedido_venta_rimec
        WHERE nro_pedido = ANY(:nros)
        ORDER BY id
    """, {"nros": list(nros)})
    return df.to_dict("records") if df is not None and not df.empty else []


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Limpieza quirúrgica de pedido_venta_rimec.")
    ap.add_argument("--dry-run", action="store_true", help="Solo muestra; no escribe.")
    ap.add_argument("--nros", help="Lista de nros de pedido separados por coma.")
    ap.add_argument("--before", help="Fecha de corte YYYY-MM-DD (borra pedidos anteriores).")
    ap.add_argument("--keep",  help="Nros a EXCLUIR del borrado (separados por coma).")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument(
        "--todos",
        action="store_true",
        help="Borrar TODOS los pedidos en pedido_venta_rimec (pruebas web).",
    )
    ap.add_argument(
        "--yes",
        action="store_true",
        help="Sin confirmación interactiva (para .bat automatizado).",
    )
    args = ap.parse_args()

    use_color = not args.no_color

    if not args.nros and not args.before and not args.todos:
        raise SystemExit("Debe pasar --nros, --before o --todos.")

    print()
    print(C("36;1", "═" * 78, use=use_color))
    print(C("36;1", "  LIMPIEZA QUIRÚRGICA DE pedido_venta_rimec", use=use_color))
    print(C("36;1", "═" * 78, use=use_color))
    print(f"  Modo: {C('33;1', 'DRY-RUN' if args.dry_run else 'EJECUCIÓN', use=use_color)}")
    if args.nros:   print(f"  --nros   : {args.nros}")
    if args.before: print(f"  --before : {args.before}")
    if args.keep:   print(f"  --keep   : {args.keep}")
    print()

    pedidos = listar_pedidos_objetivo(args)
    if not pedidos:
        print(C("32", "  (Sin pedidos que matcheen el filtro)", use=use_color))
        return 0

    print(C("1", f"  {len(pedidos)} pedido(s) marcados para eliminación:", use=use_color))
    print()
    for p in pedidos:
        print(f"    · {p['nro_pedido']}  ·  {p['estado']:<11}  "
              f"·  {p['total_pares']:>5} pares  "
              f"·  Gs. {int(p['total_monto']):,}".replace(",", "."))

    # ── Recolectar plan completo (FIs + detalles a revertir) ───────────────
    total_fis = 0
    total_pares_revertir = 0
    total_detalles = 0
    plan: list[dict] = []
    for p in pedidos:
        fis = fis_de_pedido(int(p["id"]))
        for fi in fis:
            dets = detalle_de_fi(int(fi["id"]))
            total_fis += 1
            total_detalles += len(dets)
            for d in dets:
                total_pares_revertir += int(d.get("pares") or 0)
        plan.append({"pedido": p, "fis": fis})

    print()
    print(C("36", "─" * 78, use=use_color))
    print(C("1", "  RESUMEN DEL IMPACTO", use=use_color))
    print(C("36", "─" * 78, use=use_color))
    print(f"    Pedidos a borrar:                  {len(pedidos):>5}")
    print(f"    Facturas internas a borrar:        {total_fis:>5}")
    print(f"    Detalles de FI a borrar:           {total_detalles:>5}")
    print(f"    Pares a REVERTIR (devolver stock): {total_pares_revertir:>5}")

    if args.dry_run:
        print()
        print(C("33", "  [--dry-run] No se modificó nada. Ejecutar sin --dry-run para aplicar.",
                use=use_color))
        return 0

    if not args.yes:
        print()
        ans = input(C("31;1", "  ¿Confirma la eliminación? (escriba 'SI' para continuar): ",
                      use=use_color))
        if ans.strip().upper() != "SI":
            print(C("31", "  Cancelado por el usuario.", use=use_color))
            return 0

    # ── Ejecutar ───────────────────────────────────────────────────────────
    tiene_rev = revertir_stock_fi_disponible()
    print()
    if tiene_rev:
        print(C("32", "  Función BD revertir_stock_fi() detectada — usándola.", use=use_color))
    else:
        print(C("33", "  Función revertir_stock_fi() no existe; haré el revert manual.",
                use=use_color))
    print()

    errores = 0
    for entry in plan:
        p   = entry["pedido"]
        fis = entry["fis"]
        pid = int(p["id"])
        print(f"  → {p['nro_pedido']} (id={pid}) …", end=" ", flush=True)
        try:
            with _engine().begin() as conn:
                # 1. Revertir stock por FI
                for fi in fis:
                    fi_id = int(fi["id"])
                    if tiene_rev:
                        # Acepta tanto RESERVADA como CONFIRMADA; la función internamente decide.
                        try:
                            conn.execute(sqlt("SELECT revertir_stock_fi(:id)"), {"id": fi_id})
                        except Exception as e_rev:
                            # Si la función no acepta el estado, hacemos revert manual.
                            for d in detalle_de_fi(fi_id):
                                if d.get("ppd_id") and (d.get("pares") or 0) > 0:
                                    conn.execute(sqlt("""
                                        UPDATE public.pedido_proveedor_detalle
                                        SET pares_vendidos = GREATEST(
                                          COALESCE(pares_vendidos, 0) - :pares, 0)
                                        WHERE id = :ppd
                                    """), {"pares": int(d["pares"]), "ppd": int(d["ppd_id"])})
                    else:
                        for d in detalle_de_fi(fi_id):
                            if d.get("ppd_id") and (d.get("pares") or 0) > 0:
                                conn.execute(sqlt("""
                                    UPDATE public.pedido_proveedor_detalle
                                    SET pares_vendidos = GREATEST(
                                      COALESCE(pares_vendidos, 0) - :pares, 0)
                                    WHERE id = :ppd
                                """), {"pares": int(d["pares"]), "ppd": int(d["ppd_id"])})

                    # 2. Borrar detalle + FI
                    conn.execute(sqlt(
                        "DELETE FROM public.factura_interna_detalle WHERE factura_id = :fi"
                    ), {"fi": fi_id})
                    conn.execute(sqlt(
                        "DELETE FROM public.factura_interna WHERE id = :fi"
                    ), {"fi": fi_id})

                # 3. Borrar pedido
                conn.execute(sqlt(
                    "DELETE FROM public.pedido_venta_rimec WHERE id = :pid"
                ), {"pid": pid})
            print(C("32", "✓ OK", use=use_color))
        except Exception as e:
            errores += 1
            print(C("31", f"✗ ERROR: {e}", use=use_color))

    print()
    print(C("36", "═" * 78, use=use_color))
    if errores == 0:
        print(C("32;1", f"  ✓ Limpieza completa. {len(pedidos)} pedido(s) eliminados.",
                use=use_color))
    else:
        print(C("31;1", f"  ⚠ Hubo {errores} error(es). Revisar arriba.", use=use_color))
    print(C("36", "═" * 78, use=use_color))
    print()
    return 0 if errores == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
