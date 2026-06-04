#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anular FI huérfana de PP-2026-0010
Ejecutar directamente para liberar los 36 pares bloqueados
"""
from core.database import get_dataframe
from modules.aprobacion_pedidos.logic import anular_fi
from core.database import DBInspector

print("=" * 80)
print("REPARACION: Anular FI huerfana de PP-2026-0010")
print("=" * 80)

# 1. Buscar el PP
print("\n1. Buscando PP-2026-0010...")
df_pp = get_dataframe("""
    SELECT id, numero_registro, estado
    FROM pedido_proveedor
    WHERE numero_registro = 'PP-2026-0010'
""")

if df_pp is None or df_pp.empty:
    print("ERROR - PP no encontrado en la base de datos")
    print("Verifica que estes conectado a la base de datos correcta")
    exit(1)

pp_id = int(df_pp['id'].iloc[0])
print(f"OK - PP encontrado (ID: {pp_id})")

# 2. Stock actual
print("\n2. Stock del PP:")
df_stock = get_dataframe("""
    SELECT
        SUM(cantidad_pares) as total,
        SUM(COALESCE(pares_vendidos, 0)) as vendidos,
        SUM(cantidad_pares - COALESCE(pares_vendidos, 0)) as disponible
    FROM pedido_proveedor_detalle
    WHERE pedido_proveedor_id = :pp_id
""", {"pp_id": pp_id})

if df_stock is not None and not df_stock.empty:
    total = int(df_stock['total'].iloc[0])
    vendidos = int(df_stock['vendidos'].iloc[0])
    disponible = int(df_stock['disponible'].iloc[0])
    print(f"  Total: {total} pares")
    print(f"  Bloqueados: {vendidos} pares")
    print(f"  Disponibles: {disponible} pares")

# 3. Buscar FIs del PP
print("\n3. Buscando Facturas Internas...")
df_fi = get_dataframe("""
    SELECT
        fi.id,
        fi.nro_factura,
        fi.estado,
        fi.marca,
        fi.caso,
        fi.total_pares,
        fi.pedido_id,
        pvr.nro_pedido,
        pvr.estado as pedido_estado
    FROM factura_interna fi
    LEFT JOIN pedido_venta_rimec pvr ON pvr.id = fi.pedido_id
    WHERE fi.pp_id = :pp_id
    ORDER BY fi.id
""", {"pp_id": pp_id})

if df_fi is None or df_fi.empty:
    print("No hay facturas internas para este PP")
    exit(0)

print(f"Encontradas {len(df_fi)} facturas internas:\n")
print(df_fi[['nro_factura', 'estado', 'total_pares', 'nro_pedido', 'pedido_estado']].to_string(index=False))

# 4. Identificar FIs problemáticas
print("\n4. Analizando inconsistencias...")
problematicas = []

for _, fi_row in df_fi.iterrows():
    es_problema = False
    motivo = ""

    if fi_row['estado'] == 'RESERVADA':
        if fi_row['pedido_estado'] == 'RECHAZADO':
            es_problema = True
            motivo = f"Pedido {fi_row['nro_pedido']} fue RECHAZADO"
        elif not fi_row['pedido_id']:
            es_problema = True
            motivo = "FI huerfana sin pedido asociado"

        if es_problema:
            problematicas.append({
                'fi_id': int(fi_row['id']),
                'nro_factura': fi_row['nro_factura'],
                'pares': int(fi_row['total_pares']),
                'motivo': motivo
            })

if not problematicas:
    print("OK - No hay FIs problemáticas")
    print("Todas las FIs estan en estado consistente")
    exit(0)

print(f"\nFIs PROBLEMATICAS encontradas: {len(problematicas)}")
for fp in problematicas:
    print(f"  - {fp['nro_factura']}: {fp['pares']} pares bloqueados")
    print(f"    Motivo: {fp['motivo']}")

# 5. Confirmación
print("\n" + "=" * 80)
total_liberar = sum(fp['pares'] for fp in problematicas)
print(f"Se liberaran {total_liberar} pares al anular estas {len(problematicas)} FI(s)")
print("=" * 80)

respuesta = input("\nProceder con la anulacion? (SI/no): ").strip()

if respuesta.upper() not in ('SI', 'S', 'YES', 'Y', ''):
    print("Operacion cancelada")
    exit(0)

# 6. Anular cada FI problemática
print("\n" + "=" * 80)
print("ANULANDO FIs...")
print("=" * 80)

exitosos = []
errores = []

for fp in problematicas:
    print(f"\nAnulando {fp['nro_factura']}...")

    ok, msg = anular_fi(fp['fi_id'], motivo=fp['motivo'])

    if ok:
        print(f"  OK - {msg}")
        exitosos.append(fp['nro_factura'])
        DBInspector.log(f"[REPARACION] {fp['nro_factura']} anulada: {fp['motivo']}", "SUCCESS")
    else:
        print(f"  ERROR - {msg}")
        errores.append(f"{fp['nro_factura']}: {msg}")
        DBInspector.log(f"[REPARACION] Error anulando {fp['nro_factura']}: {msg}", "ERROR")

# 7. Verificar stock final
print("\n" + "=" * 80)
print("VERIFICACION FINAL:")
print("=" * 80)

df_stock_final = get_dataframe("""
    SELECT
        SUM(cantidad_pares) as total,
        SUM(COALESCE(pares_vendidos, 0)) as vendidos,
        SUM(cantidad_pares - COALESCE(pares_vendidos, 0)) as disponible
    FROM pedido_proveedor_detalle
    WHERE pedido_proveedor_id = :pp_id
""", {"pp_id": pp_id})

if df_stock_final is not None and not df_stock_final.empty:
    total_f = int(df_stock_final['total'].iloc[0])
    vendidos_f = int(df_stock_final['vendidos'].iloc[0])
    disponible_f = int(df_stock_final['disponible'].iloc[0])

    print(f"\nStock ANTES:")
    print(f"  Bloqueados: {vendidos} pares")
    print(f"  Disponibles: {disponible} pares")

    print(f"\nStock DESPUES:")
    print(f"  Bloqueados: {vendidos_f} pares")
    print(f"  Disponibles: {disponible_f} pares")

    if disponible_f > disponible:
        liberados = disponible_f - disponible
        print(f"\nOK - Se liberaron {liberados} pares exitosamente!")

# 8. Resumen
print("\n" + "=" * 80)
print("RESUMEN:")
print(f"  FIs anuladas exitosamente: {len(exitosos)}")
if exitosos:
    for nro in exitosos:
        print(f"    - {nro}")

if errores:
    print(f"  Errores: {len(errores)}")
    for err in errores:
        print(f"    - {err}")

print("=" * 80)
print("REPARACION COMPLETADA")
print("=" * 80)
