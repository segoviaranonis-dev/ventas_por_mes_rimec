#!/usr/bin/env python3
"""
Verificar que tiendas_marcas tiene datos para sincronización
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    engine = get_engine()

    print("=" * 70)
    print(" VERIFICANDO TABLA tiendas_marcas")
    print("=" * 70)

    # Verificar marcas por tienda
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT cliente_id, COUNT(*) as total_marcas
            FROM tiendas_marcas
            GROUP BY cliente_id
            ORDER BY cliente_id
        """))

        print("\nMarcas permitidas por tienda:")
        for row in result:
            cliente_id = row[0]
            total = row[1]
            tipo = "Niños" if cliente_id in (2900, 2700, 3200) else "Adultos"
            print(f"  {cliente_id} ({tipo:7}): {total} marcas")

    # Verificar preview para cliente_id 2100
    print("\n" + "=" * 70)
    print(" PREVIEW PARA CLIENTE_ID 2100 (Fernando Adultos)")
    print("=" * 70)

    with engine.connect() as conn:
        # Contar registros TOTALES sin filtro
        result_total = conn.execute(text("""
            SELECT COUNT(*) as total
            FROM registro_st_vt_rc_reposicion
            WHERE cliente_id = 2100
              AND lower(btrim(tipo_movimiento)) = 'stock'
        """))
        total_sin_filtro = result_total.fetchone()[0]
        print(f"\nRegistros SIN filtro tiendas_marcas: {total_sin_filtro:,}")

        # Contar registros CON filtro tiendas_marcas
        result_filtrado = conn.execute(text("""
            SELECT COUNT(*) as total
            FROM registro_st_vt_rc_reposicion r
            INNER JOIN tiendas_marcas tm ON
              tm.cliente_id = 2100 AND
              tm.marca_id = r.marca_id AND
              tm.activo = true
            WHERE r.cliente_id = 2100
              AND lower(btrim(r.tipo_movimiento)) = 'stock'
        """))
        total_con_filtro = result_filtrado.fetchone()[0]
        print(f"Registros CON filtro tiendas_marcas: {total_con_filtro:,}")

        # Verificar marcas excluidas
        result_excluidas = conn.execute(text("""
            SELECT
              r.marca_id,
              m.descp_marca,
              COUNT(*) as registros
            FROM registro_st_vt_rc_reposicion r
            LEFT JOIN marca_v2 m ON m.id_marca = r.marca_id
            WHERE r.cliente_id = 2100
              AND lower(btrim(r.tipo_movimiento)) = 'stock'
              AND NOT EXISTS (
                SELECT 1 FROM tiendas_marcas tm
                WHERE tm.cliente_id = 2100
                  AND tm.marca_id = r.marca_id
              )
            GROUP BY r.marca_id, m.descp_marca
            ORDER BY registros DESC
        """))

        excluidas = list(result_excluidas)
        if excluidas:
            print(f"\n⚠️  MARCAS EXCLUIDAS (filtradas):")
            for row in excluidas:
                marca_id = row[0]
                marca = row[1] or f"ID {marca_id}"
                registros = row[2]
                print(f"  - {marca}: {registros:,} registros bloqueados")
        else:
            print("\n✅ Todas las marcas en cliente_id 2100 están permitidas")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
