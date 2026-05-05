#!/usr/bin/env python3
"""
Script de Test: Verificar nomenclatura [PP_ID]-PV[NNN] de Facturas Internas

Uso:
    python scripts/test_fi_nomenclatura.py [pp_id]
    
Ejemplo:
    python scripts/test_fi_nomenclatura.py 15
    
Si no se especifica pp_id, usa 15 por defecto.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import engine, get_dataframe
from sqlalchemy import text as sqlt


def test_nomenclatura(pp_id: int = 15):
    """
    Crea una FI de prueba para verificar la nomenclatura [PP_ID]-PV[NNN].
    """
    print("=" * 60)
    print(f"TEST: Nomenclatura Factura Interna para PP {pp_id}")
    print("=" * 60)
    print()
    
    # 1. Verificar que el PP existe
    df_pp = get_dataframe("""
        SELECT id, numero_registro, pares_comprometidos, estado
        FROM pedido_proveedor
        WHERE id = :pp_id
    """, {"pp_id": pp_id})
    
    if df_pp is None or df_pp.empty:
        print(f"⚠️  PP {pp_id} no existe. Creando PP de prueba...")
        
        with engine.begin() as conn:
            # Crear PP de prueba
            result = conn.execute(sqlt("""
                INSERT INTO pedido_proveedor (
                    numero_registro, estado, pares_comprometidos,
                    proveedor_importacion_id, fecha_pedido
                ) VALUES (
                    :nro, 'ABIERTO', 1000, 654, CURRENT_DATE
                )
                RETURNING id
            """), {"nro": f"PP-TEST-{pp_id}"})
            pp_id = result.fetchone()[0]
            print(f"✅ PP de prueba creado con id={pp_id}")
    else:
        pp_row = df_pp.iloc[0]
        print(f"✅ PP encontrado: {pp_row['numero_registro']} (id={pp_id})")
        print(f"   Estado: {pp_row['estado']}, Pares: {pp_row['pares_comprometidos']}")
    
    print()
    
    # 2. Ver FIs existentes para este PP
    df_fi = get_dataframe("""
        SELECT id, nro_factura, estado, total_pares, created_at
        FROM factura_interna
        WHERE pp_id = :pp_id
        ORDER BY created_at DESC
    """, {"pp_id": pp_id})
    
    if df_fi is not None and not df_fi.empty:
        print(f"📋 FIs existentes para PP {pp_id}:")
        for _, row in df_fi.iterrows():
            print(f"   {row['nro_factura']} | {row['estado']} | {row['total_pares']} pares")
        print()
    else:
        print(f"📋 No hay FIs existentes para PP {pp_id}")
        print()
    
    # 3. Crear FI de prueba usando la función de PostgreSQL
    print("🔧 Creando FI de prueba...")
    
    with engine.begin() as conn:
        # Usar la función generar_nro_factura_interna()
        result = conn.execute(sqlt("""
            SELECT generar_nro_factura_interna(:pp_id) AS nro
        """), {"pp_id": pp_id})
        nro_generado = result.fetchone()[0]
        print(f"   Número generado por función PostgreSQL: {nro_generado}")
        
        # Insertar la FI
        result = conn.execute(sqlt("""
            INSERT INTO factura_interna (
                pp_id, nro_factura, cliente_id, total_pares, total_monto, estado
            ) VALUES (
                :pp_id, :nro, 1, 100, 500000, 'RESERVADA'
            )
            RETURNING id, nro_factura, estado
        """), {"pp_id": pp_id, "nro": nro_generado})
        
        fi_row = result.fetchone()
        print(f"   ✅ FI creada: id={fi_row[0]}, nro={fi_row[1]}, estado={fi_row[2]}")
    
    print()
    
    # 4. Verificar el resultado
    df_after = get_dataframe("""
        SELECT id, nro_factura, estado, total_pares
        FROM factura_interna
        WHERE pp_id = :pp_id
        ORDER BY nro_factura
    """, {"pp_id": pp_id})
    
    print(f"📋 FIs después del test para PP {pp_id}:")
    for _, row in df_after.iterrows():
        # Verificar formato
        nro = row['nro_factura']
        es_valido = nro.startswith(f"{pp_id}-PV")
        marca = "✅" if es_valido else "❌"
        print(f"   {marca} {nro} | {row['estado']} | {row['total_pares']} pares")
    
    print()
    print("=" * 60)
    
    # 5. Test de correlativo
    print("🧪 Test de correlativo: creando segunda FI...")
    
    with engine.begin() as conn:
        result = conn.execute(sqlt("""
            SELECT generar_nro_factura_interna(:pp_id) AS nro
        """), {"pp_id": pp_id})
        nro_2 = result.fetchone()[0]
        
        conn.execute(sqlt("""
            INSERT INTO factura_interna (
                pp_id, nro_factura, cliente_id, total_pares, total_monto, estado
            ) VALUES (:pp_id, :nro, 1, 200, 1000000, 'RESERVADA')
        """), {"pp_id": pp_id, "nro": nro_2})
        
        print(f"   Segunda FI: {nro_2}")
    
    # Mostrar todas
    df_final = get_dataframe("""
        SELECT nro_factura, estado, total_pares
        FROM factura_interna
        WHERE pp_id = :pp_id
        ORDER BY nro_factura
    """, {"pp_id": pp_id})
    
    print()
    print(f"📋 Todas las FIs para PP {pp_id}:")
    for _, row in df_final.iterrows():
        print(f"   {row['nro_factura']} | {row['estado']} | {row['total_pares']} pares")
    
    print()
    print("=" * 60)
    print("✅ Test completado")
    print()
    print("Formato esperado: [PP_ID]-PV[NNN]")
    print(f"Ejemplo para PP {pp_id}: {pp_id}-PV001, {pp_id}-PV002, etc.")
    print()
    
    return True


def cleanup_test_fis(pp_id: int = 15):
    """Limpia las FIs de prueba creadas por este script."""
    with engine.begin() as conn:
        result = conn.execute(sqlt("""
            DELETE FROM factura_interna
            WHERE pp_id = :pp_id
              AND cliente_id = 1
              AND total_pares IN (100, 200)
            RETURNING nro_factura
        """), {"pp_id": pp_id})
        deleted = [r[0] for r in result.fetchall()]
        if deleted:
            print(f"🗑️  FIs de prueba eliminadas: {', '.join(deleted)}")
        else:
            print("ℹ️  No había FIs de prueba para eliminar")


if __name__ == "__main__":
    pp_id = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    
    if len(sys.argv) > 2 and sys.argv[2] == "--cleanup":
        cleanup_test_fis(pp_id)
    else:
        test_nomenclatura(pp_id)
        print()
        print("Para limpiar FIs de prueba: python scripts/test_fi_nomenclatura.py 15 --cleanup")
