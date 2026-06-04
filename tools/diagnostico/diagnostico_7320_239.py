"""
Diagnóstico 7320/239 - 8 colores con 1 caja
OT: Catálogo web muestra 8 chips pero solo 1 caja disponible
"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("PASO 0 - Verificar que vista tiene columnas nuevas")
    print("=" * 80)
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'v_stock_rimec'
          AND column_name IN ('cajas_disponibles', 'pares_vendidos', 'saldo_pares')
        ORDER BY column_name
    """)
    cols = cur.fetchall()
    print(f"Columnas encontradas: {[c[0] for c in cols]}")
    if len(cols) < 3:
        print("⚠️  ALERTA: Vista no tiene columnas nuevas. Aplicar fix_v_stock_rimec.py")
        cur.close()
        conn.close()
        return
    print("✓ Vista actualizada\n")

    print("=" * 80)
    print("PASO 1A - Vista v_stock_rimec (lo que lee la web)")
    print("=" * 80)
    cur.execute("""
        SELECT det_id, pp_id, pp_nro, descp_color, color_code, material_code,
               cantidad_cajas, cantidad_pares,
               COALESCE(pares_vendidos, 0) as pares_vendidos,
               COALESCE(saldo_pares, cantidad_pares) as saldo_pares,
               COALESCE(cajas_disponibles, cantidad_cajas) as cajas_disponibles
        FROM v_stock_rimec
        WHERE linea_codigo = '7320' AND referencia_codigo = '239'
        ORDER BY cajas_disponibles DESC, descp_color
    """)
    rows_vista = cur.fetchall()
    print(f"Total filas en vista: {len(rows_vista)}")
    print()
    print("det_id | pp_id | pp_nro  | color           | color_code | material | cj_tot | pares | vendidos | saldo | cj_disp")
    print("-" * 120)
    for r in rows_vista:
        print(f"{r[0]:6} | {r[1]:5} | {r[2]:7} | {r[3]:15} | {r[4]:10} | {r[5]:8} | {r[6]:6} | {r[7]:5} | {r[8]:8} | {r[9]:5} | {r[10]:7}")
    print()

    con_stock = sum(1 for r in rows_vista if r[10] > 0)
    print(f"✓ Filas con cajas_disponibles > 0: {con_stock}/{len(rows_vista)}\n")

    print("=" * 80)
    print("PASO 1B - Tabla base pedido_proveedor_detalle (sin JOINs)")
    print("=" * 80)
    cur.execute("""
        SELECT ppd.id AS det_id, pp.numero_registro AS pp_nro,
               ppd.descp_color, ppd.color_code, ppd.material_code,
               ppd.cantidad_cajas, ppd.cantidad_pares,
               COALESCE(ppd.pares_vendidos, 0) as pares_vendidos,
               pp.estado, pp.proveedor_importacion_id
        FROM pedido_proveedor_detalle ppd
        JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        WHERE ppd.linea = '7320' AND ppd.referencia = '239'
          AND pp.estado IN ('ABIERTO', 'ENVIADO')
        ORDER BY ppd.id
    """)
    rows_base = cur.fetchall()
    print(f"Total filas en tabla base: {len(rows_base)}")
    print()
    print("det_id | pp_nro  | color           | color_code | material | cj | pares | vendidos | estado  | prov_id")
    print("-" * 120)
    for r in rows_base:
        print(f"{r[0]:6} | {r[1]:7} | {r[2]:15} | {r[3]:10} | {r[4]:8} | {r[5]:2} | {r[6]:5} | {r[7]:8} | {r[8]:7} | {r[9] or 'NULL':7}")
    print()

    print("=" * 80)
    print("PASO 1C - Duplicados por det_id en vista (bug de JOIN)")
    print("=" * 80)
    cur.execute("""
        SELECT det_id, COUNT(*) AS n
        FROM v_stock_rimec
        WHERE linea_codigo = '7320' AND referencia_codigo = '239'
        GROUP BY det_id
        HAVING COUNT(*) > 1
    """)
    dups = cur.fetchall()
    if dups:
        print(f"⚠️  DUPLICADOS ENCONTRADOS: {len(dups)} det_id repetidos")
        for d in dups:
            print(f"  det_id {d[0]}: {d[1]} veces")
    else:
        print("✓ Sin duplicados (cada det_id aparece 1 vez)\n")

    print("=" * 80)
    print("PASO 2 - ¿Mezcla de varios PP en una tarjeta?")
    print("=" * 80)
    cur.execute("""
        SELECT pp_nro, pp_id, descp_color,
               COALESCE(cajas_disponibles, cantidad_cajas) as cajas_disponibles,
               det_id
        FROM v_stock_rimec
        WHERE linea_codigo = '7320' AND referencia_codigo = '239'
          AND COALESCE(cajas_disponibles, cantidad_cajas) > 0
        ORDER BY pp_nro, descp_color
    """)
    pp_mix = cur.fetchall()
    print(f"Variantes con stock > 0: {len(pp_mix)}")
    print()
    print("pp_nro  | pp_id | color           | cj_disp | det_id")
    print("-" * 70)
    for r in pp_mix:
        print(f"{r[0]:7} | {r[1]:5} | {r[2]:15} | {r[3]:7} | {r[4]:6}")
    print()

    pp_distintos = len(set(r[0] for r in pp_mix))
    if pp_distintos > 1:
        print(f"⚠️  MEZCLA DE PP: {pp_distintos} pedidos distintos en misma tarjeta")
        print("    Causa: agruparProductos() no incluye pp_id en prodKey")
    else:
        print(f"✓ Un solo PP: {pp_mix[0][0] if pp_mix else 'N/A'}\n")

    print("=" * 80)
    print("CONCLUSIÓN")
    print("=" * 80)
    if len(rows_vista) == 1 and rows_vista[0][10] == 1:
        print("✓ Dato correcto: 1 fila con 1 caja → problema en frontend/caché")
    elif len(rows_vista) == len(rows_base) and len(rows_vista) == 8:
        if pp_distintos > 1:
            print("✓ Dato correcto: 8 filas reales de varios PP → UI coherente pero agrupación incorrecta")
        else:
            print("✓ Dato real: 8 colores con stock en BD → verificar si Excel/proforma es correcto")
    elif dups:
        print("✗ Vista con JOIN duplicado → reaplicar fix_v_stock_rimec.py con DISTINCT ON")
    elif len(rows_vista) != len(rows_base):
        print("✗ Vista tiene diferente cantidad que tabla base → JOIN fan-out, revisar definición")
    else:
        print("? Caso no identificado → revisar definición de vista y frontend")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
