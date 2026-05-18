import psycopg2

conn = psycopg2.connect('postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
cur = conn.cursor()
cur.execute("""
SELECT linea_codigo, referencia_codigo, material_code, descp_color, cantidad_cajas, cantidad_pares
FROM v_stock_rimec
WHERE linea_codigo = '7320' AND referencia_codigo = '239'
ORDER BY descp_color
""")
rows = cur.fetchall()
print(f'Total variantes: {len(rows)}')
print('linea | ref  | material | color            | cajas | pares')
print('-' * 70)
for r in rows:
    print(f'{r[0]:5} | {r[1]:4} | {r[2]:8} | {r[3]:16} | {r[4]:5} | {r[5]:5}')
print()
con_stock = sum(1 for r in rows if r[4] > 0)
print(f'Variantes con stock (cajas > 0): {con_stock}')
cur.close()
conn.close()
