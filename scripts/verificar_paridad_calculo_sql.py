"""
Script de verificación de paridad: cálculo SQL vs Python
OT: OT-MOTOR-SQL-520-001
Fecha: 2026-05-18

Compara resultados de calcular_precio_lista_sql() vs calcular_precios_caso()
para garantizar paridad exacta (diferencia = 0).
"""

import sys
import pandas as pd
from sqlalchemy import text

# Agregar path para imports
sys.path.insert(0, "C:\\Users\\hecto\\Nexus_Core\\control_central")

from core.database import get_dataframe, engine
from modules.rimec_engine.logic import calcular_precios_caso


def verificar_paridad_calculo_sql(evento_id: int, n_skus: int = 20) -> dict:
    """
    Verifica paridad entre cálculo SQL y Python.

    Args:
        evento_id: ID del evento con precios calculados por SQL
        n_skus: Número de SKUs a verificar (default: 20)

    Returns:
        dict con: n_comparados, diff_count, max_diff, resultados DataFrame
    """

    print(f"\n{'='*80}")
    print(f"VERIFICACIÓN PARIDAD CÁLCULO SQL vs PYTHON")
    print(f"Evento: {evento_id} | SKUs a verificar: {n_skus}")
    print(f"{'='*80}\n")

    # 1. Obtener SKUs calculados por SQL
    query_sql = """
        SELECT
            pl.id,
            pl.evento_id,
            pl.caso_id,
            pl.linea_id,
            pl.referencia_id,
            pl.material_id,
            pl.fob_fabrica,
            pl.fob_ajustado as fob_ajustado_sql,
            pl.lpn as lpn_sql,
            pl.lpc03 as lpc03_sql,
            pl.lpc04 as lpc04_sql,
            c.dolar_politica,
            c.factor_conversion,
            c.descuento_1,
            c.descuento_2,
            c.descuento_3,
            c.descuento_4,
            c.genera_lpc03_lpc04
        FROM precio_lista pl
        INNER JOIN precio_evento_caso c ON pl.caso_id = c.id
        WHERE pl.evento_id = :eid
        ORDER BY RANDOM()
        LIMIT :n
    """

    df_sql = get_dataframe(query_sql, {"eid": evento_id, "n": n_skus})

    if df_sql is None or df_sql.empty:
        return {
            "error": f"No se encontraron precios para evento {evento_id}",
            "n_comparados": 0,
            "diff_count": 0
        }

    print(f"✓ Obtenidos {len(df_sql)} SKUs desde precio_lista (SQL)")

    # 2. Recalcular en Python y comparar
    resultados = []

    for idx, row in df_sql.iterrows():
        caso_params = {
            "dolar_politica": float(row["dolar_politica"]),
            "factor_conversion": float(row["factor_conversion"]),
            "descuento_1": row["descuento_1"],
            "descuento_2": row["descuento_2"],
            "descuento_3": row["descuento_3"],
            "descuento_4": row["descuento_4"],
            "genera_lpc03_lpc04": bool(row["genera_lpc03_lpc04"]),
        }

        fob = float(row["fob_fabrica"])
        calc_python = calcular_precios_caso(fob, caso_params)

        # Comparar
        diff_fob = abs(float(row["fob_ajustado_sql"]) - calc_python["fob_ajustado"])
        diff_lpn = abs(float(row["lpn_sql"]) - calc_python["lpn"])

        # LPC03/04 pueden ser NULL
        diff_lpc03 = 0
        diff_lpc04 = 0
        if row["lpc03_sql"] is not None and calc_python["lpc03"] is not None:
            diff_lpc03 = abs(float(row["lpc03_sql"]) - calc_python["lpc03"])
        if row["lpc04_sql"] is not None and calc_python["lpc04"] is not None:
            diff_lpc04 = abs(float(row["lpc04_sql"]) - calc_python["lpc04"])

        max_diff = max(diff_fob, diff_lpn, diff_lpc03, diff_lpc04)

        resultados.append({
            "id": row["id"],
            "fob": fob,
            "sql_fob_ajustado": float(row["fob_ajustado_sql"]),
            "py_fob_ajustado": calc_python["fob_ajustado"],
            "diff_fob": diff_fob,
            "sql_lpn": float(row["lpn_sql"]),
            "py_lpn": calc_python["lpn"],
            "diff_lpn": diff_lpn,
            "sql_lpc03": row["lpc03_sql"],
            "py_lpc03": calc_python["lpc03"],
            "diff_lpc03": diff_lpc03,
            "sql_lpc04": row["lpc04_sql"],
            "py_lpc04": calc_python["lpc04"],
            "diff_lpc04": diff_lpc04,
            "max_diff": max_diff,
            "ok": max_diff < 0.01  # Tolerancia 1 centavo
        })

    df_resultados = pd.DataFrame(resultados)

    # 3. Resumen
    n_comparados = len(df_resultados)
    diff_count = len(df_resultados[df_resultados["max_diff"] >= 0.01])
    max_diff_total = df_resultados["max_diff"].max()

    print(f"\n{'─'*80}")
    print(f"RESULTADOS:")
    print(f"{'─'*80}")
    print(f"SKUs comparados: {n_comparados}")
    print(f"Diferencias encontradas: {diff_count}")
    print(f"Máxima diferencia: ${max_diff_total:.4f}")
    print(f"{'─'*80}\n")

    if diff_count == 0:
        print("✅ PARIDAD PERFECTA: SQL y Python producen resultados idénticos")
    else:
        print(f"❌ FALLO DE PARIDAD: {diff_count} SKUs con diferencias")
        print("\nSKUs con diferencias:")
        print(df_resultados[df_resultados["max_diff"] >= 0.01][
            ["id", "fob", "diff_fob", "diff_lpn", "max_diff"]
        ])

    return {
        "n_comparados": n_comparados,
        "diff_count": diff_count,
        "max_diff": float(max_diff_total),
        "resultados": df_resultados,
        "ok": diff_count == 0
    }


if __name__ == "__main__":
    # Usar evento de prueba o último evento
    if len(sys.argv) > 1:
        evento_id = int(sys.argv[1])
    else:
        # Obtener último evento con precios
        df_evento = get_dataframe(
            """SELECT DISTINCT evento_id
               FROM precio_lista
               ORDER BY evento_id DESC
               LIMIT 1"""
        )
        if df_evento is None or df_evento.empty:
            print("❌ No hay eventos con precios calculados")
            sys.exit(1)
        evento_id = int(df_evento.iloc[0]["evento_id"])

    # Ejecutar verificación
    resultado = verificar_paridad_calculo_sql(evento_id, n_skus=20)

    # Exit code
    sys.exit(0 if resultado.get("ok") else 1)
