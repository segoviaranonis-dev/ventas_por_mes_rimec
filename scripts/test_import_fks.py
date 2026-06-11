#!/usr/bin/env python3
"""
Script de prueba: Verificar que el proceso de importación resuelve FKs correctamente
"""

import sys
from pathlib import Path

# Agregar control_central al path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    print("=" * 70)
    print(" VERIFICACION: Ultimos registros importados tienen FKs completos")
    print("=" * 70)

    engine = get_engine()

    # Obtener últimos 10 registros importados (por created_at DESC)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                r.origen_holding,
                r.linea_codigo_proveedor,
                r.referencia_codigo_proveedor,
                r.linea_id,
                r.referencia_id,
                r.cliente_id,
                r.tipo_v2_id,
                r.marca_id,
                m.descp_marca,
                r.created_at
            FROM public.registro_st_vt_rc_reposicion r
            LEFT JOIN marca_v2 m ON r.marca_id = m.id_marca
            ORDER BY r.created_at DESC
            LIMIT 10
        """))

        rows = result.fetchall()

        if not rows:
            print("\nNo hay registros en la tabla.")
            return

        print(f"\nUltimos 10 registros importados:")
        print("-" * 70)

        for i, row in enumerate(rows, 1):
            origen = row[0]
            linea_cod = row[1]
            ref_cod = row[2]
            linea_id = row[3]
            ref_id = row[4]
            cliente_id = row[5]
            tipo_v2_id = row[6]
            marca_id = row[7]
            marca = row[8]
            created = row[9]

            print(f"\n[{i}] {created}")
            print(f"    origen_holding: {origen}")
            print(f"    linea_codigo: {linea_cod} -> linea_id: {linea_id} {'OK' if linea_id else 'NULL'}")
            print(f"    ref_codigo: {ref_cod} -> ref_id: {ref_id} {'OK' if ref_id else 'NULL'}")
            print(f"    marca: {marca} (id={marca_id})")
            print(f"    cliente_id: {cliente_id} {'OK' if cliente_id else 'NULL (RIMEC)'}")
            print(f"    tipo_v2_id: {tipo_v2_id} {'OK' if tipo_v2_id else 'NULL'}")

    # Estadísticas generales
    print(f"\n{'=' * 70}")
    print(" ESTADISTICAS GENERALES")
    print("=" * 70)

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE linea_id IS NOT NULL) AS con_linea,
                COUNT(*) FILTER (WHERE referencia_id IS NOT NULL) AS con_ref,
                COUNT(*) FILTER (WHERE cliente_id IS NOT NULL) AS con_cliente,
                COUNT(*) FILTER (WHERE tipo_v2_id IS NOT NULL) AS con_tipo
            FROM public.registro_st_vt_rc_reposicion
        """))

        row = result.fetchone()
        total = row[0]
        con_linea = row[1]
        con_ref = row[2]
        con_cliente = row[3]
        con_tipo = row[4]

        print(f"\nTotal registros: {total:,}")
        print(f"Con linea_id:    {con_linea:,} ({100*con_linea/total:.1f}%)")
        print(f"Con ref_id:      {con_ref:,} ({100*con_ref/total:.1f}%)")
        print(f"Con cliente_id:  {con_cliente:,} ({100*con_cliente/total:.1f}%)")
        print(f"Con tipo_v2_id:  {con_tipo:,} ({100*con_tipo/total:.1f}%)")

        if con_linea == total and con_ref == total and con_tipo == total:
            print(f"\n{'=' * 70}")
            print(" OK - SISTEMA FUNCIONANDO CORRECTAMENTE")
            print(" Todos los FKs se resuelven automaticamente en cada import")
            print("=" * 70)
        else:
            print(f"\n{'=' * 70}")
            print(" ATENCION: Algunos registros sin FKs")
            print(" Esto es normal si son registros antiguos (antes del fix)")
            print("=" * 70)

if __name__ == "__main__":
    main()
