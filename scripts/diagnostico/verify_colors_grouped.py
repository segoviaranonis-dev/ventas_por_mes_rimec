import psycopg2

conn = psycopg2.connect('postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
cur = conn.cursor()
cur.execute("""
SELECT descp_color, color_code, SUM(cantidad_cajas) as total_cajas, SUM(cantidad_pares) as total_pares, COUNT(*) as filas
FROM v_stock_rimec
WHERE linea_codigo = '7320' AND referencia_codigo = '239' AND material_code = '30998'
GROUP BY descp_color, color_code
ORDER BY descp_color
""")
rows = cur.fetchall()
print(f'Modelo: 7320 / 239 / 30998')
print(f'Colores unicos: {len(rows)}')
print()
print('Color            | Code  | Cajas | Pares | Filas')
print('-' * 60)
for r in rows:
    print(f'{r[0]:16} | {r[1]:5} | {r[2]:5} | {r[3]:5} | {r[4]:5}')
print()
con_stock = sum(1 for r in rows if r[2] > 0)
print(f'Colores con stock (cajas > 0): {con_stock}/{len(rows)}')
print()
print('Con el filtro aplicado, la tarjeta debe mostrar:')
print(f'  - {con_stock} chips de color')
print(f'  - Badge: "{con_stock} col."')
cur.close()
conn.close()
