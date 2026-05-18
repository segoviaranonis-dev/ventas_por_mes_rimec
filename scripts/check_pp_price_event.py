import psycopg2

conn = psycopg2.connect('postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres')
cur = conn.cursor()

# Check precio_evento_id
cur.execute('''
    SELECT pp.id, pp.numero_registro, ic.precio_evento_id
    FROM pedido_proveedor pp
    LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
    WHERE pp.id = 1
''')
r = cur.fetchone()

if r:
    pp_id, pp_nro, precio_evento_id = r
    print(f'PP id={pp_id} ({pp_nro}):')
    print(f'  precio_evento_id: {precio_evento_id if precio_evento_id else "NULL (sin listado vinculado)"}')
else:
    print('PP id=1 no encontrado')
    precio_evento_id = None

# Check FI RESERVADA - simplificado (puede no existir estructura completa aun)
try:
    cur.execute("SELECT COUNT(*) FROM factura_interna WHERE estado = 'RESERVADA'")
    fi_count = cur.fetchone()[0]
    print(f'  FI RESERVADA (total sistema): {fi_count}')
except Exception as e:
    print(f'  FI: No disponible o estructura incompleta ({e})')
    fi_count = 0

print()
if precio_evento_id:
    print(f'[INFO] PP tiene listado vinculado (evento {precio_evento_id})')
    if fi_count > 0:
        print(f'[ACCION] Recalcular {fi_count} FI RESERVADA tras saneo')
    else:
        print('[OK] Sin FI RESERVADA para recalcular')
else:
    print('[INFO] PP sin listado RIMEC vinculado - no requiere recalculo FI')

cur.close()
conn.close()
