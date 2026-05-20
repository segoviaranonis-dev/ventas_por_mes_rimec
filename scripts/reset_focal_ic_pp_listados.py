"""
RESET FOCAL — OT-RESET-FOCAL-IC-PP-LISTADOS-001

Alcance ACOTADO:
  Borra:    intencion_compra(+pedido), pedido_proveedor(+detalle, snapshot),
            precio_evento(+caso, lista, excepcion, auditoria)
  Conserva: pilares + biblioteca + diccionario web + Sales Report + Retail
            + factura_interna + compra_legal + traspaso + movimiento + pedido_web

Pre-check: si etapas downstream (FI/CL/traspaso/movimiento/pedido_web) tienen
filas, ABORTAR. Ese caso = OT-511 (reset completo), no este reset focal.

Uso:
  python scripts/reset_focal_ic_pp_listados.py --dry-run
  python scripts/reset_focal_ic_pp_listados.py --execute --confirm RESET-FOCAL-CONFIRMADO
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402

from scripts.backfill_combinacion_desde_ppd import _db_url  # noqa: E402

# ── ALCANCE ───────────────────────────────────────────────────────────────────

# Operativas focales — TRUNCATE
TABLAS_FOCALES = [
    # Intención + Digitación (tabla puente)
    "intencion_compra_pedido",
    "intencion_compra",
    # Pedido proveedor
    "snapshot_costos",
    "pedido_proveedor_detalle",
    "pedido_proveedor",
]

TABLAS_LISTADOS = [
    "precio_auditoria",
    "precio_evento_linea_excepcion",
    "precio_lista",
    "precio_evento_caso",
    "precio_evento",
]

# DEBEN estar en 0 antes del reset focal (si tienen filas → abort y usar OT-511)
TABLAS_DOWNSTREAM_BLOQUEANTES = [
    "factura_interna_detalle",
    "factura_interna",
    "compra_legal_detalle",
    "compra_legal_pedido",
    "compra_legal",
    "traspaso_detalle",
    "traspaso",
    "movimiento_detalle",
    "movimiento",
    "pedido_web_detalle",
    "pedido_web",
    "pedido_venta_rimec",
]

# Conservar (COUNT pre = post obligatorio)
TABLAS_CONSERVAR = [
    # Pilares
    "linea", "referencia", "linea_referencia", "material", "color", "talla",
    # Biblioteca
    "caso_precio_biblioteca", "biblioteca_precio", "biblioteca_caso_linea",
    # Diccionario Web
    "caso_precio_web_regla",
    # Sales Report blindado
    "registro_ventas_general_v2",
    # Retail propio (OT-RETAIL-ST-VT-RC-001)
    "registro_st_vt_rc_reposicion",
    # Maestras
    "marca_v2", "genero", "grupo_estilo_v2", "tipo_v2", "categoria_v2",
    "cliente_v2", "vendedor_v2", "proveedor_importacion",
]

TOKEN = "RESET-FOCAL-CONFIRMADO"


def get_counts(cur, tablas: list[str]) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for t in tablas:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{t}",))
        if not cur.fetchone()[0]:
            out[t] = None
            continue
        try:
            cur.execute(f"SELECT COUNT(*) FROM public.{t}")
            out[t] = int(cur.fetchone()[0])
        except Exception as e:
            print(f"[WARN] count {t}: {e}")
            out[t] = None
    return out


def existing(cur, tablas: list[str]) -> list[str]:
    return [t for t in tablas if get_counts(cur, [t]).get(t) is not None]


def truncar(cur, tablas: list[str], label: str) -> int:
    tab = existing(cur, tablas)
    if not tab:
        print(f"  ({label}) sin tablas existentes")
        return 0
    print(f"  ({label}) TRUNCATE {', '.join(tab)}")
    cur.execute(f"TRUNCATE TABLE {', '.join(tab)} RESTART IDENTITY CASCADE")
    return len(tab)


def desvincular_precio_evento(cur) -> int:
    total = 0
    cur.execute("UPDATE intencion_compra SET precio_evento_id = NULL WHERE precio_evento_id IS NOT NULL")
    total += cur.rowcount
    print(f"  intencion_compra: {cur.rowcount} filas desvinculadas")

    cur.execute("UPDATE intencion_compra_pedido SET precio_evento_id = NULL WHERE precio_evento_id IS NOT NULL")
    total += cur.rowcount
    print(f"  intencion_compra_pedido: {cur.rowcount} filas desvinculadas")

    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='precio_evento'
          AND column_name='biblioteca_precio_id'
    """)
    if cur.fetchone():
        cur.execute("UPDATE precio_evento SET biblioteca_precio_id = NULL WHERE biblioteca_precio_id IS NOT NULL")
        total += cur.rowcount
        print(f"  precio_evento.biblioteca_precio_id: {cur.rowcount} filas desvinculadas")
    else:
        print("  precio_evento.biblioteca_precio_id: columna no existe (OK)")
    return total


def imprimir_seccion(titulo: str, tablas: list[str], counts: dict[str, int | None]) -> None:
    print(f"\n[{titulo}]")
    for t in tablas:
        v = counts.get(t)
        if v is None:
            print(f"  {t}: (no existe)")
        elif v == 0:
            print(f"  {t}: 0")
        else:
            print(f"  {t}: {v}")


def main() -> bool:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", type=str)
    parser.add_argument("--force", action="store_true",
                        help="Permitir reset focal incluso con FI/CL/traspaso/movimiento/pedido_web (riesgo CASCADE)")
    args = parser.parse_args()

    dry_run = args.dry_run or not args.execute
    if args.execute and args.confirm != TOKEN:
        print(f"[ERROR] Confirmación inválida. Usar: --execute --confirm {TOKEN}")
        return False

    db_url = _db_url()
    if not db_url:
        print("[ERROR] DATABASE_URL no configurada (.env / secrets.toml)")
        return False

    print("=" * 78)
    print("OT-RESET-FOCAL-IC-PP-LISTADOS-001")
    print("Borra: IC + Pedido Proveedor + Digitación + Listados de precios")
    print("Conserva: pilares + biblioteca + Sales Report + Retail + downstream")
    print("=" * 78)
    print(f"Modo: {'DRY RUN' if dry_run else 'EXECUTE'}")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    todas = TABLAS_FOCALES + TABLAS_LISTADOS + TABLAS_DOWNSTREAM_BLOQUEANTES + TABLAS_CONSERVAR
    pre = get_counts(cur, todas)

    imprimir_seccion("CONSERVAR (pre)", TABLAS_CONSERVAR, pre)
    imprimir_seccion("A BORRAR — IC + PP + Digitación", TABLAS_FOCALES, pre)
    imprimir_seccion("A BORRAR — Listados de precios", TABLAS_LISTADOS, pre)
    imprimir_seccion("DOWNSTREAM (deben estar en 0)", TABLAS_DOWNSTREAM_BLOQUEANTES, pre)

    bloqueantes = [t for t in TABLAS_DOWNSTREAM_BLOQUEANTES if (pre.get(t) or 0) > 0]
    if bloqueantes:
        print()
        print("[ABORT] Hay etapas downstream con filas:")
        for t in bloqueantes:
            print(f"  - {t}: {pre[t]}")
        print()
        print("Este reset es FOCAL. Para reset completo usar OT-RESET-TRANSACCIONAL-511-001.")
        if not args.force:
            cur.close(); conn.close()
            return False
        print("[WARN] --force activo: continúo igualmente. CASCADE puede afectar downstream.")

    # Validaciones pilares
    for pilar in ["linea", "referencia", "material", "color", "talla"]:
        if (pre.get(pilar) or 0) == 0:
            print(f"[WARN] pilar {pilar} en 0 (¿BD recién creada?)")

    if dry_run:
        print()
        print("=" * 78)
        print("[DRY RUN] Sin cambios. Para ejecutar:")
        print(f"  python scripts/reset_focal_ic_pp_listados.py --execute --confirm {TOKEN}")
        print("=" * 78)
        cur.close(); conn.close()
        return True

    print()
    print("[FASE A] Desvincular FKs precio_evento")
    n_desv = desvincular_precio_evento(cur)

    print("\n[FASE B] TRUNCATE IC + Pedido Proveedor + Digitación")
    n_focal = truncar(cur, TABLAS_FOCALES, "focales")

    print("\n[FASE C] TRUNCATE Listados de precios")
    n_list = truncar(cur, TABLAS_LISTADOS, "listados")

    print("\n[FASE D] POST-SNAPSHOT")
    post = get_counts(cur, todas)

    errores: list[str] = []
    for t in TABLAS_CONSERVAR:
        if pre.get(t) != post.get(t):
            errores.append(f"{t}: pre={pre.get(t)} post={post.get(t)}")
            print(f"  [ERROR] {t}: {pre.get(t)} -> {post.get(t)}")
    for t in TABLAS_FOCALES + TABLAS_LISTADOS:
        v = post.get(t)
        if v is not None and v != 0:
            errores.append(f"{t}: {v} (esperado 0)")
            print(f"  [ERROR] {t}: {v}")

    if errores:
        print("\n[FAIL] ROLLBACK")
        conn.rollback()
        cur.close(); conn.close()
        return False

    conn.commit()
    print("\n[PASS] COMMIT")

    evidencia = {
        "ot_id": "OT-RESET-FOCAL-IC-PP-LISTADOS-001",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "modo": "execute",
        "filas_desvinculadas": n_desv,
        "tablas_focales_truncadas": n_focal,
        "tablas_listados_truncadas": n_list,
        "pre_counts": {k: v for k, v in pre.items()},
        "post_counts": {k: v for k, v in post.items()},
        "checks": [
            {"id": "C1", "desc": "intencion_compra=0", "actual": post.get("intencion_compra")},
            {"id": "C2", "desc": "pedido_proveedor=0", "actual": post.get("pedido_proveedor")},
            {"id": "C3", "desc": "precio_evento=0", "actual": post.get("precio_evento")},
            {"id": "C4", "desc": "linea preservada", "actual": post.get("linea"), "pre": pre.get("linea")},
            {"id": "C5", "desc": "caso_precio_biblioteca preservada",
             "actual": post.get("caso_precio_biblioteca"), "pre": pre.get("caso_precio_biblioteca")},
            {"id": "C6", "desc": "registro_ventas_general_v2 sin cambios",
             "actual": post.get("registro_ventas_general_v2"), "pre": pre.get("registro_ventas_general_v2")},
            {"id": "C7", "desc": "registro_st_vt_rc_reposicion sin cambios",
             "actual": post.get("registro_st_vt_rc_reposicion"),
             "pre": pre.get("registro_st_vt_rc_reposicion")},
        ],
    }
    out_path = ROOT.parent / "ot" / "RESET-FOCAL-IC-PP-LISTADOS-001-EVIDENCIA.json"
    out_path.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nEvidencia: {out_path}")

    cur.close(); conn.close()
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
