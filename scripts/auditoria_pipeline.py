"""
Auditoría del pipeline COMPLETO: del tránsito Rimec al pedido web Bazzar.

Muestra el estado actual de cada eslabón de la cadena:

    [pp_detalle]  →  [factura_interna]  →  [traspaso]  →  [movimiento]  →
        [stock_bazar / combinacion]  →  [pedido_web]

Cada bloque imprime conteos, sumas, ejemplos y un veredicto automático
(✅ tiene datos, ⚠ vacío esperable, 🐛 vacío inesperado).

Uso:
    python scripts/auditoria_pipeline.py
    python scripts/auditoria_pipeline.py --no-color
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pandas as pd

from core.database import get_dataframe


# ─────────────────────────────────────────────────────────────────────────────
# Render
# ─────────────────────────────────────────────────────────────────────────────

class _C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"


def _disable_colors() -> None:
    for name in vars(_C):
        if not name.startswith("_"):
            setattr(_C, name, "")


def _seccion(num: str, titulo: str) -> None:
    print()
    print(f"{_C.BOLD}{_C.CYAN}{'═' * 78}{_C.RESET}")
    print(f"{_C.BOLD}{_C.CYAN}  {num}  {titulo}{_C.RESET}")
    print(f"{_C.BOLD}{_C.CYAN}{'═' * 78}{_C.RESET}")


def _df(df: pd.DataFrame | None, max_rows: int = 30) -> None:
    if df is None or df.empty:
        print(f"  {_C.DIM}(sin filas){_C.RESET}")
        return
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 60)
    n = len(df)
    print(df.head(max_rows).to_string(index=False))
    if n > max_rows:
        print(f"  {_C.DIM}... {n - max_rows} filas más omitidas{_C.RESET}")


def _ok(msg: str) -> None:
    print(f"{_C.GREEN}  ✅ {msg}{_C.RESET}")


def _warn(msg: str) -> None:
    print(f"{_C.YELLOW}  ⚠  {msg}{_C.RESET}")


def _bug(msg: str) -> None:
    print(f"{_C.RED}  🐛 {msg}{_C.RESET}")


def _info(msg: str) -> None:
    print(f"{_C.BLUE}  ℹ  {msg}{_C.RESET}")


def _tabla_existe(nombre: str) -> bool:
    """Verifica existencia de una tabla/vista en el esquema public."""
    df = get_dataframe(
        "SELECT to_regclass(:n) IS NOT NULL AS existe",
        {"n": f"public.{nombre}"},
    )
    if df is None or df.empty:
        return False
    return bool(df.iloc[0]["existe"])


# ─────────────────────────────────────────────────────────────────────────────
# Bloques
# ─────────────────────────────────────────────────────────────────────────────

def bloque_almacenes() -> None:
    _seccion("①", "Almacenes registrados (catálogo)")

    candidatas = ["almacen_v2", "almacen"]
    tabla = next((t for t in candidatas if _tabla_existe(t)), None)
    if tabla is None:
        _bug("No encontré tabla 'almacen' ni 'almacen_v2'.")
        return

    # Buscar columnas comunes
    cols_df = get_dataframe(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='{tabla}'
        ORDER BY ordinal_position
    """)
    cols = cols_df["column_name"].tolist() if cols_df is not None else []
    _info(f"Tabla: public.{tabla}  ·  columnas: {cols}")

    df = get_dataframe(f"SELECT * FROM public.{tabla} ORDER BY 1 LIMIT 30")
    _df(df)


def bloque_stock_bazar() -> None:
    _seccion("②", "Stock en BAZAR (lo que ve la web bazzar-web)")

    if not _tabla_existe("stock_bazar"):
        _warn("No existe public.stock_bazar (puede ser vista creada bajo demanda).")
        return

    df_tot = get_dataframe("""
        SELECT COUNT(*)::int                       AS combinaciones,
               COALESCE(SUM(stock), 0)::int        AS pares_totales,
               COUNT(DISTINCT linea_id)::int       AS lineas_distintas
        FROM public.stock_bazar
    """)
    _df(df_tot)
    if df_tot is not None and not df_tot.empty:
        n = int(df_tot.iloc[0]["combinaciones"])
        pares = int(df_tot.iloc[0]["pares_totales"]) if pd.notna(df_tot.iloc[0]["pares_totales"]) else 0
        if n == 0:
            _warn("Bazar está vacío. Necesitás Factura Interna → Traspaso → Movimiento INGRESO_COMPRA para poblarlo.")
        else:
            _ok(f"Bazar tiene {n:,} combinaciones con {pares:,} pares totales.")

    print()
    _info("Top 10 líneas con más stock en Bazar:")
    df_top = get_dataframe("""
        SELECT linea_id, SUM(stock) AS pares, COUNT(*) AS combinaciones
        FROM public.stock_bazar
        GROUP BY linea_id
        ORDER BY pares DESC NULLS LAST
        LIMIT 10
    """)
    _df(df_top)


def bloque_combinacion() -> None:
    _seccion("③", "Combinaciones definidas (SKU físico)")

    if not _tabla_existe("combinacion"):
        _warn("No existe public.combinacion.")
        return

    df = get_dataframe("""
        SELECT COUNT(*) AS filas FROM public.combinacion
    """)
    _df(df)
    if df is not None and int(df.iloc[0]["filas"]) > 0:
        _info("Estructura:")
        df_cols = get_dataframe("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='combinacion'
            ORDER BY ordinal_position
        """)
        _df(df_cols)


def bloque_movimientos() -> None:
    _seccion("④", "Movimientos (INGRESO_COMPRA / TRASPASO / VENTA_WEB)")

    if not _tabla_existe("movimiento"):
        _warn("No existe public.movimiento.")
        return

    df = get_dataframe("""
        SELECT m.tipo,
               COUNT(*)                                 AS movimientos,
               COUNT(DISTINCT md.movimiento_id) FILTER (WHERE md.id IS NOT NULL) AS movs_con_detalle,
               COALESCE(SUM(md.cantidad_pares), 0)::int AS pares_total
        FROM public.movimiento m
        LEFT JOIN public.movimiento_detalle md ON md.movimiento_id = m.id
        GROUP BY m.tipo
        ORDER BY m.tipo
    """)
    _df(df)
    if df is None or df.empty:
        _warn("No hay movimientos en el sistema. Aún no se aprobó ninguna factura interna.")
    else:
        for _, row in df.iterrows():
            tipo = row["tipo"]
            n_movs = int(row["movimientos"])
            con_det = int(row["movs_con_detalle"]) if pd.notna(row["movs_con_detalle"]) else 0
            pares = int(row["pares_total"]) if pd.notna(row["pares_total"]) else 0
            if con_det < n_movs:
                _warn(f"{tipo}: {n_movs} cabeceras pero solo {con_det} con detalle, {pares:,} pares.")
            else:
                _ok(f"{tipo}: {n_movs} cabeceras, {con_det} con detalle, {pares:,} pares.")


def bloque_factura_interna() -> None:
    _seccion("⑤", "Facturas Internas (FI)")

    if not _tabla_existe("factura_interna"):
        _warn("No existe public.factura_interna.")
        return

    df = get_dataframe("""
        SELECT estado,
               COUNT(*) AS cant,
               COALESCE(SUM(total_pares), 0)::int AS pares_total
        FROM public.factura_interna
        GROUP BY estado
        ORDER BY estado
    """)
    _df(df)
    if df is None or df.empty:
        _warn("No hay Facturas Internas. Próximo paso: generar FIs desde el PP cargado.")
        return

    print()
    df_recientes = get_dataframe("""
        SELECT fi.id, fi.numero_registro, fi.estado, fi.pp_id,
               fi.id_marca, fi.caso_id,
               fi.total_pares, fi.total_fob_usd,
               COUNT(fid.id) AS items_detalle,
               fi.created_at
        FROM public.factura_interna fi
        LEFT JOIN public.factura_interna_detalle fid ON fid.factura_id = fi.id
        GROUP BY fi.id, fi.numero_registro, fi.estado, fi.pp_id,
                 fi.id_marca, fi.caso_id, fi.total_pares,
                 fi.total_fob_usd, fi.created_at
        ORDER BY fi.id DESC
        LIMIT 20
    """)
    _info("Facturas Internas recientes:")
    _df(df_recientes)


def bloque_compra_legal() -> None:
    _seccion("⑥", "Compras Legales (CL)")

    if not _tabla_existe("compra_legal"):
        _warn("No existe public.compra_legal.")
        return

    df = get_dataframe("""
        SELECT estado, COUNT(*) AS cant
        FROM public.compra_legal
        GROUP BY estado
        ORDER BY estado
    """)
    _df(df)
    if df is None or df.empty:
        _warn("No hay Compras Legales. Se generan al aprobar facturas internas.")


def bloque_traspasos() -> None:
    _seccion("⑦", "Traspasos (movimiento entre almacenes)")

    if not _tabla_existe("traspaso"):
        _warn("No existe public.traspaso.")
        return

    df = get_dataframe("""
        SELECT t.estado,
               COUNT(*) AS cant,
               COALESCE(SUM(td.cantidad_pares), 0)::int AS pares
        FROM public.traspaso t
        LEFT JOIN public.traspaso_detalle td ON td.traspaso_id = t.id
        GROUP BY t.estado
        ORDER BY t.estado
    """)
    _df(df)


def bloque_pedido_web() -> None:
    _seccion("⑧", "Pedidos Web (ventas Bazzar)")

    if not _tabla_existe("pedido_web"):
        _warn("No existe public.pedido_web.")
        return

    df = get_dataframe("""
        SELECT pw.estado,
               COUNT(*) AS pedidos,
               COALESCE(SUM(pwd.cantidad), 0)::int AS pares
        FROM public.pedido_web pw
        LEFT JOIN public.pedido_web_detalle pwd ON pwd.pedido_web_id = pw.id
        GROUP BY pw.estado
        ORDER BY pw.estado
    """)
    _df(df)
    if df is None or df.empty:
        _warn("No hay pedidos web aún. Esperable hasta que la web Bazzar tenga stock.")


def bloque_resumen_pipeline() -> None:
    _seccion("⑨", "RESUMEN: Salud del pipeline end-to-end")

    chequeos: list[tuple[str, str, str]] = []

    def _check(nombre_tabla: str, query: str, label: str) -> None:
        if not _tabla_existe(nombre_tabla):
            chequeos.append((label, "—", "tabla no existe"))
            return
        df = get_dataframe(query)
        if df is None or df.empty:
            chequeos.append((label, "0", "vacío"))
            return
        try:
            v = int(df.iloc[0, 0])
        except Exception:
            v = 0
        chequeos.append((label, f"{v:,}", "ok" if v > 0 else "vacío"))

    _check("pedido_proveedor",         "SELECT COUNT(*) FROM public.pedido_proveedor",         "1. Pedidos Proveedor")
    _check("pedido_proveedor_detalle", "SELECT COALESCE(SUM(cantidad_pares),0) FROM public.pedido_proveedor_detalle", "   └ pares en tránsito (Rimec)")
    _check("factura_interna",          "SELECT COUNT(*) FROM public.factura_interna",          "2. Facturas Internas")
    _check("compra_legal",             "SELECT COUNT(*) FROM public.compra_legal",             "3. Compras Legales")
    _check("traspaso",                 "SELECT COUNT(*) FROM public.traspaso",                 "4. Traspasos")
    _check("movimiento",               "SELECT COUNT(*) FROM public.movimiento",               "5. Movimientos")
    _check("combinacion",              "SELECT COUNT(*) FROM public.combinacion",              "6. Combinaciones (SKUs)")
    _check("stock_bazar",              "SELECT COALESCE(SUM(stock),0) FROM public.stock_bazar","7. Stock en BAZAR (pares)")
    _check("pedido_web",               "SELECT COUNT(*) FROM public.pedido_web",               "8. Pedidos Web")

    print()
    df = pd.DataFrame(chequeos, columns=["paso", "cantidad", "estado"])
    print(df.to_string(index=False))

    print()
    # Diagnóstico final
    map_estado = dict((label.strip(), estado) for label, _, estado in chequeos)
    print()
    if map_estado.get("1. Pedidos Proveedor") == "ok" and map_estado.get("2. Facturas Internas") == "vacío":
        _bug("Tenés PP cargados pero NO Facturas Internas → próximo paso: generar FIs.")
    elif map_estado.get("2. Facturas Internas") == "ok" and map_estado.get("5. Movimientos") == "vacío":
        _bug("Hay FIs pero no se aprobaron (no hay movimientos).")
    elif map_estado.get("5. Movimientos") == "ok" and map_estado.get("7. Stock en BAZAR (pares)") == "vacío":
        _bug("Hay movimientos pero stock_bazar quedó en 0 → revisar pipeline de movimiento → stock.")
    elif map_estado.get("7. Stock en BAZAR (pares)") == "ok" and map_estado.get("8. Pedidos Web") == "vacío":
        _ok("Pipeline operativa hasta stock. Esperando ventas web.")
    elif map_estado.get("8. Pedidos Web") == "ok":
        _ok("Pipeline completa: hay pedidos web activos.")


# ─────────────────────────────────────────────────────────────────────────────
# Entry
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoría del pipeline completo")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()
    if args.no_color:
        _disable_colors()

    print()
    print(f"{_C.BOLD}{_C.MAGENTA}{'═' * 78}{_C.RESET}")
    print(f"{_C.BOLD}{_C.MAGENTA}  AUDITORÍA DE PIPELINE COMPLETO: tránsito → factura → stock → venta web{_C.RESET}")
    print(f"{_C.BOLD}{_C.MAGENTA}{'═' * 78}{_C.RESET}")

    bloque_almacenes()
    bloque_stock_bazar()
    bloque_combinacion()
    bloque_movimientos()
    bloque_factura_interna()
    bloque_compra_legal()
    bloque_traspasos()
    bloque_pedido_web()
    bloque_resumen_pipeline()

    print()
    print(f"{_C.BOLD}{_C.MAGENTA}{'═' * 78}{_C.RESET}")
    print(f"{_C.BOLD}{_C.MAGENTA}  FIN{_C.RESET}")
    print(f"{_C.BOLD}{_C.MAGENTA}{'═' * 78}{_C.RESET}")


if __name__ == "__main__":
    main()
