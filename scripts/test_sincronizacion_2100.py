#!/usr/bin/env python3
"""
Probar sincronización del depósito 2100 manualmente
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    engine = get_engine()

    print("=" * 70)
    print(" PRUEBA DE SINCRONIZACION: Deposito Fernando Adultos (2100)")
    print("=" * 70)

    with engine.begin() as conn:
        # 1. Borrar registros existentes
        print("\n1. Borrando registros existentes...")
        delete_result = conn.execute(text("DELETE FROM deposito_tienda_fernando_adultos"))
        registros_borrados = delete_result.rowcount
        print(f"   Registros borrados: {registros_borrados}")

        # 2. Insertar registros con filtro tiendas_marcas
        print("\n2. Insertando registros desde registro_st_vt_rc_reposicion...")
        insert_result = conn.execute(text("""
            INSERT INTO deposito_tienda_fernando_adultos
            SELECT r.*
            FROM registro_st_vt_rc_reposicion r
            INNER JOIN tiendas_marcas tm ON
              tm.cliente_id = 2100 AND
              tm.marca_id = r.marca_id AND
              tm.activo = true
            WHERE r.cliente_id = 2100
              AND lower(btrim(r.tipo_movimiento)) = 'stock'
        """))
        registros_insertados = insert_result.rowcount
        print(f"   Registros insertados: {registros_insertados}")

        # 3. Verificar
        print("\n3. Verificando...")
        verify_result = conn.execute(text("""
            SELECT COUNT(*) as total
            FROM deposito_tienda_fernando_adultos
        """))
        total = verify_result.fetchone()[0]
        print(f"   Total en deposito: {total}")

    print("\n" + "=" * 70)
    if registros_insertados > 0:
        print(" SINCRONIZACION EXITOSA")
    else:
        print(" ADVERTENCIA: 0 registros insertados")
    print("=" * 70)

if __name__ == "__main__":
    main()
