"""
OT-004 Paso 3: Listar PPs con SKUs sin precio
"""

import psycopg2

conn = psycopg2.connect(
    host='aws-1-sa-east-1.pooler.supabase.com',
    port=6543,
    dbname='postgres',
    user='postgres.extrlcvcgypwazxipvqm',
    password='IJoFJbT8Qj0Q0w5m'
)
cur = conn.cursor()

print("="*70)
print("OT-004 PASO 3: PPs con SKUs sin Precio")
print("="*70)
print()

cur.execute("""
    SELECT
      pp.id,
      pp.numero_registro AS pp_nro,
      pp.estado,
      pp.fecha_arribo_estimada::date AS eta,
      COUNT(DISTINCT vs.det_id) FILTER (WHERE vs.lpn IS NULL)             AS sku_sin_precio,
      COUNT(DISTINCT vs.det_id)                                            AS sku_total,
      ARRAY_AGG(DISTINCT icp.precio_evento_id) FILTER (WHERE icp.precio_evento_id IS NOT NULL) AS eventos_vigentes
    FROM pedido_proveedor pp
    JOIN v_stock_rimec vs ON vs.pp_id = pp.id
    LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
    WHERE pp.estado IN ('ABIERTO','ENVIADO')
    GROUP BY pp.id, pp.numero_registro, pp.estado, pp.fecha_arribo_estimada
    HAVING COUNT(DISTINCT vs.det_id) FILTER (WHERE vs.lpn IS NULL) > 0
    ORDER BY sku_sin_precio DESC
    LIMIT 50
""")

rows = cur.fetchall()

print(f"Total PPs con SKUs sin precio: {len(rows)}")
print()

if rows:
    print("Detalle (top 50):")
    print("-"*110)
    print(f"{'ID':<6} {'Numero':<15} {'Estado':<10} {'ETA':<12} {'Sin Precio':<12} {'Total SKUs':<12} {'Eventos'}")
    print("-"*110)

    for row in rows:
        pp_id, pp_nro, estado, eta, sin_precio, total, eventos = row
        eta_str = str(eta) if eta else 'N/A'
        eventos_str = str(eventos) if eventos and eventos != [None] else 'SIN EVENTO'

        print(f"{pp_id:<6} {pp_nro:<15} {estado:<10} {eta_str:<12} {sin_precio:<12} {total:<12} {eventos_str}")

    print("-"*110)
    print()

    # Analizar diagnóstico
    sin_evento = sum(1 for r in rows if not r[6] or r[6] == [None])
    con_evento = len(rows) - sin_evento

    print("Diagnostico:")
    print(f"  PPs SIN evento asignado: {sin_evento}")
    print(f"  PPs CON evento pero SKUs sin precio: {con_evento}")
    print()

    if sin_evento > 0:
        print("ACCION REQUERIDA:")
        print("  - Asignar precio_evento_id desde Streamlit (modulo digitacion)")
        print(f"  - PPs afectados: {[r[0] for r in rows if not r[6] or r[6] == [None]]}")
else:
    print("No se encontraron PPs con SKUs sin precio")

conn.close()
