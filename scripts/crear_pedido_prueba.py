#!/usr/bin/env python3
"""Crea un pedido de prueba para testing del módulo de aprobaciones"""
import sys
from pathlib import Path

# Agregar el directorio raíz al path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backfill_combinacion_desde_ppd import _db_url
import psycopg2

# Obtener DATABASE_URL
db_url = _db_url()
if not db_url:
    print("ERROR: No se encontró DATABASE_URL")
    exit(1)

print("Conectando a la base de datos...")
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Verificar si ya hay pedidos
cur.execute("SELECT COUNT(*) FROM pedido_venta_rimec")
count = cur.fetchone()[0]
print(f"Pedidos existentes: {count}")

if count == 0:
    print("\nNo hay pedidos. Verificando datos necesarios...")

    # Verificar cliente
    cur.execute("SELECT id FROM cadena_cliente LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("ERROR: No hay clientes en la BD")
        exit(1)
    cliente_id = row[0]
    print(f"Cliente ID: {cliente_id}")

    # Verificar vendedor
    cur.execute("SELECT id_usuario FROM usuario_v2 WHERE categoria = 'VENDEDOR' LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("ERROR: No hay vendedores en la BD")
        exit(1)
    vendedor_id = row[0]
    print(f"Vendedor ID: {vendedor_id}")

    print("\nINFO: Necesitas crear pedidos desde RIMEC Web")
    print("O ejecutar la función confirmar_pedido_web() desde el módulo de digitación")
else:
    print("\nPedidos encontrados:")
    cur.execute("""
        SELECT
            id,
            nro_pedido,
            estado,
            total_pares,
            total_monto,
            vendedor_id,
            cliente_id
        FROM pedido_venta_rimec
        ORDER BY id DESC
        LIMIT 5
    """)

    for row in cur.fetchall():
        print(f"  ID: {row[0]} | {row[1]} | Estado: {row[2]} | {row[3]} pares | Gs. {row[4]:,} | Vendedor ID: {row[5]} | Cliente ID: {row[6]}")

conn.close()
print("\nDone!")
