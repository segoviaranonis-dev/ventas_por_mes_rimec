"""
Buscar material con codigo_proveedor=31855 para resolver ref 565.
"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("BUSCAR: Material codigo_proveedor=31855")
    print("=" * 80)
    print()

    # Buscar por codigo_proveedor
    cur.execute("""
        SELECT m.id, m.proveedor_id, m.codigo_proveedor, m.descripcion
        FROM material m
        WHERE m.codigo_proveedor = 31855
        LIMIT 5
    """)

    rows = cur.fetchall()

    if rows:
        print(f"ENCONTRADO: {len(rows)} materiales con codigo_proveedor=31855")
        for mat_id, prov_id, cod, desc in rows:
            print(f'  material_id={mat_id}, prov={prov_id}, codigo={cod}, desc="{desc}"')
        print()

        # Usar el primero para resolver combinaciones
        mat_id, prov_id, cod, desc = rows[0]

        if desc and desc.strip():
            print("[SOLUCION ENCONTRADA]")
            print(f'  Material {cod} tiene descripcion: "{desc}"')
            print(f"  Se puede usar para resolver combinaciones de ref 565")
            print()
            print("[PASOS SIGUIENTES]")
            print(f'  1. Corregir snapshot_json: material="" -> material="{desc}"')
            print("  2. Re-ejecutar rehidratar_traspaso_standalone.py --traspaso-id 2 --yes")
            print("  3. Verificar que los 8 pares se insertan correctamente")
        else:
            print("[PROBLEMA PERSISTENTE]")
            print(f"  Material {cod} tambien tiene descripcion vacia")
            print("  No se puede resolver sin descripcion")
    else:
        print("NO ENCONTRADO: Material con codigo_proveedor=31855")
        print()
        print("Alternativa: Buscar en tabla material del proveedor 654")

        cur.execute("""
            SELECT m.id, m.codigo_proveedor, m.descripcion
            FROM material m
            WHERE m.proveedor_id = 654
            ORDER BY m.codigo_proveedor
            LIMIT 20
        """)

        mats = cur.fetchall()
        print(f"Materiales del proveedor 654:")
        for m_id, m_cod, m_desc in mats:
            print(f"  {m_cod}: {m_desc}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
