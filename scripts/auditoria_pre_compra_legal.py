"""
Auditoría PRE-Compra Legal — fotografía del estado actual del pipeline.

Antes de cablear el flujo:
    PEDIDO PROVEEDOR  ─▶  COMPRA LEGAL  ─▶  FACTURA LEGAL (madre)
                                              ├──▶ BAZZAR (web)
                                              └──▶ STOCK DEPÓSITO RIMEC

Esta auditoría revela qué piezas ya existen, qué falta, y qué FIs están
listas para promover.

Checks:
  1. Inventario de FIs por estado (RESERVADA / CONFIRMADA / ANULADA).
  2. FIs CONFIRMADAS pendientes de pasar a compra (candidatas inmediatas).
  3. PPs cuyas FIs están TODAS confirmadas (candidatos a "Enviar a Compra").
  4. Tablas operativas relacionadas (compra_legal, traspaso, movimiento, stock_bazar).
  5. Catálogo de almacenes (¿existe ALM_DEPOSITO_RIMEC?).
  6. Compras legales históricas y su estado actual.
  7. Reconciliación stock_bazar ⇄ movimiento (los dos pipelines paralelos).

Uso:
    python scripts/auditoria_pre_compra_legal.py [--no-color]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pandas as pd
from core.database import get_dataframe


# ─────────────────────────────────────────────────────────────────────────────
# Estética
# ─────────────────────────────────────────────────────────────────────────────
class Style:
    use_color = True
    @classmethod
    def disable(cls):
        cls.use_color = False
    @classmethod
    def c(cls, code: str, txt: str) -> str:
        return f"\033[{code}m{txt}\033[0m" if cls.use_color else txt

def bold(txt):   return Style.c("1",  txt)
def dim(txt):    return Style.c("2",  txt)
def green(txt):  return Style.c("32", txt)
def red(txt):    return Style.c("31", txt)
def yellow(txt): return Style.c("33", txt)
def cyan(txt):   return Style.c("36", txt)
def blue(txt):   return Style.c("34", txt)


def header(n: int, titulo: str) -> None:
    print()
    print(cyan("═" * 78))
    print(cyan(f"  [{n}] {titulo}"))
    print(cyan("═" * 78))


def verdict(estado: str, msg: str) -> None:
    tag = {
        "OK":   green("  ✓ OK  "),
        "WARN": yellow("  ⚠ WARN"),
        "BUG":  red("  ✗ BUG "),
        "INFO": blue("  ℹ INFO"),
    }.get(estado, f"  ? {estado}")
    print(f"{tag}  {msg}")


def tabla(df: pd.DataFrame | None, max_filas: int = 30) -> None:
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


def existe_tabla(nombre: str, esquema: str = "public") -> bool:
    df = run("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = :sch AND table_name = :n
    """, {"sch": esquema, "n": nombre})
    return df is not None and not df.empty


def existe_columna(tabla: str, col: str, esquema: str = "public") -> bool:
    df = run("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = :sch AND table_name = :t AND column_name = :c
    """, {"sch": esquema, "t": tabla, "c": col})
    return df is not None and not df.empty


def columnas_de(tabla: str, esquema: str = "public") -> set[str]:
    df = run("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = :sch AND table_name = :t
    """, {"sch": esquema, "t": tabla})
    if df is None or df.empty:
        return set()
    return set(df["column_name"].tolist())


def pick(cols: set[str], *candidates: str) -> str | None:
    """Devuelve la primera col de `candidates` que exista en `cols`."""
    for c in candidates:
        if c in cols:
            return c
    return None


# ─────────────────────────────────────────────────────────────────────────────
# CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def check_1_inventario_fi() -> None:
    header(1, "INVENTARIO DE FACTURAS INTERNAS — distribución por estado")
    df = run("""
        SELECT
          estado,
          COUNT(*)               AS facturas,
          SUM(total_pares)::int  AS pares,
          SUM(total_monto)::bigint AS monto_total
        FROM public.factura_interna
        GROUP BY estado
        ORDER BY estado
    """)
    tabla(df)

    confirmadas = run("""
        SELECT COUNT(*) AS n FROM public.factura_interna WHERE estado='CONFIRMADA'
    """)
    n_conf = int(confirmadas.iloc[0]["n"]) if confirmadas is not None and not confirmadas.empty else 0
    if n_conf == 0:
        verdict("INFO", "No hay FIs CONFIRMADAS aún. Necesitás confirmar al menos 1 para probar el flujo de compra.")
    else:
        verdict("OK", f"{n_conf} FI(s) CONFIRMADAS listas para promover a compra legal.")


def check_2_fis_candidatas() -> None:
    header(2, "FIs CANDIDATAS A PASAR A COMPRA LEGAL")
    print(dim("  (FIs CONFIRMADAS sin compra/traspaso asociado todavía)"))

    # Detectar si existe la columna `compra_legal_id` o equivalente en factura_interna
    tiene_compra_fk = existe_columna("factura_interna", "compra_legal_id")
    if tiene_compra_fk:
        df = run("""
            SELECT
              fi.id, fi.nro_factura, fi.marca, fi.caso,
              fi.total_pares, fi.total_monto, fi.created_at,
              pp.numero_registro AS pp,
              cv.descp_cliente AS cliente
            FROM public.factura_interna fi
            LEFT JOIN public.pedido_proveedor pp ON pp.id = fi.pp_id
            LEFT JOIN public.cliente_v2 cv       ON cv.id_cliente = fi.cliente_id
            WHERE fi.estado = 'CONFIRMADA'
              AND fi.compra_legal_id IS NULL
            ORDER BY fi.created_at DESC
            LIMIT 50
        """)
    else:
        verdict("INFO", "No existe `factura_interna.compra_legal_id` (FK al PADRE compra) — falta cablear.")
        df = run("""
            SELECT
              fi.id, fi.nro_factura, fi.marca, fi.caso,
              fi.total_pares, fi.total_monto, fi.created_at,
              pp.numero_registro AS pp,
              cv.descp_cliente AS cliente
            FROM public.factura_interna fi
            LEFT JOIN public.pedido_proveedor pp ON pp.id = fi.pp_id
            LEFT JOIN public.cliente_v2 cv       ON cv.id_cliente = fi.cliente_id
            WHERE fi.estado = 'CONFIRMADA'
            ORDER BY fi.created_at DESC
            LIMIT 50
        """)
    tabla(df)
    if df is not None and not df.empty:
        verdict("OK", f"{len(df)} FI(s) confirmadas se ven {'sin compra asociada' if tiene_compra_fk else '(sin filtro de compra)'}.")
    else:
        verdict("WARN", "Ninguna FI confirmada visible.")


def check_3_pps_listos() -> None:
    header(3, "PEDIDOS PROVEEDOR con TODAS sus FIs CONFIRMADAS")
    print(dim("  (candidatos a 'Enviar a Compra' en batch)"))
    df = run("""
        WITH fi_por_pp AS (
            SELECT
              fi.pp_id,
              COUNT(*) FILTER (WHERE fi.estado = 'CONFIRMADA') AS conf,
              COUNT(*) FILTER (WHERE fi.estado = 'RESERVADA')  AS res,
              COUNT(*) FILTER (WHERE fi.estado = 'ANULADA')    AS anul,
              COUNT(*)                                          AS total,
              SUM(fi.total_pares)                               AS pares
            FROM public.factura_interna fi
            WHERE fi.pp_id IS NOT NULL
            GROUP BY fi.pp_id
        )
        SELECT
          pp.numero_registro AS pp,
          x.total            AS fis,
          x.conf, x.res, x.anul,
          x.pares::int       AS pares,
          pp.estado          AS pp_estado
        FROM fi_por_pp x
        JOIN public.pedido_proveedor pp ON pp.id = x.pp_id
        WHERE x.res = 0 AND x.conf > 0
        ORDER BY pp.id DESC
        LIMIT 30
    """)
    tabla(df)
    if df is not None and not df.empty:
        verdict("OK", f"{len(df)} PP(s) tienen TODAS sus FIs cerradas (sin RESERVADAS) y al menos 1 confirmada.")
    else:
        verdict("INFO", "Todavía no hay PPs con todas las FIs confirmadas.")


def check_4_tablas_pipeline() -> None:
    header(4, "TABLAS OPERATIVAS DEL PIPELINE POST-FI")
    tablas = [
        ("factura_interna",          "FI (origen del flujo)"),
        ("factura_interna_detalle",  "Items de FI"),
        ("compra_legal",             "PADRE de la compra (entidad legal)"),
        ("factura_legal",            "Factura legal (madre) — si existe como tabla aparte"),
        ("traspaso",                 "Movimiento entre almacenes (PP→destinos)"),
        ("movimiento",               "Cabecera de movimiento de stock"),
        ("movimiento_detalle",       "Detalle SKU del movimiento"),
        ("combinacion",              "SKU normalizado (linea+ref+material+color)"),
        ("almacen",                  "Catálogo de almacenes"),
        ("stock_bazar",              "Stock para web Next.js (pipeline paralelo)"),
        ("stock_deposito",           "Stock depósito Rimec (¿existe?)"),
        ("stock_deposito_rimec",     "Stock depósito Rimec (¿alternativa?)"),
    ]
    rows = []
    for t, descr in tablas:
        if existe_tabla(t):
            cnt = run(f"SELECT COUNT(*) AS n FROM public.{t}")
            n = int(cnt.iloc[0]["n"]) if cnt is not None and not cnt.empty else 0
            rows.append({"tabla": t, "existe": "✓", "filas": n, "descripcion": descr})
        else:
            rows.append({"tabla": t, "existe": "✗", "filas": 0, "descripcion": descr})
    df = pd.DataFrame(rows)
    tabla(df, max_filas=30)

    falt = [r for r in rows if r["existe"] == "✗"]
    pres = [r for r in rows if r["existe"] == "✓"]
    verdict("INFO", f"{len(pres)} tabla(s) presentes, {len(falt)} ausentes.")
    if any(r["tabla"] in ("stock_deposito", "stock_deposito_rimec") and r["existe"] == "✓" for r in rows):
        verdict("OK", "Ya existe tabla para stock de depósito Rimec.")
    else:
        verdict("WARN", "No hay tabla específica de stock_deposito_rimec — habrá que crearla o reusar otra (movimiento + almacen=4).")


def check_5_almacenes() -> None:
    header(5, "CATÁLOGO DE ALMACENES")
    if not existe_tabla("almacen"):
        verdict("BUG", "No existe la tabla `almacen` — el pipeline traspaso/movimiento no podría correr.")
        return

    cols = columnas_de("almacen")
    print(dim(f"  Columnas: {sorted(cols)}"))

    # Detección dinámica del nombre de la columna descriptiva
    id_col   = pick(cols, "id", "id_almacen", "almacen_id") or "id"
    nom_col  = pick(cols, "descripcion", "nombre", "descp_almacen", "desc_almacen", "name")
    sel = f"{id_col}, "
    sel += f"{nom_col}" if nom_col else "NULL AS nombre"
    df = run(f"""
        SELECT {sel}
        FROM public.almacen
        ORDER BY {id_col}
    """)
    tabla(df)
    if df is None or df.empty:
        verdict("WARN", "Tabla `almacen` vacía.")
        return
    try:
        ids = set(int(r) for r in df[id_col].tolist())
    except Exception:
        ids = set()
    if 1 in ids: verdict("OK", "ALM_WEB_BAZAR (id=1) presente.")
    if 3 in ids: verdict("OK", "ALM_TRANSITO (id=3) presente.")
    if 4 in ids:
        verdict("OK", "ALM_DEPOSITO_RIMEC (id=4) presente — listo para cablear destino dual.")
    else:
        verdict("WARN", "No hay almacén ID=4. Habrá que crearlo para el destino 'Depósito Rimec'.")


def check_6_compras_legales() -> None:
    header(6, "COMPRAS LEGALES — schema + histórico")
    if not existe_tabla("compra_legal"):
        verdict("INFO", "No existe la tabla `compra_legal`.")
        return

    cols = columnas_de("compra_legal")
    print(dim(f"  Columnas: {sorted(cols)}"))

    if "estado" in cols:
        df = run("""
            SELECT
              COUNT(*)                              AS total,
              COUNT(*) FILTER (WHERE estado = 'PENDIENTE')  AS pendientes,
              COUNT(*) FILTER (WHERE estado = 'CONFIRMADA') AS confirmadas,
              COUNT(*) FILTER (WHERE estado = 'ANULADA')    AS anuladas
            FROM public.compra_legal
        """)
        tabla(df)
    else:
        df = run("SELECT COUNT(*) AS total FROM public.compra_legal")
        tabla(df)
        verdict("INFO", "Sin columna `estado` — versión simplificada del schema.")

    # Top 10 últimos registros (con las columnas que existan)
    id_col    = pick(cols, "id", "id_compra")
    nro_col   = pick(cols, "nro_factura_legal", "nro_factura", "nro_compra",
                     "numero_factura", "numero_compra", "documento")
    fecha_col = pick(cols, "fecha_factura", "fecha", "fecha_compra", "created_at")
    sels = [c for c in [id_col, nro_col, fecha_col, "estado" if "estado" in cols else None] if c]
    if sels:
        df2 = run(f"""
            SELECT {', '.join(sels)}
            FROM public.compra_legal
            ORDER BY {id_col or fecha_col or sels[0]} DESC
            LIMIT 10
        """)
        if df2 is not None and not df2.empty:
            print(dim("\n  Últimas 10:"))
            tabla(df2)


def check_7_reconciliacion_stock() -> None:
    header(7, "RECONCILIACIÓN STOCK_BAZAR ⇄ MOVIMIENTO (pipelines paralelos)")

    # ── stock_bazar ──
    if not existe_tabla("stock_bazar"):
        verdict("INFO", "No existe `stock_bazar` — pipeline web Next.js ausente.")
    else:
        sb_cols = columnas_de("stock_bazar")
        print(dim(f"  stock_bazar columnas: {sorted(sb_cols)}"))
        pares_col = pick(sb_cols, "cantidad_pares", "pares", "stock_pares", "qty_pares")
        cajas_col = pick(sb_cols, "cantidad_cajas", "cajas", "stock_cajas", "qty_cajas")
        sels = ["COUNT(*) AS skus"]
        if pares_col: sels.append(f"COALESCE(SUM({pares_col}),0)::int AS pares")
        if cajas_col: sels.append(f"COALESCE(SUM({cajas_col}),0)::int AS cajas")
        df_sb = run(f"SELECT {', '.join(sels)} FROM public.stock_bazar")
        tabla(df_sb)

    # ── movimiento_detalle ──
    if not existe_tabla("movimiento_detalle"):
        verdict("INFO", "No existe `movimiento_detalle` — pipeline Streamlit ausente.")
        return

    md_cols    = columnas_de("movimiento_detalle")
    m_cols     = columnas_de("movimiento")
    a_cols     = columnas_de("almacen")
    print(dim(f"  movimiento columnas: {sorted(m_cols)}"))
    print(dim(f"  movimiento_detalle columnas: {sorted(md_cols)}"))

    pares_col = pick(md_cols, "cantidad_pares", "pares")
    cajas_col = pick(md_cols, "cantidad_cajas", "cajas")
    dest_col  = pick(m_cols,  "almacen_destino_id", "id_almacen_destino", "destino_id", "almacen_id")
    estado_col = pick(m_cols, "estado", "status")
    alm_nom   = pick(a_cols,  "descripcion", "nombre", "descp_almacen", "desc_almacen")

    if not (pares_col and dest_col):
        verdict("WARN", "No pude detectar columnas necesarias en movimiento_detalle / movimiento.")
        return

    where = f"WHERE m.{estado_col} = 'CONFIRMADO'" if estado_col else ""
    nombre_sel = f"a.{alm_nom} AS nombre" if alm_nom else "NULL AS nombre"
    df_mv = run(f"""
        SELECT
          m.{dest_col}              AS almacen,
          {nombre_sel},
          COUNT(DISTINCT md.id)     AS detalles,
          SUM(md.{pares_col})::int  AS pares
          {', SUM(md.' + cajas_col + ')::int AS cajas' if cajas_col else ''}
        FROM public.movimiento m
        JOIN public.movimiento_detalle md ON md.movimiento_id = m.id
        LEFT JOIN public.almacen a       ON a.id = m.{dest_col}
        {where}
        GROUP BY m.{dest_col}{', a.' + alm_nom if alm_nom else ''}
        ORDER BY m.{dest_col}
    """)
    if df_mv is not None and not df_mv.empty:
        print(dim("\n  Stock acumulado por destino (movimiento CONFIRMADO):"))
        tabla(df_mv)
    else:
        verdict("INFO", "Sin movimientos confirmados todavía.")


def check_8_schema_fi() -> None:
    header(8, "SCHEMA `factura_interna` — columnas clave post-029")
    df = run("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'factura_interna'
        ORDER BY ordinal_position
    """)
    tabla(df, max_filas=40)
    if df is None or df.empty:
        verdict("BUG", "No se pudo leer el schema.")
        return
    cols = set(df["column_name"].tolist())
    needed = {"marca_id", "caso_id", "pedido_id", "pp_id"}
    falt = needed - cols
    if not falt:
        verdict("OK", "Todas las columnas clave presentes (marca_id, caso_id, pedido_id, pp_id).")
    else:
        verdict("BUG", f"Faltan columnas: {', '.join(sorted(falt))}")

    # ¿Existe FK al padre compra?
    if "compra_legal_id" in cols:
        verdict("OK", "Ya existe `factura_interna.compra_legal_id` — el cableado al padre está listo.")
    else:
        verdict("INFO", "Falta `factura_interna.compra_legal_id` — necesario para 'Enviar a Compra'.")


def check_9_schemas_legacy() -> None:
    header(9, "SCHEMAS COMPLETOS — tablas legadas del pipeline")
    print(dim("  Volcamos el schema de las tablas críticas para diseñar la migración 030.\n"))

    for t in ("compra_legal", "traspaso", "movimiento", "movimiento_detalle",
              "combinacion", "stock_bazar", "almacen"):
        if not existe_tabla(t):
            verdict("INFO", f"`{t}` — no existe.")
            continue
        print(bold(f"\n  ── {t} ──"))
        df = run("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :t
            ORDER BY ordinal_position
        """, {"t": t})
        tabla(df, max_filas=40)

    # Foreign Keys salientes desde factura_interna (¿ya hay relación al pipeline?)
    print(bold("\n  ── FKs salientes de `factura_interna` ──"))
    df_fk = run("""
        SELECT
          tc.constraint_name,
          kcu.column_name           AS columna,
          ccu.table_name            AS ref_tabla,
          ccu.column_name           AS ref_columna
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema    = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema    = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema    = 'public'
          AND tc.table_name      = 'factura_interna'
        ORDER BY kcu.column_name
    """)
    tabla(df_fk)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-color", action="store_true", help="Desactiva ANSI colors.")
    args = ap.parse_args()
    if args.no_color:
        Style.disable()

    print(bold("\n🔍 AUDITORÍA PRE-COMPRA LEGAL — Pipeline post-FI"))
    print(dim(  "    fotografía del estado actual antes de cablear PP→Compra→Bazzar/Depósito\n"))

    check_1_inventario_fi()
    check_2_fis_candidatas()
    check_3_pps_listos()
    check_4_tablas_pipeline()
    check_5_almacenes()
    check_6_compras_legales()
    check_7_reconciliacion_stock()
    check_8_schema_fi()
    check_9_schemas_legacy()

    print()
    print(cyan("═" * 78))
    print(cyan(bold("  ✅ Auditoría completa")))
    print(cyan("═" * 78))


if __name__ == "__main__":
    main()
