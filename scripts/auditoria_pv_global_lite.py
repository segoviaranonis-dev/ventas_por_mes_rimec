"""Auditoría PV global — versión liviana."""
from __future__ import annotations

import json
from collections import Counter

from core.database import get_dataframe
from modules.aprobacion_pedidos.logic import get_fi_confirmadas

def q(sql):
    df = get_dataframe(sql)
    return df if df is not None else __import__("pandas").DataFrame()


print("=== 1. CONTEOS ===")
df1 = q("""
    SELECT estado, COUNT(*) n, COUNT(pv_global) con_pv,
           MIN(pv_global) min_pv, MAX(pv_global) max_pv
    FROM factura_interna
    GROUP BY estado ORDER BY estado
""")
print(df1.to_string(index=False))

print("\n=== 2. NUMERADAS (CONFIRMADA+ANULADA) ===")
df2 = q("""
    SELECT COUNT(*) AS total_numeradas,
           MAX(pv_global) AS max_pv,
           MIN(pv_global) AS min_pv
    FROM factura_interna WHERE pv_global IS NOT NULL
""")
print(df2.to_string(index=False))

print("\n=== 3. ERRORES NUMERACIÓN ===")
df3 = q("""
    SELECT 'CONFIRMADA sin pv' AS e, COUNT(*) n FROM factura_interna
      WHERE estado='CONFIRMADA' AND pv_global IS NULL
    UNION ALL SELECT 'ANULADA sin pv', COUNT(*) FROM factura_interna
      WHERE estado='ANULADA' AND pv_global IS NULL
    UNION ALL SELECT 'RESERVADA con pv', COUNT(*) FROM factura_interna
      WHERE estado='RESERVADA' AND pv_global IS NOT NULL
    UNION ALL SELECT 'duplicados pv', COUNT(*) FROM (
      SELECT pv_global FROM factura_interna WHERE pv_global IS NOT NULL
      GROUP BY pv_global HAVING COUNT(*)>1
    ) x
""")
print(df3.to_string(index=False))

print("\n=== 4. HUECOS en secuencia ===")
df4 = q("""
    WITH bounds AS (
      SELECT MIN(pv_global) mn, MAX(pv_global) mx
      FROM factura_interna WHERE pv_global IS NOT NULL
    ),
    series AS (
      SELECT generate_series(mn, mx) expected FROM bounds
    )
    SELECT COUNT(*) AS huecos
    FROM series s
    LEFT JOIN factura_interna fi ON fi.pv_global = s.expected
    WHERE fi.id IS NULL
""")
print(df4.to_string(index=False))

print("\n=== 5. UI vs BD confirmadas ===")
ui = get_fi_confirmadas()
db_n = q("SELECT COUNT(*) n FROM factura_interna WHERE estado='CONFIRMADA'").iloc[0]["n"]
print(f"UI: {len(ui)} | BD: {db_n}")

print("\n=== 6. INTEGRIDAD (agregado) ===")
df6 = q("""
    SELECT
      SUM(CASE WHEN fi.pv_global IS NULL THEN 1 ELSE 0 END) AS sin_pv,
      SUM(CASE WHEN NOT EXISTS (
        SELECT 1 FROM factura_interna_detalle d WHERE d.factura_id=fi.id
      ) THEN 1 ELSE 0 END) AS sin_items,
      SUM(CASE WHEN fi.pedido_id IS NULL THEN 1 ELSE 0 END) AS sin_pedido,
      SUM(CASE WHEN p.id IS NOT NULL AND p.estado NOT IN ('CONFIRMADO','EDITADO') THEN 1 ELSE 0 END) AS pedido_mal_estado,
      COUNT(*) AS total
    FROM factura_interna fi
    LEFT JOIN pedido_venta_rimec p ON p.id = fi.pedido_id
    WHERE fi.estado = 'CONFIRMADA'
""")
print(df6.to_string(index=False))

print("\n=== 7. ANULADAS numeradas ===")
df7 = q("""
    SELECT pv_global, id, nro_factura, estado
    FROM factura_interna WHERE estado='ANULADA' ORDER BY pv_global
""")
print(df7.to_string(index=False))

print("\n=== 8. RESERVADA (sin pv esperado) ===")
df8 = q("""
    SELECT id, nro_factura, pv_global, pedido_id
    FROM factura_interna WHERE estado='RESERVADA'
""")
print(df8.to_string(index=False))

print("\n=== 9. TOP incidencias detalle (pares/monto) ===")
df9 = q("""
    SELECT fi.id, fi.pv_global, fi.total_pares, fi.total_monto,
           COALESCE(SUM(d.pares),0) sum_pares,
           COALESCE(SUM(d.subtotal),0) sum_monto
    FROM factura_interna fi
    LEFT JOIN factura_interna_detalle d ON d.factura_id = fi.id
    WHERE fi.estado = 'CONFIRMADA'
    GROUP BY fi.id, fi.pv_global, fi.total_pares, fi.total_monto
    HAVING ABS(COALESCE(SUM(d.pares),0) - COALESCE(fi.total_pares,0)) > 0
        OR ABS(COALESCE(SUM(d.subtotal),0) - COALESCE(fi.total_monto,0)) > 1
    ORDER BY fi.pv_global
    LIMIT 20
""")
if df9.empty:
    print("Ninguna discrepancia pares/monto en cabecera vs detalle")
else:
    print(df9.to_string(index=False))

print("\n=== RESUMEN ===")
max_pv = int(df2.iloc[0]["max_pv"]) if not df2.empty and df2.iloc[0]["max_pv"] else None
total_num = int(df2.iloc[0]["total_numeradas"]) if not df2.empty else 0
conf = int(df1[df1["estado"]=="CONFIRMADA"]["n"].iloc[0]) if not df1.empty else 0
anul = int(df1[df1["estado"]=="ANULADA"]["n"].iloc[0]) if not df1.empty and "ANULADA" in df1["estado"].values else 0
print(json.dumps({
    "max_pv_global": max_pv,
    "numeradas_total": total_num,
    "confirmadas": conf,
    "anuladas": anul,
    "ui_confirmadas": len(ui),
    "explicacion_147": "MAX(pv_global)=147 incluye CONFIRMADA+ANULADA; UI Confirmadas solo muestra CONFIRMADA (145)",
}, indent=2))

print("\n=== 10. LISTA COMPLETA 147 NUMERADAS ===")
df10 = q("""
    SELECT
      fi.pv_global,
      'PV' || LPAD(fi.pv_global::text, 6, '0') AS pv,
      fi.id AS fi_id,
      fi.nro_factura AS legacy,
      fi.estado,
      fi.pedido_id,
      p.nro_pedido,
      p.estado AS pedido_estado,
      fi.marca,
      fi.caso,
      fi.total_pares,
      fi.total_monto,
      c.descp_cliente AS cliente
    FROM factura_interna fi
    LEFT JOIN pedido_venta_rimec p ON p.id = fi.pedido_id
    LEFT JOIN cliente_v2 c ON c.id_cliente = fi.cliente_id
    WHERE fi.pv_global IS NOT NULL
    ORDER BY fi.pv_global
""")
out = "scripts/auditoria_pv_global_export.csv"
df10.to_csv(out, index=False)
print(f"Export: {out} ({len(df10)} filas)")

print("\n=== 11. MONTO cabecera vs detalle (CONFIRMADA) ===")
df11 = q("""
    SELECT fi.pv_global, fi.id, fi.total_monto, fi.total_pares,
           fi.descuento_1, fi.descuento_2, s.sum_det, s.sum_pares
    FROM factura_interna fi
    JOIN LATERAL (
      SELECT SUM(subtotal) sum_det, SUM(pares) sum_pares
      FROM factura_interna_detalle WHERE factura_id = fi.id
    ) s ON true
    WHERE fi.estado = 'CONFIRMADA'
      AND (ABS(s.sum_pares - COALESCE(fi.total_pares,0)) > 0
           OR ABS(s.sum_det - COALESCE(fi.total_monto,0)) > 1)
    ORDER BY fi.pv_global
""")
print(f"Incidencias: {len(df11)}")
if not df11.empty:
    print(df11.to_string(index=False))
