import psycopg2

conn = psycopg2.connect('postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
cur = conn.cursor()
cur.execute('''
SELECT det_id, descp_color, material_code, cantidad_cajas, cajas_disponibles,
       LEFT(grades_json::text, 60) as grades_preview
FROM v_stock_rimec
WHERE linea_codigo = %s AND referencia_codigo = %s
ORDER BY descp_color, material_code, grades_json::text
''', ['5287', '210'])

print('det_id | Color           | Material | Cajas | Disp | Grades')
print('-' * 90)
for r in cur.fetchall():
    print(f'{r[0]:6} | {r[1]:15} | {r[2]:8} | {r[3]:5} | {r[4]:4} | {r[5]}')

cur.close()
conn.close()
