"""
OT-WEB-PRECIO-509-001 T2: Auditar SKUs sin caso, sin regla, o sin LPN.

Detecta problemas que impedirían calcular precio_web correctamente:
- SKUs sin nombre_caso_aplicado en precio_lista
- Casos sin regla en caso_precio_web_regla
- SKUs sin LPN (no puede calcular precio_web)
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from core.database import get_dataframe


def main() -> bool:
    print("=" * 80)
    print("OT-509: AUDITORIA PRECIO WEB POR CASOS")
    print("=" * 80)
    print()

    # ── C1: SKUs sin caso en precio_lista ────────────────────────────────────
    print("[C1] SKUs con lpn pero sin nombre_caso_aplicado:")
    df_sin_caso = get_dataframe("""
        SELECT
            pl.evento_id,
            pe.nombre_evento,
            l.codigo_proveedor AS linea,
            r.codigo_proveedor AS referencia,
            m.descripcion AS material,
            pl.lpn,
            pl.nombre_caso_aplicado
        FROM precio_lista pl
        JOIN precio_evento pe ON pe.id = pl.evento_id
        LEFT JOIN linea l ON l.id = pl.linea_id
        LEFT JOIN referencia r ON r.id = pl.referencia_id
        LEFT JOIN material m ON m.id = pl.material_id
        WHERE pl.lpn IS NOT NULL
          AND (pl.nombre_caso_aplicado IS NULL OR TRIM(pl.nombre_caso_aplicado) = '')
        ORDER BY pl.evento_id, l.codigo_proveedor, r.codigo_proveedor
        LIMIT 20
    """)

    if df_sin_caso is not None and not df_sin_caso.empty:
        print(f"  Total: {len(df_sin_caso)} líneas (mostrando primeras 20)")
        print(df_sin_caso.to_string(index=False))
        print()
        print("  [WARN] Estos SKUs usarán regla DEFAULT (+50%) en precio_web")
    else:
        print("  PASS - Todos los SKUs con LPN tienen caso asignado")
    print()

    # ── C2: Casos en precio_lista sin regla en caso_precio_web_regla ─────────
    print("[C2] Casos en precio_lista sin regla de markup:")
    df_casos_sin_regla = get_dataframe("""
        SELECT DISTINCT
            pl.nombre_caso_aplicado AS caso,
            COUNT(*) AS lineas_precio_lista
        FROM precio_lista pl
        WHERE pl.nombre_caso_aplicado IS NOT NULL
          AND TRIM(pl.nombre_caso_aplicado) != ''
          AND NOT EXISTS (
              SELECT 1 FROM caso_precio_web_regla cpr
              WHERE UPPER(TRIM(cpr.caso_codigo)) = UPPER(TRIM(pl.nombre_caso_aplicado))
                AND cpr.activo = true
          )
        GROUP BY pl.nombre_caso_aplicado
        ORDER BY COUNT(*) DESC
    """)

    if df_casos_sin_regla is not None and not df_casos_sin_regla.empty:
        print(f"  Total: {len(df_casos_sin_regla)} casos")
        print(df_casos_sin_regla.to_string(index=False))
        print()
        print("  [WARN] Estos casos usarán regla DEFAULT (+50%) en precio_web")
        print("  [ACCION] Agregar reglas en módulo 'Diccionario Web' de Nexus")
    else:
        print("  PASS - Todos los casos tienen regla de markup activa")
    print()

    # ── C3: SKUs en v_stock_rimec sin LPN (no puede calcular precio_web) ─────
    print("[C3] SKUs en catálogo web sin LPN:")
    df_sin_lpn = get_dataframe("""
        SELECT
            linea_codigo,
            referencia_codigo,
            descp_material,
            descp_color,
            caso_precio,
            lpn,
            precio_web
        FROM v_stock_rimec
        WHERE lpn IS NULL
        ORDER BY linea_codigo, referencia_codigo
        LIMIT 20
    """)

    if df_sin_lpn is not None and not df_sin_lpn.empty:
        print(f"  Total: {len(df_sin_lpn)} SKUs (mostrando primeros 20)")
        print(df_sin_lpn.to_string(index=False))
        print()
        print("  [ERROR] Estos SKUs no tendrán precio_web (lpn=NULL, precio_web=NULL)")
        print("  [ACCION] Revisar por qué no tienen LPN en precio_lista")
    else:
        print("  PASS - Todos los SKUs en catálogo tienen LPN")
    print()

    # ── C4: Resumen estadísticas precio_web ──────────────────────────────────
    print("[C4] Estadísticas precio_web en catálogo:")
    df_stats = get_dataframe("""
        SELECT
            COUNT(*) AS total_skus,
            COUNT(lpn) AS con_lpn,
            COUNT(caso_precio) AS con_caso,
            COUNT(precio_web) AS con_precio_web,
            COUNT(markup_pct_aplicado) AS con_markup,
            ROUND(AVG(precio_web), 0) AS precio_web_promedio,
            ROUND(AVG(markup_pct_aplicado), 2) AS markup_promedio
        FROM v_stock_rimec
    """)

    if df_stats is not None and not df_stats.empty:
        row = df_stats.iloc[0]
        print(f"  Total SKUs en catálogo: {row['total_skus']}")
        print(f"  Con LPN: {row['con_lpn']} ({100*row['con_lpn']/row['total_skus']:.1f}%)")
        print(f"  Con caso asignado: {row['con_caso']} ({100*row['con_caso']/row['total_skus']:.1f}%)")
        print(f"  Con precio_web: {row['con_precio_web']} ({100*row['con_precio_web']/row['total_skus']:.1f}%)")
        print(f"  Precio web promedio: {row['precio_web_promedio']:.0f} Gs")
        print(f"  Markup promedio: {row['markup_promedio']:.2f}%")
    print()

    # ── C5: Sample precio_web calculado por caso ─────────────────────────────
    print("[C5] Muestra precio_web por caso (primeros 5 de cada caso):")
    df_sample = get_dataframe("""
        WITH ranked AS (
            SELECT
                linea_codigo,
                referencia_codigo,
                caso_precio,
                lpn,
                precio_web,
                markup_pct_aplicado,
                ROW_NUMBER() OVER (PARTITION BY caso_precio ORDER BY det_id) AS rn
            FROM v_stock_rimec
            WHERE precio_web IS NOT NULL
        )
        SELECT
            caso_precio,
            linea_codigo,
            referencia_codigo,
            lpn,
            precio_web,
            markup_pct_aplicado
        FROM ranked
        WHERE rn <= 2
        ORDER BY caso_precio, linea_codigo, referencia_codigo
    """)

    if df_sample is not None and not df_sample.empty:
        print(df_sample.to_string(index=False))
    else:
        print("  [WARN] No hay SKUs con precio_web calculado")
    print()

    print("=" * 80)
    print("[RESUMEN]")

    count_sin_caso = len(df_sin_caso) if df_sin_caso is not None and not df_sin_caso.empty else 0
    count_casos_sin_regla = len(df_casos_sin_regla) if df_casos_sin_regla is not None and not df_casos_sin_regla.empty else 0
    count_sin_lpn = len(df_sin_lpn) if df_sin_lpn is not None and not df_sin_lpn.empty else 0

    if count_sin_caso > 0:
        print(f"  [WARN] {count_sin_caso} SKUs sin caso (usarán DEFAULT +50%)")
    if count_casos_sin_regla > 0:
        print(f"  [WARN] {count_casos_sin_regla} casos sin regla (usarán DEFAULT +50%)")
    if count_sin_lpn > 0:
        print(f"  [ERROR] {count_sin_lpn} SKUs sin LPN (no tendrán precio_web)")

    if count_sin_caso == 0 and count_casos_sin_regla == 0 and count_sin_lpn == 0:
        print("  PASS - Sistema precio_web OK para todos los SKUs")

    print("=" * 80)
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
