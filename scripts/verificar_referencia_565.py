"""
Verificar si referencia 565 existe en algun PP o si es dato invalido.
"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("VERIFICACION: Referencia 565")
    print("=" * 80)
    print()

    # 1. Buscar en pedido_proveedor_detalle
    print("[1] Buscar referencia 565 en pedido_proveedor_detalle")
    cur.execute("""
        SELECT ppd.id, ppd.pedido_proveedor_id, ppd.linea, ppd.referencia,
               pp.numero_registro, pp.proveedor_importacion_id
        FROM pedido_proveedor_detalle ppd
        JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        WHERE ppd.referencia::text = '565'
        LIMIT 10
    """)

    ppd_rows = cur.fetchall()

    if ppd_rows:
        print(f"    ENCONTRADO: {len(ppd_rows)} rows en PPD con referencia 565")
        for row in ppd_rows[:5]:
            ppd_id, pp_id, linea, ref, pp_nro, prov_id = row
            print(f"      PPD {ppd_id}: PP {pp_nro} (pp_id={pp_id}) linea={linea} ref={ref} prov={prov_id}")
    else:
        print("    NO ENCONTRADO en pedido_proveedor_detalle")

    print()

    # 2. Buscar en tabla referencia
    print("[2] Buscar referencia 565 en tabla referencia")
    cur.execute("""
        SELECT r.id, r.proveedor_id, r.linea_id, r.codigo_proveedor,
               l.codigo_proveedor AS linea_codigo
        FROM referencia r
        JOIN linea l ON l.id = r.linea_id
        WHERE r.codigo_proveedor::text = '565'
        LIMIT 10
    """)

    ref_rows = cur.fetchall()

    if ref_rows:
        print(f"    ENCONTRADO: {len(ref_rows)} rows en tabla referencia")
        for row in ref_rows[:5]:
            ref_id, prov_id, linea_id, ref_cod, linea_cod = row
            print(f"      ref_id={ref_id}: linea {linea_cod} prov={prov_id}")
    else:
        print("    NO ENCONTRADO en tabla referencia")

    print()

    # 3. Verificar si linea 4202 + referencia 565 debería existir
    print("[3] Verificar combinacion linea 4202 + referencia 565")
    cur.execute("""
        SELECT l.id, l.codigo_proveedor, l.proveedor_id
        FROM linea l
        WHERE l.codigo_proveedor::text = '4202'
    """)

    linea_row = cur.fetchone()

    if linea_row:
        linea_id, linea_cod, prov_id = linea_row
        print(f"    Linea 4202: id={linea_id}, proveedor_id={prov_id}")

        # Buscar si existe referencia 565 para esa linea
        cur.execute("""
            SELECT id
            FROM referencia
            WHERE linea_id = %s AND codigo_proveedor::text = '565'
        """, (linea_id,))

        ref_row = cur.fetchone()

        if ref_row:
            print(f"    Referencia 565 EXISTE para linea 4202 (ref_id={ref_row[0]})")
        else:
            print(f"    Referencia 565 NO EXISTE para linea 4202")

            # Ver qué referencias existen para linea 4202
            cur.execute("""
                SELECT codigo_proveedor
                FROM referencia
                WHERE linea_id = %s
                ORDER BY codigo_proveedor
                LIMIT 20
            """, (linea_id,))

            refs_existentes = [r[0] for r in cur.fetchall()]
            print(f"    Referencias existentes para linea 4202: {refs_existentes}")

    print()

    # 4. Diagnóstico final
    print("=" * 80)
    print("[DIAGNOSTICO FINAL]")
    print("=" * 80)

    if not ppd_rows:
        print("  CONCLUSION: Referencia 565 NO EXISTE en pedido_proveedor_detalle")
        print("  IMPLICACION: No se puede hacer backfill desde PPD")
        print()
        print("  POSIBLES CAUSAS:")
        print("    1. Error en captura de Factura Interna (ref 565 no es valida)")
        print("    2. Referencia 565 es valida pero nunca se importo en un PP")
        print("    3. Codigo de referencia incorrecto en snapshot_json")
        print()
        print("  ACCION RECOMENDADA:")
        print("    - Verificar con usuario si ref 565 es valida")
        print("    - Si es valida: crear manualmente en tabla referencia")
        print("    - Si es error: corregir snapshot_json y rehidratar")
    else:
        print("  CONCLUSION: Referencia 565 EXISTE en PPD pero NO en tabla referencia")
        print("  IMPLICACION: Backfill incompleto - falta procesar ese PP")
        print()
        print("  ACCION RECOMENDADA:")
        print(f"    - Ejecutar backfill para PP que contiene ref 565")
        print(f"    - Luego rehidratar traspaso_detalle nuevamente")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
