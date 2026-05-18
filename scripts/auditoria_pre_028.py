"""
Auditoría PRE-Migración 028 (RPC confirmar_pedido_web con Regla 1).

Verifica TODO lo que la 028 va a tocar / requerir antes de aplicarla:

  1. Estado del pilar `color` (hex_web post-backfill).
  2. Consistencia de la vista `v_stock_rimec` (campos críticos no-null).
  3. Huérfanos: marca_id sin match en marca_v2 / caso_id sin match en caso_precio_biblioteca.
     ⇒ Si > 0, la FK de la 028 va a explotar al primer pedido que toque un huérfano.
  4. Estado actual de la tabla `factura_interna` (¿ya tiene marca_id / caso_id?).
  5. Versión actual del RPC `confirmar_pedido_web` (¿vieja o nueva?).
  6. Inventario operativo: PPs activos, pares disponibles, marcas, casos.

Cada check tiene un verdict: OK / WARN / BUG.

Uso:
    python scripts/auditoria_pre_028.py [--no-color]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pandas as pd
from core.database import get_dataframe


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de presentación (ANSI)
# ─────────────────────────────────────────────────────────────────────────────
class Style:
    use_color = True
    @classmethod
    def disable(cls):
        cls.use_color = False
    @classmethod
    def c(cls, code: str, txt: str) -> str:
        return f"\033[{code}m{txt}\033[0m" if cls.use_color else txt

def bold(txt: str)   -> str: return Style.c("1", txt)
def dim(txt: str)    -> str: return Style.c("2", txt)
def green(txt: str)  -> str: return Style.c("32", txt)
def red(txt: str)    -> str: return Style.c("31", txt)
def yellow(txt: str) -> str: return Style.c("33", txt)
def cyan(txt: str)   -> str: return Style.c("36", txt)
def blue(txt: str)   -> str: return Style.c("34", txt)


def header(n: int, titulo: str) -> None:
    print()
    print(cyan("═" * 78))
    print(cyan(f"  [{n}] {titulo}"))
    print(cyan("═" * 78))


def verdict(estado: str, msg: str) -> None:
    """estado ∈ {OK, WARN, BUG, INFO}"""
    tag = {
        "OK":   green("  ✓ OK  "),
        "WARN": yellow("  ⚠ WARN"),
        "BUG":  red("  ✗ BUG "),
        "INFO": blue("  ℹ INFO"),
    }.get(estado, f"  ? {estado}")
    print(f"{tag}  {msg}")


def tabla(df: pd.DataFrame | None, max_filas: int = 20) -> None:
    if df is None or df.empty:
        print(dim("  (sin datos)"))
        return
    s = df.head(max_filas).to_string(index=False)
    for ln in s.splitlines():
        print(f"  {ln}")
    if len(df) > max_filas:
        print(dim(f"  … {len(df) - max_filas} filas más"))


def run(sql: str, params: dict | None = None) -> pd.DataFrame | None:
    try:
        return get_dataframe(sql, params or {})
    except Exception as e:
        verdict("BUG", f"Query falló: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def check_1_colores() -> None:
    header(1, "PILAR `color` — estado del backfill de hex_web")
    df = run("""
        SELECT
          COUNT(*) FILTER (WHERE activo)                            AS total_activos,
          COUNT(*) FILTER (WHERE activo AND hex_web IS NOT NULL)    AS con_hex,
          COUNT(*) FILTER (WHERE activo AND hex_web IS NULL)        AS sin_hex,
          COUNT(*) FILTER (WHERE activo AND hex_web !~ '^#[0-9a-fA-F]{3,8}$') AS hex_invalido
        FROM public.color
        WHERE proveedor_id = 654
    """)
    if df is None: return
    tabla(df)

    r = df.iloc[0]
    total = int(r["total_activos"])
    con   = int(r["con_hex"])
    sin   = int(r["sin_hex"])
    inv   = int(r["hex_invalido"])

    if total == 0:
        verdict("BUG", "No hay colores activos. ¿Se truncó el pilar?")
        return
    pct = 100 * con / total
    if pct >= 95:
        verdict("OK", f"{con}/{total} colores con hex_web ({pct:.0f}%).")
    elif pct >= 60:
        verdict("WARN", f"Solo {con}/{total} con hex ({pct:.0f}%). Backfill incompleto.")
    else:
        verdict("BUG", f"Solo {con}/{total} con hex ({pct:.0f}%). Backfill falló o no se ejecutó.")
    if inv > 0:
        verdict("BUG", f"{inv} filas con hex_web malformado (debe matchear ^#[0-9a-fA-F]+).")
    if sin > 0:
        verdict("INFO", f"{sin} colores quedaron sin asignar (caen al gris default).")


def check_2_vista_stock() -> None:
    header(2, "VISTA `v_stock_rimec` — campos críticos no-null")
    df = run("""
        SELECT
          COUNT(*)                                                   AS filas,
          COUNT(*) FILTER (WHERE marca_id IS NULL)                   AS sin_marca_id,
          COUNT(*) FILTER (WHERE descp_marca IS NULL OR descp_marca = '—') AS sin_descp_marca,
          COUNT(*) FILTER (WHERE caso_id IS NULL)                    AS sin_caso_id,
          COUNT(*) FILTER (WHERE descp_color IS NULL OR descp_color = '') AS sin_descp_color,
          COUNT(*) FILTER (WHERE color_hex IS NULL)                  AS sin_color_hex,
          COUNT(*) FILTER (WHERE cantidad_cajas <= 0)                AS cajas_vacias
        FROM public.v_stock_rimec
    """)
    if df is None: return
    tabla(df)

    r = df.iloc[0]
    n = int(r["filas"])
    if n == 0:
        verdict("BUG", "La vista está vacía. No hay nada para vender.")
        return
    verdict("INFO", f"{n} filas en la vista.")

    if int(r["sin_marca_id"]) > 0:
        verdict("BUG", f"{int(r['sin_marca_id'])} filas SIN marca_id ⇒ rompen Regla 1.")
    else:
        verdict("OK", "Todas las filas tienen marca_id.")

    if int(r["sin_descp_marca"]) > 0:
        verdict("WARN", f"{int(r['sin_descp_marca'])} filas con descp_marca vacío/—.")

    if int(r["sin_caso_id"]) == n:
        verdict("WARN", "TODAS las filas sin caso_id (Regla 1 caerá en 'Sin caso').")
    elif int(r["sin_caso_id"]) > 0:
        verdict("INFO", f"{int(r['sin_caso_id'])}/{n} filas sin caso_id (mix de casos).")
    else:
        verdict("OK", "Todas las filas con caso_id.")

    if int(r["sin_color_hex"]) == n:
        verdict("WARN", "Ninguna fila tiene color_hex (backfill no se reflejó en la vista).")
    elif int(r["sin_color_hex"]) > 0:
        verdict("INFO", f"{int(r['sin_color_hex'])}/{n} filas sin color_hex (caen al regex).")
    else:
        verdict("OK", "Todas las filas con color_hex.")

    if int(r["cajas_vacias"]) > 0:
        verdict("WARN", f"{int(r['cajas_vacias'])} filas con cantidad_cajas <= 0 (deberían filtrarse).")


def check_3_huerfanos_fk() -> None:
    header(3, "HUÉRFANOS — preview de las FKs que crea la migración 028")
    print(dim("  Si alguna fila aparece huérfana, la FK de la 028 va a fallar"))
    print(dim("  al primer pedido que la toque. Acá lo detectamos antes."))
    print()

    # ── 3a. marca_id huérfano (vista vs marca_v2) ────────────────────────────
    df1 = run("""
        SELECT
          COUNT(*)                                                   AS filas_con_marca_id,
          COUNT(*) FILTER (WHERE mv.id_marca IS NULL)                AS huerfanos,
          COUNT(DISTINCT v.marca_id) FILTER (WHERE mv.id_marca IS NULL) AS marcas_huerfanas_distintas
        FROM public.v_stock_rimec v
        LEFT JOIN public.marca_v2 mv ON mv.id_marca = v.marca_id
        WHERE v.marca_id IS NOT NULL
    """)
    if df1 is not None:
        print(bold("  · marca_id en v_stock_rimec → marca_v2(id_marca):"))
        tabla(df1)
        h = int(df1.iloc[0]["huerfanos"])
        if h == 0:
            verdict("OK", "No hay marca_id huérfanos. FK marca_id es SEGURA.")
        else:
            verdict("BUG", f"{h} filas con marca_id que no existe en marca_v2. FK va a fallar.")
            df1b = run("""
                SELECT DISTINCT v.marca_id, v.descp_marca
                FROM public.v_stock_rimec v
                LEFT JOIN public.marca_v2 mv ON mv.id_marca = v.marca_id
                WHERE v.marca_id IS NOT NULL AND mv.id_marca IS NULL
                ORDER BY v.marca_id
            """)
            print(bold("    IDs huérfanos:"))
            tabla(df1b)
    print()

    # ── 3b. caso_id huérfano (vista vs caso_precio_biblioteca) ───────────────
    df2 = run("""
        SELECT
          COUNT(*)                                                   AS filas_con_caso_id,
          COUNT(*) FILTER (WHERE c.id IS NULL)                       AS huerfanos,
          COUNT(DISTINCT v.caso_id) FILTER (WHERE c.id IS NULL)      AS casos_huerfanos_distintos
        FROM public.v_stock_rimec v
        LEFT JOIN public.caso_precio_biblioteca c ON c.id = v.caso_id
        WHERE v.caso_id IS NOT NULL
    """)
    if df2 is not None:
        print(bold("  · caso_id en v_stock_rimec → caso_precio_biblioteca(id):"))
        tabla(df2)
        h = int(df2.iloc[0]["huerfanos"])
        if h == 0:
            verdict("OK", "No hay caso_id huérfanos. FK caso_id es SEGURA.")
        else:
            verdict("BUG", f"{h} filas con caso_id que no existe en caso_precio_biblioteca.")


def check_4_factura_interna_schema() -> None:
    header(4, "TABLA `factura_interna` — estado pre-028")
    df = run("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'factura_interna'
          AND column_name IN ('marca_id', 'caso_id', 'marca', 'caso')
        ORDER BY column_name
    """)
    if df is None: return
    tabla(df)

    cols = set(df["column_name"].tolist())
    if {"marca", "caso"}.issubset(cols):
        verdict("OK", "Columnas `marca`, `caso` (text) ya existen.")
    else:
        verdict("WARN", "Faltan columnas `marca` o `caso`. La 028 NO las crea (las usa).")
    if {"marca_id", "caso_id"}.issubset(cols):
        verdict("INFO", "Columnas `marca_id`, `caso_id` ya existen. La 028 se saltea ADD COLUMN (idempotente).")
    else:
        verdict("INFO", "Columnas `marca_id`, `caso_id` aún no existen. La 028 las creará.")

    # ── Conteo de FIs existentes ────────────────────────────────────────────
    df_count = run("""
        SELECT
          COUNT(*) AS total_fi,
          COUNT(DISTINCT pp_id) AS pps_con_fi,
          COUNT(*) FILTER (WHERE estado = 'RESERVADA') AS reservadas,
          COUNT(*) FILTER (WHERE estado = 'FACTURADA') AS facturadas
        FROM public.factura_interna
    """)
    if df_count is not None and not df_count.empty:
        print()
        print(bold("  Inventario de facturas internas:"))
        tabla(df_count)


def check_5_rpc_actual() -> None:
    header(5, "RPC `confirmar_pedido_web` — versión actual en BD")
    df = run("""
        SELECT
          pg_get_function_arguments(oid) AS args,
          LENGTH(prosrc) AS body_len
        FROM pg_proc
        WHERE proname = 'confirmar_pedido_web'
    """)
    if df is None or df.empty:
        verdict("WARN", "RPC `confirmar_pedido_web` NO existe en BD. La 028 lo creará desde cero.")
        return

    tabla(df)

    # ¿Itera lotes[].marcas[] (vieja) o lotes[].facturas[] (nueva)?
    df_src = run("""
        SELECT
          (prosrc LIKE '%v_lote->''facturas''%')::int AS itera_facturas,
          (prosrc LIKE '%v_lote->''marcas''%')::int   AS itera_marcas
        FROM pg_proc WHERE proname = 'confirmar_pedido_web'
    """)
    if df_src is not None and not df_src.empty:
        ito_f = int(df_src.iloc[0]["itera_facturas"])
        ito_m = int(df_src.iloc[0]["itera_marcas"])
        if ito_f and not ito_m:
            verdict("OK", "RPC YA itera `lotes[].facturas[]` (Regla 1 enforced). 028 reaplica idempotente.")
        elif ito_m and not ito_f:
            verdict("BUG", "RPC todavía itera `lotes[].marcas[]` (versión vieja 010). Necesita la 028.")
        elif ito_m and ito_f:
            verdict("WARN", "RPC menciona ambas estructuras. Revisar.")
        else:
            verdict("WARN", "No se detectó ninguna estructura conocida. Revisar manualmente.")


def check_6_inventario() -> None:
    header(6, "INVENTARIO OPERATIVO — qué se puede vender ahora mismo")
    df = run("""
        SELECT
          COUNT(*)                                                        AS filas,
          COUNT(DISTINCT pp_id)                                           AS pps,
          COUNT(DISTINCT marca_id)                                        AS marcas,
          COUNT(DISTINCT caso_id) FILTER (WHERE caso_id IS NOT NULL)      AS casos,
          SUM(cantidad_cajas)                                             AS cajas_total,
          SUM(cantidad_cajas * pares_por_caja)                            AS pares_total
        FROM public.v_stock_rimec
        WHERE cantidad_cajas > 0
    """)
    if df is None: return
    tabla(df)

    r = df.iloc[0]
    pares = int(r["pares_total"] or 0)
    pps   = int(r["pps"] or 0)
    if pps == 0 or pares == 0:
        verdict("BUG", "No hay stock disponible para vender.")
    else:
        verdict("OK", f"{pares:,} pares disponibles en {pps} PPs ({int(r['marcas'])} marcas, {int(r['casos'])} casos).")

    # Detalle por marca (Top 10)
    df_marca = run("""
        SELECT
          descp_marca,
          COUNT(*)               AS items,
          COUNT(DISTINCT pp_id)  AS pps,
          SUM(cantidad_cajas)    AS cajas,
          SUM(cantidad_cajas * pares_por_caja) AS pares
        FROM public.v_stock_rimec
        WHERE cantidad_cajas > 0
        GROUP BY descp_marca
        ORDER BY pares DESC NULLS LAST
        LIMIT 10
    """)
    if df_marca is not None and not df_marca.empty:
        print()
        print(bold("  Top 10 marcas por pares disponibles:"))
        tabla(df_marca)


def check_7_simulacion_regla1() -> None:
    header(7, "SIMULACIÓN REGLA 1 — ¿cuántas FIs se generarían si compras TODO?")
    print(dim("  Una FI por cada (PP × marca_id × caso_id) con stock > 0."))
    df = run("""
        SELECT
          COUNT(*) AS facturas_que_se_generarian,
          COUNT(DISTINCT pp_id) AS pps_involucrados,
          MAX(items_por_grupo) AS max_items_por_factura,
          AVG(items_por_grupo)::numeric(10,2) AS prom_items_por_factura
        FROM (
          SELECT pp_id, marca_id, caso_id, COUNT(*) AS items_por_grupo
          FROM public.v_stock_rimec
          WHERE cantidad_cajas > 0
          GROUP BY pp_id, marca_id, caso_id
        ) g
    """)
    if df is None: return
    tabla(df)
    r = df.iloc[0]
    fi = int(r["facturas_que_se_generarian"] or 0)
    pps = int(r["pps_involucrados"] or 0)
    if fi == 0:
        verdict("BUG", "0 grupos posibles. Stock vacío o columnas malas.")
    else:
        verdict("INFO", f"Si compraras TODO el stock, se generarían {fi} FIs distribuidas en {pps} PPs.")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Auditoría pre-Migración 028.")
    ap.add_argument("--no-color", action="store_true", help="Desactivar colores ANSI.")
    args = ap.parse_args()
    if args.no_color:
        Style.disable()

    print()
    print(bold("┌" + "─" * 76 + "┐"))
    print(bold("│") + cyan("  AUDITORÍA PRE-028 · confirmar_pedido_web con Regla 1".ljust(76)) + bold("│"))
    print(bold("└" + "─" * 76 + "┘"))

    check_1_colores()
    check_2_vista_stock()
    check_3_huerfanos_fk()
    check_4_factura_interna_schema()
    check_5_rpc_actual()
    check_6_inventario()
    check_7_simulacion_regla1()

    print()
    print(cyan("═" * 78))
    print(bold("  Veredicto final:"))
    print(cyan("─" * 78))
    print("  · Si todos los checks dieron OK / INFO ⇒ aplicar migración 028.")
    print("  · Si hay BUG en check #3 (huérfanos) ⇒ limpiar antes o sacar la FK de la 028.")
    print("  · Si hay BUG en check #5 (RPC viejo) ⇒ aplicar 028 lo antes posible.")
    print(cyan("═" * 78))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
