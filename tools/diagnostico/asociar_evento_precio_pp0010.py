# Script para asociar evento de precios al pedido PP-2026-0010

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import engine
from sqlalchemy import text

print("\n" + "="*80)
print("SOLUCION: Asociar evento de precios a PP-2026-0010")
print("="*80 + "\n")

print("[INFO] Este script va a:")
print("  1. Crear una intencion_compra para el pedido PP-2026-0010")
print("  2. Asociar el evento de precios ID 11 (CP 0421-4081-2CORx)")
print("\n")

respuesta = input("¿Deseas continuar? (SI/NO): ")

if respuesta.upper() != "SI":
    print("\n[CANCELADO] No se realizaron cambios")
    sys.exit(0)

print("\n[PROCESO] Iniciando...")

try:
    with engine.begin() as conn:
        # 1. Verificar que el pedido existe
        result = conn.execute(text("""
            SELECT id, numero_registro, proveedor_importacion_id
            FROM public.pedido_proveedor
            WHERE numero_registro = 'PP-2026-0010'
        """))
        pp = result.fetchone()

        if not pp:
            print("[ERROR] Pedido PP-2026-0010 no encontrado")
            sys.exit(1)

        pp_id = pp[0]
        proveedor_id = pp[2]

        print(f"[OK] Pedido encontrado - ID: {pp_id}, Proveedor: {proveedor_id}")

        # 2. Verificar el evento de precios
        result = conn.execute(text("""
            SELECT id, nombre_evento, estado
            FROM public.precio_evento
            WHERE id = 11
        """))
        evento = result.fetchone()

        if not evento:
            print("[ERROR] Evento de precios ID 11 no encontrado")
            sys.exit(1)

        print(f"[OK] Evento encontrado: {evento[1]} (estado: {evento[2]})")

        # 3. Crear intención de compra
        print("\n[CREANDO] Intencion de compra...")

        result = conn.execute(text("""
            INSERT INTO public.intencion_compra
            (id_proveedor, precio_evento_id, estado, created_at)
            VALUES
            (:proveedor_id, 11, 'PENDIENTE', NOW())
            RETURNING id
        """), {"proveedor_id": proveedor_id})

        ic_id = result.fetchone()[0]
        print(f"[OK] Intencion de compra creada - ID: {ic_id}")

        # 4. Asociar al pedido
        print("\n[ACTUALIZANDO] Pedido proveedor...")

        conn.execute(text("""
            UPDATE public.pedido_proveedor
            SET id_intencion_compra = :ic_id
            WHERE id = :pp_id
        """), {"ic_id": ic_id, "pp_id": pp_id})

        print(f"[OK] Pedido actualizado con intencion_compra ID: {ic_id}")

        print("\n" + "="*80)
        print("[EXITO] Proceso completado!")
        print("="*80)
        print("\nAhora el pedido PP-2026-0010 debería poder consultar precios.")
        print("Recarga la página de revisión de pedido en el navegador.")

except Exception as e:
    print(f"\n[ERROR] Fallo durante el proceso:")
    print(f"  {str(e)}")
    print("\n[ROLLBACK] No se realizaron cambios")

print("\n" + "="*80)
