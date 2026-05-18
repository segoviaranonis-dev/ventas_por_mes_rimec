"""
Auditoría de integridad: pedido_proveedor → pedido_proveedor_detalle → v_stock_rimec

Corre 10 queries en cadena, imprime los resultados con formato, y al final
emite un veredicto automático (✅ OK / ⚠ ATENCIÓN / 🐛 BUG).

Uso:
    python scripts/auditoria_proforma.py
    python scripts/auditoria_proforma.py --pp-id 1        # auditar un PP puntual
    python scripts/auditoria_proforma.py --solo-dupes     # solo el bloque de duplicados
    python scripts/auditoria_proforma.py --no-color       # sin códigos ANSI

Ideal para re-correr después de cualquier cambio en el parser, el INSERT
o la vista, y verificar end-to-end que cada capa sigue siendo fiel.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pandas as pd

from core.database import get_dataframe


# ─────────────────────────────────────────────────────────────────────────────
# Render helpers
# ─────────────────────────────────────────────────────────────────────────────

class _C:
    """Códigos ANSI para colorear salida en terminal."""
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


def _hr(char: str = "─", width: int = 78) -> str:
    return char * width


def _seccion(num: str, titulo: str) -> None:
    print()
    print(f"{_C.BOLD}{_C.CYAN}{_hr('═')}{_C.RESET}")
    print(f"{_C.BOLD}{_C.CYAN}  {num}  {titulo}{_C.RESET}")
    print(f"{_C.BOLD}{_C.CYAN}{_hr('═')}{_C.RESET}")


def _print_df(df: pd.DataFrame | None, max_rows: int = 50) -> None:
    if df is None or df.empty:
        print(f"  {_C.DIM}(sin filas){_C.RESET}")
        return
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 60)
    n = len(df)
    show = df.head(max_rows)
    print(show.to_string(index=False))
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


# ─────────────────────────────────────────────────────────────────────────────
# Bloques de auditoría
# ─────────────────────────────────────────────────────────────────────────────

_FILTRO_PP = "pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])"


def bloque_1_resumen_global(pp_id: int | None) -> tuple[int, int, int, int, int, int]:
    """① Resumen global de cada capa.

    Returns
    -------
    tuple
        (items_det, combos_det, pares_det, items_vis, combos_vis, pares_vis)
    """
    _seccion("①", "Resumen global por capa")

    filtro_pp = f"AND pp.id = {pp_id}" if pp_id is not None else ""

    det = get_dataframe(f"""
        SELECT
            COUNT(*)::int                              AS items,
            COUNT(DISTINCT (ppd.linea, ppd.referencia,
                            ppd.material_code, ppd.color_code))::int AS combinaciones,
            COALESCE(SUM(ppd.cantidad_pares), 0)::int  AS pares
        FROM public.pedido_proveedor_detalle ppd
        JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        WHERE {_FILTRO_PP}
          AND COALESCE(ppd.cantidad_pares, 0) > 0
          {filtro_pp}
    """)
    vis = get_dataframe(f"""
        SELECT
            COUNT(*)::int                      AS items,
            COUNT(DISTINCT (linea_codigo, referencia_codigo,
                            material_code, color_code))::int AS combinaciones,
            COALESCE(SUM(cantidad_pares), 0)::int AS pares
        FROM public.v_stock_rimec
        {f"WHERE pp_id = {pp_id}" if pp_id is not None else ""}
    """)

    det_row = det.iloc[0] if det is not None and not det.empty else None
    vis_row = vis.iloc[0] if vis is not None and not vis.empty else None

    if det_row is None or vis_row is None:
        _warn("No hay datos para auditar.")
        return (0, 0, 0, 0, 0, 0)

    items_det, combos_det, pares_det = int(det_row["items"]), int(det_row["combinaciones"]), int(det_row["pares"])
    items_vis, combos_vis, pares_vis = int(vis_row["items"]), int(vis_row["combinaciones"]), int(vis_row["pares"])

    resumen = pd.DataFrame([
        {"capa": "pedido_proveedor_detalle (verdad)",
         "items": items_det, "combinaciones": combos_det, "pares": pares_det},
        {"capa": "v_stock_rimec (web Rimec)",
         "items": items_vis, "combinaciones": combos_vis, "pares": pares_vis},
    ])
    _print_df(resumen)
    print()

    if items_det == items_vis and pares_det == pares_vis:
        _ok("La vista es FIEL al detalle (1:1).")
    else:
        _bug(
            f"La vista DIFIERE del detalle: "
            f"Δitems={items_vis - items_det}, Δpares={pares_vis - pares_det}"
        )

    duplicados_det = items_det - combos_det
    duplicados_vis = items_vis - combos_vis
    if duplicados_det > 0 or duplicados_vis > 0:
        _warn(
            f"Hay {duplicados_det} filas extras en pp_detalle y {duplicados_vis} en la vista "
            f"(combinaciones repetidas)."
        )

    return (items_det, combos_det, pares_det, items_vis, combos_vis, pares_vis)


def bloque_2_duplicados_vista(pp_id: int | None) -> int:
    """② Filas de v_stock_rimec con combinación repetida.

    Returns
    -------
    int
        Cantidad de combinaciones duplicadas.
    """
    _seccion("②", "Detector de DUPLICACIÓN en v_stock_rimec")

    df = get_dataframe(f"""
        SELECT linea_codigo, referencia_codigo, material_code, color_code,
               COUNT(*) AS veces_en_vista,
               SUM(cantidad_pares) AS pares_acumulados
        FROM public.v_stock_rimec
        {f"WHERE pp_id = {pp_id}" if pp_id is not None else ""}
        GROUP BY linea_codigo, referencia_codigo, material_code, color_code
        HAVING COUNT(*) > 1
        ORDER BY veces_en_vista DESC, pares_acumulados DESC
        LIMIT 30;
    """)
    _print_df(df, max_rows=30)
    n = 0 if df is None or df.empty else len(df)
    print()
    if n == 0:
        _ok("La vista no multiplica registros.")
    else:
        _warn(
            f"{n} combinaciones aparecen más de una vez en la vista. "
            "(Puede ser duplicación de la fuente, no de la vista. Ver ④.)"
        )
    return n


def bloque_3_perdida(pp_id: int | None) -> int:
    """③ SKUs presentes en pp_detalle que no aparecen en v_stock_rimec.

    Returns
    -------
    int
        Cantidad de SKUs perdidos.
    """
    _seccion("③", "Detector de PÉRDIDA (pp_detalle → vista)")

    filtro_pp = f"AND pp.id = {pp_id}" if pp_id is not None else ""
    df = get_dataframe(f"""
        SELECT ppd.id AS ppd_id,
               pp.numero_registro,
               pp.estado,
               ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code,
               ppd.cantidad_pares,
               'no aparece en v_stock_rimec' AS motivo
        FROM public.pedido_proveedor_detalle ppd
        JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        WHERE {_FILTRO_PP}
          AND COALESCE(ppd.cantidad_pares, 0) > 0
          {filtro_pp}
          AND NOT EXISTS (
              SELECT 1 FROM public.v_stock_rimec v
              WHERE v.linea_codigo      = COALESCE(ppd.linea, '')
                AND v.referencia_codigo = COALESCE(ppd.referencia, '')
                AND v.material_code     = COALESCE(ppd.material_code, '')
                AND v.color_code        = COALESCE(ppd.color_code, '')
          )
        LIMIT 30;
    """)
    _print_df(df, max_rows=30)
    n = 0 if df is None or df.empty else len(df)
    print()
    if n == 0:
        _ok("La vista no pierde registros.")
    else:
        _bug(f"{n} SKUs del detalle no aparecen en la vista. Revisar joins/filtros.")
    return n


def bloque_4_check_por_marca(pp_id: int | None) -> int:
    """④ Cruce detalle vs vista por marca.

    Returns
    -------
    int
        Cantidad de marcas con diferencia.
    """
    _seccion("④", "Cruce DETALLE vs VISTA por marca")

    filtro_pp = f"AND pp.id = {pp_id}" if pp_id is not None else ""
    filtro_v  = f"WHERE pp_id = {pp_id}" if pp_id is not None else ""
    df = get_dataframe(f"""
        WITH det AS (
            SELECT mv.descp_marca AS marca,
                   COUNT(*) AS items_pp,
                   SUM(ppd.cantidad_pares) AS pares_pp
            FROM public.pedido_proveedor_detalle ppd
            JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
            LEFT JOIN public.marca_v2 mv ON mv.id_marca = ppd.id_marca
            WHERE {_FILTRO_PP}
              AND COALESCE(ppd.cantidad_pares, 0) > 0
              {filtro_pp}
            GROUP BY mv.descp_marca
        ),
        vis AS (
            SELECT descp_marca AS marca,
                   COUNT(*) AS items_web,
                   SUM(cantidad_pares) AS pares_web
            FROM public.v_stock_rimec
            {filtro_v}
            GROUP BY descp_marca
        )
        SELECT COALESCE(det.marca, vis.marca) AS marca,
               det.items_pp, vis.items_web,
               (COALESCE(vis.items_web,0) - COALESCE(det.items_pp,0)) AS diff_items,
               det.pares_pp, vis.pares_web,
               (COALESCE(vis.pares_web,0) - COALESCE(det.pares_pp,0)) AS diff_pares
        FROM det
        FULL OUTER JOIN vis ON vis.marca = det.marca
        ORDER BY marca;
    """)
    _print_df(df)
    n_dif = 0
    if df is not None and not df.empty:
        n_dif = int(((df["diff_items"].fillna(0) != 0) | (df["diff_pares"].fillna(0) != 0)).sum())
    print()
    if n_dif == 0:
        _ok("Todas las marcas cierran (vista == detalle).")
    else:
        _bug(f"{n_dif} marcas con diferencia entre detalle y vista.")
    return n_dif


def bloque_5_pares_cero() -> int:
    """⑤ Filas en la vista con cantidad_pares = 0 o NULL."""
    _seccion("⑤", "Filas con cantidad_pares = 0 / NULL")
    df = get_dataframe("""
        SELECT COUNT(*) AS filas_con_pares_cero
        FROM public.v_stock_rimec
        WHERE cantidad_pares = 0 OR cantidad_pares IS NULL;
    """)
    _print_df(df)
    print()
    n = 0 if df is None or df.empty else int(df.iloc[0]["filas_con_pares_cero"])
    if n == 0:
        _ok("La vista filtra correctamente las filas vacías.")
    else:
        _warn(f"{n} filas con pares = 0 / NULL llegan a la vista (deberían filtrarse).")
    return n


def bloque_6_anatomia_dupes(pp_id: int | None) -> pd.DataFrame | None:
    """⑥ Anatomía de los duplicados: ¿qué los distingue?"""
    _seccion("⑥", "Anatomía de los duplicados (qué los diferencia)")

    filtro_pp = f"AND pp.id = {pp_id}" if pp_id is not None else ""
    df = get_dataframe(f"""
        WITH dupes AS (
            SELECT ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code
            FROM public.pedido_proveedor_detalle ppd
            JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
            WHERE {_FILTRO_PP}
              AND COALESCE(ppd.cantidad_pares, 0) > 0
              {filtro_pp}
            GROUP BY ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code
            HAVING COUNT(*) > 1
        )
        SELECT ppd.id AS ppd_id,
               ppd.fila_origen_f9 AS fila_excel,
               ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code,
               ppd.cantidad_cajas, ppd.cantidad_pares,
               ppd.unit_fob, ppd.unit_fob_ajustado,
               ppd.grades_json::text AS grades_json
        FROM public.pedido_proveedor_detalle ppd
        JOIN dupes d
               ON d.linea = ppd.linea
              AND d.referencia = ppd.referencia
              AND d.material_code = ppd.material_code
              AND d.color_code = ppd.color_code
        ORDER BY ppd.linea, ppd.referencia, ppd.material_code,
                 ppd.color_code, ppd.fila_origen_f9;
    """)
    _print_df(df, max_rows=80)
    print()
    if df is None or df.empty:
        _ok("No hay duplicados que diagnosticar.")
        return df

    # Heurísticas de clasificación
    grupos = df.groupby(["linea", "referencia", "material_code", "color_code"])
    n_clones = 0
    n_fob_distinto = 0
    n_grade_distinto = 0
    for _, g in grupos:
        if len(g) < 2:
            continue
        grades_unicos = g["grades_json"].nunique()
        fob_unicos    = g["unit_fob"].nunique()
        pares_unicos  = g["cantidad_pares"].nunique()
        if grades_unicos > 1:
            n_grade_distinto += 1
        elif fob_unicos > 1:
            n_fob_distinto += 1
        elif grades_unicos == 1 and fob_unicos == 1 and pares_unicos == 1:
            n_clones += 1
        else:
            n_fob_distinto += 1

    _info(f"Clones perfectos (mismo todo):                  {n_clones}")
    _info(f"Mismo SKU, FOB distinto (sospechoso ⚠):         {n_fob_distinto}")
    _info(f"Mismo SKU, grades distintos (probablemente OK): {n_grade_distinto}")

    # Detección específica: ¿la relación FOB es ~0.65?
    ratio_distinto_pero_consistente = 0
    for _, g in grupos:
        if len(g) == 2 and g["grades_json"].nunique() == 1:
            fobs = sorted(g["unit_fob"].dropna().astype(float).tolist())
            if len(fobs) == 2 and fobs[0] > 0:
                ratio = fobs[0] / fobs[1]
                if 0.60 <= ratio <= 0.70:
                    ratio_distinto_pero_consistente += 1
    if ratio_distinto_pero_consistente > 0:
        _bug(
            f"{ratio_distinto_pero_consistente} pares de duplicados con FOB en ratio ~0.65. "
            "Sospecha: el Excel manda FOB lista + FOB descontado como filas separadas."
        )
    return df


def bloque_7_pares_dup(pp_id: int | None) -> None:
    """⑦ Pares por combinación duplicada."""
    _seccion("⑦", "Pares acumulados en combinaciones duplicadas")

    filtro_pp = f"AND pp.id = {pp_id}" if pp_id is not None else ""
    df = get_dataframe(f"""
        SELECT ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code,
               COUNT(*) AS filas,
               SUM(ppd.cantidad_pares) AS pares_total,
               MIN(ppd.cantidad_pares) AS pares_min,
               MAX(ppd.cantidad_pares) AS pares_max
        FROM public.pedido_proveedor_detalle ppd
        JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        WHERE {_FILTRO_PP}
          {filtro_pp}
        GROUP BY ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code
        HAVING COUNT(*) > 1
        ORDER BY pares_total DESC
        LIMIT 30;
    """)
    _print_df(df, max_rows=30)
    print()


def bloque_8_origen_dupes(pp_id: int | None) -> None:
    """⑧ ¿Los duplicados vienen del Excel (fila_origen distinta) o del sistema?"""
    _seccion("⑧", "Origen de los duplicados: ¿Excel o sistema?")

    filtro_pp = f"AND pp.id = {pp_id}" if pp_id is not None else ""
    df = get_dataframe(f"""
        WITH dupes AS (
            SELECT ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code
            FROM public.pedido_proveedor_detalle ppd
            JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
            WHERE {_FILTRO_PP}
              {filtro_pp}
            GROUP BY ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code
            HAVING COUNT(*) > 1
        )
        SELECT ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code,
               ppd.fila_origen_f9 AS fila_excel,
               ppd.pedido_proveedor_id AS pp_id,
               ppd.cantidad_pares,
               ppd.unit_fob,
               ppd.unit_fob_ajustado,
               ppd.id AS ppd_id
        FROM public.pedido_proveedor_detalle ppd
        JOIN dupes d
               ON d.linea = ppd.linea
              AND d.referencia = ppd.referencia
              AND d.material_code = ppd.material_code
              AND d.color_code = ppd.color_code
        ORDER BY ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code,
                 ppd.fila_origen_f9
        LIMIT 80;
    """)
    _print_df(df, max_rows=80)
    print()
    if df is not None and not df.empty:
        # Si dentro de cada grupo, hay fila_excel repetida → bug del INSERT
        grupos = df.groupby(["linea", "referencia", "material_code", "color_code"])
        bug_insert = 0
        excel_diff = 0
        for _, g in grupos:
            filas = g["fila_excel"].dropna().tolist()
            if len(filas) != len(set(filas)):
                bug_insert += 1
            else:
                excel_diff += 1
        if bug_insert > 0:
            _bug(f"{bug_insert} grupos con fila_origen repetida → el sistema duplicó al insertar.")
        if excel_diff > 0:
            _warn(
                f"{excel_diff} grupos con fila_origen distinta → el Excel ya traía duplicados. "
                "Solución: deduplicar en el parser."
            )


def bloque_9_pps(pp_id: int | None) -> pd.DataFrame | None:
    """⑨ ¿Cuántos PPs tienen detalle?"""
    _seccion("⑨", "PPs presentes en pedido_proveedor_detalle")
    df = get_dataframe("""
        SELECT pedido_proveedor_id, COUNT(*) AS items,
               COALESCE(SUM(cantidad_pares), 0) AS pares
        FROM public.pedido_proveedor_detalle
        GROUP BY pedido_proveedor_id
        ORDER BY pedido_proveedor_id;
    """)
    _print_df(df)
    print()
    return df


def bloque_10_header_vs_detalle(pp_id: int | None) -> pd.DataFrame | None:
    """⑩ Header (pares_comprometidos) vs detalle (suma real)."""
    _seccion("⑩", "Header vs Detalle (pares_comprometidos vs SUM(cantidad_pares))")

    df = get_dataframe(f"""
        SELECT pp.id, pp.numero_registro, pp.estado,
               pp.pares_comprometidos AS pares_header,
               COALESCE(SUM(ppd.cantidad_pares), 0) AS pares_detalle,
               COALESCE(SUM(ppd.cantidad_pares), 0) - pp.pares_comprometidos AS diff,
               COUNT(ppd.*) AS items_detalle
        FROM public.pedido_proveedor pp
        LEFT JOIN public.pedido_proveedor_detalle ppd
               ON ppd.pedido_proveedor_id = pp.id
        {f"WHERE pp.id = {pp_id}" if pp_id is not None else ""}
        GROUP BY pp.id, pp.numero_registro, pp.estado, pp.pares_comprometidos
        ORDER BY pp.id;
    """)
    _print_df(df)
    print()
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            diff = int(row["diff"]) if pd.notna(row["diff"]) else 0
            nro  = row["numero_registro"]
            if diff == 0:
                _ok(f"{nro}: header = detalle ({row['pares_header']:,} pares).")
            elif diff > 0:
                _bug(
                    f"{nro}: detalle SUPERA al header por {diff:,} pares "
                    f"({row['pares_detalle']:,} vs {row['pares_header']:,}). "
                    "Posible duplicación al cargar."
                )
            else:
                _warn(
                    f"{nro}: detalle MENOR al header por {abs(diff):,} pares "
                    f"({row['pares_detalle']:,} vs {row['pares_header']:,}). "
                    "Carga parcial o filtrada."
                )
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auditoría de integridad pp_detalle ↔ v_stock_rimec"
    )
    parser.add_argument(
        "--pp-id", type=int, default=None,
        help="Filtrar por un pedido_proveedor.id puntual. Por defecto, todos los abiertos/enviados."
    )
    parser.add_argument(
        "--solo-dupes", action="store_true",
        help="Solo correr los bloques relacionados con duplicados (⑥⑦⑧)."
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Sin códigos ANSI de color (útil para CI / archivos)."
    )
    args = parser.parse_args()

    if args.no_color:
        _disable_colors()

    print()
    print(f"{_C.BOLD}{_C.MAGENTA}{'═' * 78}{_C.RESET}")
    print(f"{_C.BOLD}{_C.MAGENTA}  AUDITORÍA DE INTEGRIDAD: pedido_proveedor → v_stock_rimec{_C.RESET}")
    if args.pp_id is not None:
        print(f"{_C.BOLD}{_C.MAGENTA}  Filtro: pp.id = {args.pp_id}{_C.RESET}")
    print(f"{_C.BOLD}{_C.MAGENTA}{'═' * 78}{_C.RESET}")

    if args.solo_dupes:
        bloque_6_anatomia_dupes(args.pp_id)
        bloque_7_pares_dup(args.pp_id)
        bloque_8_origen_dupes(args.pp_id)
        return

    bloque_1_resumen_global(args.pp_id)
    bloque_2_duplicados_vista(args.pp_id)
    bloque_3_perdida(args.pp_id)
    bloque_4_check_por_marca(args.pp_id)
    bloque_5_pares_cero()
    bloque_6_anatomia_dupes(args.pp_id)
    bloque_7_pares_dup(args.pp_id)
    bloque_8_origen_dupes(args.pp_id)
    bloque_9_pps(args.pp_id)
    bloque_10_header_vs_detalle(args.pp_id)

    print()
    print(f"{_C.BOLD}{_C.MAGENTA}{'═' * 78}{_C.RESET}")
    print(f"{_C.BOLD}{_C.MAGENTA}  FIN DE LA AUDITORÍA{_C.RESET}")
    print(f"{_C.BOLD}{_C.MAGENTA}{'═' * 78}{_C.RESET}")


if __name__ == "__main__":
    main()
