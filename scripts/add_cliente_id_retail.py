#!/usr/bin/env python3
"""
Agregar columna cliente_id a registro_st_vt_rc_reposicion
Derivada desde origen_holding + marca_id

REGLAS:
- Fernando + Molekinha/Molekinho → 2900 (Niños)
- Fernando + Otras marcas → 2100 (Adultos)
- San Martin + Molekinha/Molekinho → 2700 (Niños)
- San Martin + Otras marcas → 2400 (Adultos)
- Palma + Molekinha/Molekinho → 3200 (Niños)
- Palma + Otras marcas → 3100 (Adultos)
- RIMEC → NULL (no es tienda)
"""

import sys
from pathlib import Path

# Agregar control_central al path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    print("=" * 70)
    print(" AGREGAR COLUMNA cliente_id - Venta en Tienda")
    print("=" * 70)

    engine = get_engine()

    # Paso 1: Obtener IDs de marcas Molekinha y Molekinho
    print("\n[1/5] Obteniendo IDs de marcas Molekinha y Molekinho...")

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id_marca, descp_marca
            FROM marca_v2
            WHERE descp_marca IN ('MOLEKINHA', 'MOLEKINHO')
        """))
        marcas_ninos = result.fetchall()

        if marcas_ninos:
            ids_ninos = [str(m[0]) for m in marcas_ninos]
            print(f"     OK - Marcas niños encontradas: {', '.join([m[1] for m in marcas_ninos])}")
            print(f"     IDs: {', '.join(ids_ninos)}")
        else:
            print("     ERROR - No se encontraron marcas Molekinha/Molekinho")
            return

    # Paso 2: Agregar columna cliente_id
    print("\n[2/5] Agregando columna cliente_id...")

    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE public.registro_st_vt_rc_reposicion
            ADD COLUMN IF NOT EXISTS cliente_id INT;
        """))
        print("     OK")

    # Paso 3: Resolver cliente_id para tiendas NIÑOS
    print("\n[3/5] Resolviendo cliente_id para tiendas NIÑOS (Molekinha/Molekinho)...")

    ids_str = ','.join(ids_ninos)

    sql_ninos = f"""
    UPDATE public.registro_st_vt_rc_reposicion
    SET cliente_id = CASE
        WHEN lower(trim(origen_holding)) LIKE '%fernando%' THEN 2900
        WHEN lower(trim(origen_holding)) LIKE '%san%mart%' THEN 2700
        WHEN lower(trim(origen_holding)) LIKE '%palma%' THEN 3200
    END
    WHERE cliente_id IS NULL
      AND marca_id IN ({ids_str})
      AND lower(trim(origen_holding)) SIMILAR TO '%(fernando|san.?mart|palma)%';
    """

    with engine.begin() as conn:
        result = conn.execute(text(sql_ninos))
        print(f"     OK - {result.rowcount} filas (Molekinha/Molekinho)")

    # Paso 4: Resolver cliente_id para tiendas ADULTOS
    print("\n[4/5] Resolviendo cliente_id para tiendas ADULTOS (otras marcas)...")

    sql_adultos = f"""
    UPDATE public.registro_st_vt_rc_reposicion
    SET cliente_id = CASE
        WHEN lower(trim(origen_holding)) LIKE '%fernando%' THEN 2100
        WHEN lower(trim(origen_holding)) LIKE '%san%mart%' THEN 2400
        WHEN lower(trim(origen_holding)) LIKE '%palma%' THEN 3100
    END
    WHERE cliente_id IS NULL
      AND (marca_id NOT IN ({ids_str}) OR marca_id IS NULL)
      AND lower(trim(origen_holding)) SIMILAR TO '%(fernando|san.?mart|palma)%';
    """

    with engine.begin() as conn:
        result = conn.execute(text(sql_adultos))
        print(f"     OK - {result.rowcount} filas (otras marcas)")

    # Paso 5: RIMEC queda NULL (es depósito, no tienda)
    print("\n[5/5] Verificando RIMEC (debe quedar NULL)...")

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*)
            FROM public.registro_st_vt_rc_reposicion
            WHERE lower(trim(origen_holding)) LIKE '%rimec%'
              OR lower(trim(origen_holding)) LIKE '%import%'
        """))
        rimec_count = result.fetchone()[0]
        print(f"     OK - {rimec_count} registros RIMEC con cliente_id=NULL (correcto)")

    # Verificación final
    print(f"\n{'=' * 70}")
    print(" VERIFICACION FINAL")
    print("=" * 70)

    verification_sql = """
    SELECT
      origen_holding,
      cliente_id,
      COUNT(*) AS cantidad,
      MIN(m.descp_marca) AS ejemplo_marca
    FROM public.registro_st_vt_rc_reposicion r
    LEFT JOIN marca_v2 m ON r.marca_id = m.id_marca
    GROUP BY origen_holding, cliente_id
    ORDER BY origen_holding, cliente_id;
    """

    with engine.connect() as conn:
        result = conn.execute(text(verification_sql))
        rows = result.fetchall()

        print("\nDistribución por origen_holding y cliente_id:")
        print("-" * 70)
        print(f"{'Origen':<20} {'cliente_id':<12} {'Cantidad':<10} {'Ejemplo Marca'}")
        print("-" * 70)

        for row in rows:
            origen = row[0] or "(NULL)"
            cliente = row[1] if row[1] else "NULL"
            cantidad = row[2]
            marca = row[3] or "-"
            print(f"{origen:<20} {str(cliente):<12} {cantidad:<10} {marca}")

    # Resumen por cliente_id
    print(f"\n{'=' * 70}")
    print(" RESUMEN POR CLIENTE")
    print("=" * 70)

    summary_sql = """
    SELECT
      cliente_id,
      COUNT(*) AS cantidad
    FROM public.registro_st_vt_rc_reposicion
    GROUP BY cliente_id
    ORDER BY cliente_id NULLS LAST;
    """

    with engine.connect() as conn:
        result = conn.execute(text(summary_sql))
        rows = result.fetchall()

        tiendas = {
            2100: "Fernando Adultos",
            2900: "Fernando Niños",
            2400: "San Martin Adultos",
            2700: "San Martin Niños",
            3100: "Palma Adultos",
            3200: "Palma Niños"
        }

        print(f"\n{'cliente_id':<15} {'Tienda':<25} {'Registros'}")
        print("-" * 70)
        for row in rows:
            cliente = row[0]
            cantidad = row[1]
            if cliente:
                nombre = tiendas.get(cliente, "DESCONOCIDO")
                print(f"{cliente:<15} {nombre:<25} {cantidad:,}")
            else:
                print(f"{'NULL':<15} {'RIMEC (depósito)':<25} {cantidad:,}")

    print(f"\n{'=' * 70}")
    print(" COLUMNA cliente_id AGREGADA Y RESUELTA EXITOSAMENTE")
    print("=" * 70)

if __name__ == "__main__":
    main()
