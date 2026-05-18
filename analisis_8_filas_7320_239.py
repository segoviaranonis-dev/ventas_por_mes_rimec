"""
Investigar por qué 7320/239 tiene 8 det_id distintos
"""
import psycopg2
import json

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("=" * 80)
print("ANALISIS DETALLADO: Por que hay 8 filas para 7320/239")
print("=" * 80)

# Ver todos los campos relevantes
cur.execute("""
    SELECT det_id, pp_id, pp_nro, descp_color, color_code,
           cantidad_cajas, cantidad_pares, grades_json::text,
           proforma, eta
    FROM v_stock_rimec
    WHERE linea_codigo = '7320' AND referencia_codigo = '239'
    ORDER BY pp_id, descp_color, det_id
""")
rows = cur.fetchall()

print(f"\nTotal registros: {len(rows)}\n")
print("det_id | pp_id | pp_nro  | color      | color_code | cj | pares | grades_json                | proforma | eta")
print("-" * 140)
for r in rows:
    grades_short = r[7][:30] + "..." if r[7] and len(r[7]) > 30 else (r[7] or "NULL")
    print(f"{r[0]:6} | {r[1]:5} | {r[2]:7} | {r[3]:10} | {r[4]:10} | {r[5]:2} | {r[6]:5} | {grades_short:26} | {r[8]:8} | {r[9] or 'NULL':10}")

# Agrupar por PP
print("\n" + "=" * 80)
print("AGRUPACION POR PEDIDO PROVEEDOR")
print("=" * 80)
cur.execute("""
    SELECT pp_id, pp_nro, proforma, COUNT(*) as n_filas,
           COUNT(DISTINCT descp_color) as n_colores,
           COUNT(DISTINCT grades_json::text) as n_grades_distintos
    FROM v_stock_rimec
    WHERE linea_codigo = '7320' AND referencia_codigo = '239'
    GROUP BY pp_id, pp_nro, proforma
    ORDER BY pp_id
""")
pp_summary = cur.fetchall()
print(f"\nTotal PP distintos: {len(pp_summary)}\n")
print("pp_id | pp_nro  | proforma | filas | colores | grades_distintos")
print("-" * 70)
for p in pp_summary:
    print(f"{p[0]:5} | {p[1]:7} | {p[2]:8} | {p[3]:5} | {p[4]:7} | {p[5]:16}")

# Ver grades_json completos
print("\n" + "=" * 80)
print("GRADES_JSON COMPLETOS (para verificar si son identicos)")
print("=" * 80)
cur.execute("""
    SELECT det_id, descp_color, grades_json
    FROM v_stock_rimec
    WHERE linea_codigo = '7320' AND referencia_codigo = '239'
    ORDER BY descp_color, det_id
""")
grades_rows = cur.fetchall()
for r in grades_rows:
    grades_dict = r[2] if r[2] else {}
    grades_str = json.dumps(grades_dict, ensure_ascii=False, sort_keys=True) if grades_dict else "NULL"
    print(f"det_id {r[0]:3} | {r[1]:12} | {grades_str}")

# Verificar en tabla base sin vista
print("\n" + "=" * 80)
print("TABLA BASE pedido_proveedor_detalle (sin JOINs de vista)")
print("=" * 80)
cur.execute("""
    SELECT ppd.id, pp.numero_registro, ppd.descp_color,
           ppd.cantidad_cajas, ppd.cantidad_pares,
           ppd.grades_json::text,
           pp.numero_proforma
    FROM pedido_proveedor_detalle ppd
    JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
    WHERE ppd.linea = '7320' AND ppd.referencia = '239'
      AND pp.estado IN ('ABIERTO', 'ENVIADO')
    ORDER BY pp.numero_registro, ppd.descp_color, ppd.id
""")
base_rows = cur.fetchall()
print(f"\nTotal en tabla base: {len(base_rows)}")
print("id  | pp_nro  | color      | cj | pares | grades (primeros 40 chars) | proforma")
print("-" * 110)
for r in base_rows:
    grades_preview = r[5][:40] if r[5] else "NULL"
    print(f"{r[0]:3} | {r[1]:7} | {r[2]:10} | {r[3]:2} | {r[4]:5} | {grades_preview:40} | {r[6]}")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)

if len(pp_summary) > 1:
    print(f"✓ MEZCLA DE PP: {len(pp_summary)} pedidos distintos en misma tarjeta")
    print("  Causa: agruparProductos() no incluye pp_id en prodKey")
    print(f"  Solucion: Decidir si mostrar todos los PP o filtrar por PP activo/mas reciente")
elif len(base_rows) == 8 and len(set(r[5] for r in base_rows)) == 8:
    print("✓ GRADES DISTINTOS: 8 combinaciones de tallas diferentes")
    print("  Cada fila es una combinacion unica de tallas (grades_json distinto)")
    print("  Comportamiento correcto: el catálogo debe mostrar 8 variantes")
elif len(base_rows) == 8 and len(set(r[5] for r in base_rows)) < 8:
    print("✗ DUPLICACION EN EXCEL/IMPORT: Mismos grades repetidos")
    print("  Causa probable: error en Excel o import multiple del mismo archivo")
    print("  Solucion: Limpiar datos duplicados en pedido_proveedor_detalle")
else:
    print(f"? Caso no identificado claramente. Revisar datos manualmente.")
    print(f"  - Total filas: {len(base_rows)}")
    print(f"  - PP distintos: {len(pp_summary)}")
    print(f"  - Grades distintos: {len(set(r[5] for r in base_rows))}")

cur.close()
conn.close()
