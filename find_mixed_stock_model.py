import psycopg2

conn = psycopg2.connect('postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
cur = conn.cursor()

# Find models with multiple colors where only some have stock
cur.execute("""
WITH color_stock AS (
  SELECT
    linea_codigo, referencia_codigo, material_code,
    descp_color, color_code,
    SUM(cantidad_cajas) as total_cajas
  FROM v_stock_rimec
  GROUP BY linea_codigo, referencia_codigo, material_code, descp_color, color_code
),
modelo_summary AS (
  SELECT
    linea_codigo, referencia_codigo, material_code,
    COUNT(*) as total_colores,
    SUM(CASE WHEN total_cajas > 0 THEN 1 ELSE 0 END) as colores_con_stock,
    SUM(CASE WHEN total_cajas = 0 THEN 1 ELSE 0 END) as colores_sin_stock
  FROM color_stock
  GROUP BY linea_codigo, referencia_codigo, material_code
  HAVING COUNT(*) > 1 AND SUM(CASE WHEN total_cajas = 0 THEN 1 ELSE 0 END) > 0
)
SELECT linea_codigo, referencia_codigo, material_code, total_colores, colores_con_stock, colores_sin_stock
FROM modelo_summary
ORDER BY total_colores DESC, colores_sin_stock DESC
LIMIT 5
""")
rows = cur.fetchall()

print('Modelos con stock mixto (algunos colores con stock, otros sin):')
print()
print('Linea | Ref  | Material | Total | Con Stock | Sin Stock')
print('-' * 70)
for r in rows:
    print(f'{r[0]:5} | {r[1]:4} | {r[2]:8} | {r[3]:5} | {r[4]:9} | {r[5]:9}')

if rows:
    print()
    print('Verificando primer modelo en detalle:')
    test_linea, test_ref, test_mat = rows[0][0], rows[0][1], rows[0][2]

    cur.execute("""
    SELECT descp_color, color_code, SUM(cantidad_cajas) as cajas
    FROM v_stock_rimec
    WHERE linea_codigo = %s AND referencia_codigo = %s AND material_code = %s
    GROUP BY descp_color, color_code
    ORDER BY cajas DESC, descp_color
    """, (test_linea, test_ref, test_mat))

    detail = cur.fetchall()
    print()
    print(f'Modelo: {test_linea} / {test_ref} / {test_mat}')
    print('Color            | Code  | Cajas')
    print('-' * 40)
    for d in detail:
        stock_marker = '✓' if d[2] > 0 else '✗'
        print(f'{d[0]:16} | {d[1]:5} | {d[2]:5} {stock_marker}')

    chips_esperados = sum(1 for d in detail if d[2] > 0)
    print()
    print(f'Chips esperados (solo con stock): {chips_esperados}/{len(detail)}')
    print(f'Badge esperado: "{chips_esperados} col."')

cur.close()
conn.close()
