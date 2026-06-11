"""Backfill pedido_venta_rimec PENDIENTE → CONFIRMADO (orden ORDEN_CURSOR_BACKFILL_PEDIDOS)."""
from core.database import get_dataframe, engine
from sqlalchemy import text as sqlt

SQL_DIAG = """
SELECT
    pvr.id AS pedido_id,
    pvr.nro_pedido,
    pvr.estado AS estado_pedido,
    COUNT(fi.id) AS total_fis,
    SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) AS fis_confirmadas
FROM pedido_venta_rimec pvr
LEFT JOIN factura_interna fi ON fi.pedido_id = pvr.id
WHERE pvr.estado = 'PENDIENTE'
  AND EXISTS (SELECT 1 FROM factura_interna WHERE pedido_id = pvr.id)
GROUP BY pvr.id, pvr.nro_pedido, pvr.estado
HAVING
    COUNT(fi.id) > 0
    AND SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) = COUNT(fi.id)
ORDER BY pvr.id
"""

SQL_BACKFILL = """
WITH pedidos_a_confirmar AS (
    SELECT pvr.id AS pedido_id
    FROM pedido_venta_rimec pvr
    INNER JOIN factura_interna fi ON fi.pedido_id = pvr.id
    WHERE pvr.estado = 'PENDIENTE'
    GROUP BY pvr.id
    HAVING
        COUNT(fi.id) > 0
        AND SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) = COUNT(fi.id)
)
UPDATE pedido_venta_rimec pvr
SET estado = 'CONFIRMADO'
FROM pedidos_a_confirmar pac
WHERE pvr.id = pac.pedido_id
  AND pvr.estado = 'PENDIENTE'
RETURNING pvr.id, pvr.nro_pedido, pvr.estado
"""

SQL_CHECK = """
SELECT
    pvr.id,
    pvr.nro_pedido,
    pvr.estado,
    COUNT(fi.id) AS total_fis,
    STRING_AGG(DISTINCT fi.estado, ', ') AS estados_fis
FROM pedido_venta_rimec pvr
LEFT JOIN factura_interna fi ON fi.pedido_id = pvr.id
WHERE pvr.estado = 'PENDIENTE'
  AND EXISTS (
    SELECT 1 FROM factura_interna
    WHERE pedido_id = pvr.id AND estado = 'CONFIRMADA'
  )
GROUP BY pvr.id, pvr.nro_pedido, pvr.estado
HAVING
    COUNT(fi.id) > 0
    AND SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) = COUNT(fi.id)
"""


def main() -> None:
    print("=== PASO 1: DIAGNÓSTICO ===")
    df = get_dataframe(SQL_DIAG)
    n_diag = 0 if df is None or df.empty else len(df)
    print(f"Pedidos desincronizados: {n_diag}")
    if n_diag:
        print(df.to_string(index=False))

    print("\n=== PASO 2: BACKFILL ===")
    with engine.begin() as conn:
        result = conn.execute(sqlt(SQL_BACKFILL))
        rows = result.fetchall()
    print(f"Pedidos actualizados: {len(rows)}")
    for row in rows:
        print(f"  {row.nro_pedido} → {row.estado}")

    print("\n=== PASO 3: ESTADOS ===")
    df_estados = get_dataframe("""
        SELECT estado, COUNT(*) AS cantidad
        FROM pedido_venta_rimec
        GROUP BY estado
        ORDER BY estado
    """)
    print(df_estados.to_string(index=False) if df_estados is not None else "FAIL")

    print("\n=== VERIFICACIÓN FINAL ===")
    df_check = get_dataframe(SQL_CHECK)
    n_rest = 0 if df_check is None or df_check.empty else len(df_check)
    if n_rest == 0:
        print("OK: No hay pedidos desincronizados")
    else:
        print(f"ERROR: Aún hay {n_rest} pedidos desincronizados")
        print(df_check.to_string(index=False))


if __name__ == "__main__":
    main()
