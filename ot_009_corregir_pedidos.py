"""
ORDEN DE TRABAJO 009: CORRECCIÓN DE TOTALES EN PEDIDOS
URGENCIA: CRÍTICA
DESCRIPCIÓN: Recalcular totales de pedidos_venta_rimec basándose en FIs corregidas
"""

from core.database import engine, get_dataframe
from sqlalchemy import text as sqlt

print("="*80)
print("CORRECCIÓN DE TOTALES EN PEDIDOS - ORDEN DE TRABAJO 009")
print("="*80)

# Obtener todos los pedidos con sus FIs
query = """
SELECT
    pvr.id as pedido_id,
    pvr.nro_pedido,
    pvr.total_pares as pedido_pares,
    pvr.total_monto as pedido_monto,
    COUNT(fi.id) as num_fis,
    SUM(fi.total_pares) as fis_pares,
    SUM(fi.total_monto) as fis_monto
FROM pedido_venta_rimec pvr
LEFT JOIN factura_interna fi ON fi.pedido_id = pvr.id
WHERE pvr.estado = 'PENDIENTE'
GROUP BY pvr.id, pvr.nro_pedido, pvr.total_pares, pvr.total_monto
ORDER BY pvr.id
"""

print("\n[1/2] Obteniendo pedidos y sus FIs...")
df = get_dataframe(query)

if df.empty:
    print("No hay pedidos para verificar.")
    exit(0)

print(f"   - {len(df)} pedidos encontrados")

# Identificar pedidos con discrepancia
print("\n[2/2] Corrigiendo totales...")
print("-"*80)

corregidos = 0
sin_cambios = 0
errores = []

with engine.begin() as conn:
    for idx, row in df.iterrows():
        pedido_id = int(row['pedido_id'])
        nro_pedido = row['nro_pedido']
        pedido_pares = float(row['pedido_pares'] or 0)
        pedido_monto = float(row['pedido_monto'] or 0)
        fis_pares = float(row['fis_pares'] or 0)
        fis_monto = float(row['fis_monto'] or 0)

        # Verificar si hay discrepancia
        diff_pares = abs(pedido_pares - fis_pares)
        diff_monto = abs(pedido_monto - fis_monto)

        if diff_pares > 0.1 or diff_monto > 1:
            print(f"\n[{idx+1}/{len(df)}] {nro_pedido} (ID:{pedido_id})")
            print(f"        Pedido: {pedido_pares:,.0f} pares, Gs. {pedido_monto:,.0f}")
            print(f"        FIs:    {fis_pares:,.0f} pares, Gs. {fis_monto:,.0f}")
            print(f"        Diff:   {diff_pares:,.0f} pares, Gs. {diff_monto:,.0f}")

            # Actualizar pedido
            try:
                update_query = sqlt("""
                    UPDATE pedido_venta_rimec
                    SET total_pares = :pares,
                        total_monto = :monto
                    WHERE id = :pedido_id
                """)

                conn.execute(update_query, {
                    'pedido_id': pedido_id,
                    'pares': fis_pares,
                    'monto': fis_monto
                })

                print(f"        [OK] Corregido")
                corregidos += 1

            except Exception as e:
                print(f"        [ERROR] {str(e)}")
                errores.append({
                    'pedido_id': pedido_id,
                    'nro_pedido': nro_pedido,
                    'error': str(e)
                })
        else:
            sin_cambios += 1

# Reporte final
print("\n" + "="*80)
print("RESUMEN DE CORRECCIÓN")
print("="*80)
print(f"Total procesados: {len(df)}")
print(f"Corregidos: {corregidos}")
print(f"Sin cambios: {sin_cambios}")
print(f"Errores: {len(errores)}")

if errores:
    print("\n" + "-"*80)
    print("ERRORES DETECTADOS")
    print("-"*80)
    for err in errores:
        print(f"  - {err['nro_pedido']} (ID:{err['pedido_id']}): {err['error']}")

print("\n" + "="*80)
if len(errores) == 0:
    print("[OK] CORRECCIÓN COMPLETADA EXITOSAMENTE")
else:
    print(f"[WARNING] CORRECCIÓN COMPLETADA CON {len(errores)} ERRORES")
print("="*80)
