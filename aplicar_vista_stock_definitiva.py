"""
Aplicar vista v_stock_rimec DEFINITIVA con cajas_disponibles
Incluye: DISTINCT ON, proveedor_id en JOINs, pares_vendidos, saldo_pares
"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

SQL = r"""
CREATE OR REPLACE VIEW v_stock_rimec AS
SELECT DISTINCT ON (ppd.id)
    ppd.id AS det_id,
    pp.id AS pp_id,
    pp.numero_registro AS pp_nro,
    COALESCE(pp.numero_proforma, '') AS proforma,
    (pp.fecha_arribo_estimada)::text AS eta,
    pp.estado AS pp_estado,
    l.marca_id::bigint AS marca_id,
    COALESCE(mv.descp_marca, '—') AS descp_marca,
    COALESCE(lr.linea_id, l.id, x.cast_linea_id)::bigint AS linea_id,
    COALESCE(lr.referencia_id, ref_j.id, x.cast_referencia_id)::bigint AS referencia_id,
    COALESCE(lr.grupo_estilo_id, x.cast_style_id)::bigint AS grupo_estilo_id,
    lr.tipo_1_id::bigint AS tipo_1_id,
    COALESCE(ppd.linea, '') AS linea_codigo,
    COALESCE(ppd.referencia, '') AS referencia_codigo,
    COALESCE(
        (COALESCE(lr.grupo_estilo_id, x.cast_style_id))::text,
        btrim(COALESCE(ppd.style_code::text, '')),
        ''
    ) AS style_code,
    COALESCE(ppd.nombre, '') AS nombre,
    COALESCE(ppd.material_code, '') AS material_code,
    COALESCE(ppd.descp_material, '') AS descp_material,
    COALESCE(ppd.color_code, '') AS color_code,
    COALESCE(ppd.descp_color, '') AS descp_color,
    col_j.hex_web AS color_hex,
    ppd.grades_json,
    COALESCE(ppd.cantidad_cajas, 0) AS cantidad_cajas,
    COALESCE(ppd.cantidad_pares, 0) AS cantidad_pares,
    COALESCE(ppd.pares_vendidos, 0) AS pares_vendidos,
    GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) AS saldo_pares,
    CASE
        WHEN COALESCE(ppd.cantidad_cajas, 0) > 0 THEN ppd.cantidad_pares / ppd.cantidad_cajas
        ELSE 0
    END AS pares_por_caja,
    GREATEST(
        0,
        COALESCE(ppd.cantidad_cajas, 0) - CASE
            WHEN COALESCE(ppd.cantidad_cajas, 0) > 0
             AND COALESCE(ppd.cantidad_pares, 0) > 0
            THEN (
                COALESCE(ppd.pares_vendidos, 0)
                + (ppd.cantidad_pares / ppd.cantidad_cajas)
                - 1
            ) / (ppd.cantidad_pares / ppd.cantidad_cajas)
            ELSE COALESCE(ppd.pares_vendidos, 0)
        END
    )::integer AS cajas_disponibles,
    ppd.unit_fob_ajustado,
    pl.lpn,
    pl.lpc02,
    pl.lpc03,
    pl.lpc04,
    pl.nombre_caso_aplicado AS caso_precio,
    l.caso_id AS caso_id,
    COALESCE(cpb.nombre_caso, '') AS descp_caso,
    COALESCE(ge.descp_grupo_estilo, lr.descp_grupo_estilo, '') AS descp_grupo_estilo,
    COALESCE(t1.descp_tipo_1, lr.descp_tipo_1, '') AS descp_tipo_1,
    CASE
        WHEN COALESCE(ppd.linea, '') <> ''
         AND COALESCE(ppd.referencia, '') <> ''
         AND COALESCE(ppd.material_code, '') <> ''
         AND COALESCE(ppd.color_code, '') <> ''
        THEN 'https://extrlcvcgypwazxipvqm.supabase.co/storage/v1/object/public/productos/'
             || ppd.linea || '-' || ppd.referencia || '-'
             || ppd.material_code || '-' || ppd.color_code || '.jpg'
        ELSE NULL
    END AS imagen_url
FROM pedido_proveedor_detalle ppd
JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
LEFT JOIN material m
    ON m.codigo_proveedor::text = ppd.material_code
   AND m.proveedor_id = pp.proveedor_importacion_id
LEFT JOIN linea l
    ON l.codigo_proveedor::text = ppd.linea
   AND l.proveedor_id = pp.proveedor_importacion_id
LEFT JOIN marca_v2 mv ON mv.id_marca = l.marca_id
LEFT JOIN caso_precio_biblioteca cpb ON cpb.id = l.caso_id
LEFT JOIN color col_j
    ON col_j.codigo_proveedor::text = ppd.color_code
   AND col_j.proveedor_id = pp.proveedor_importacion_id
   AND col_j.activo = TRUE
LEFT JOIN referencia ref_j
    ON ref_j.codigo_proveedor::text = ppd.referencia
   AND ref_j.linea_id = l.id
CROSS JOIN LATERAL (
    SELECT
        CASE
            WHEN nullif(btrim(ppd.linea::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.linea::text)::bigint
            ELSE NULL::bigint
        END AS cast_linea_id,
        CASE
            WHEN nullif(btrim(ppd.referencia::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.referencia::text)::bigint
            ELSE NULL::bigint
        END AS cast_referencia_id,
        CASE
            WHEN nullif(btrim(ppd.style_code::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.style_code::text)::bigint
            ELSE NULL::bigint
        END AS cast_style_id
) x
LEFT JOIN linea_referencia lr
    ON lr.linea_id = l.id
   AND lr.referencia_id = ref_j.id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = COALESCE(lr.grupo_estilo_id, x.cast_style_id)
LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
LEFT JOIN LATERAL (
    SELECT pl2.lpn, pl2.lpc02, pl2.lpc03, pl2.lpc04, pl2.nombre_caso_aplicado
    FROM precio_lista pl2
    WHERE pl2.evento_id = COALESCE(ic.precio_evento_id, (
        SELECT pe.id FROM precio_evento pe
        WHERE pe.estado = 'cerrado'
        ORDER BY pe.created_at DESC
        LIMIT 1
    ))
    AND pl2.linea_id = COALESCE(l.id, ref_j.linea_id)
    AND pl2.referencia_id = ref_j.id
    AND pl2.material_id = m.id
    LIMIT 1
) pl ON true
WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
  AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
ORDER BY ppd.id;
"""

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("[1/3] Dropping old view...")
    cur.execute("DROP VIEW IF EXISTS v_stock_rimec CASCADE")
    conn.commit()
    print("[OK]")

    print("[2/3] Creating new view with cajas_disponibles, pares_vendidos, saldo_pares...")
    try:
        cur.execute(SQL)
        conn.commit()
        print("[OK] Vista recreada")
    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return

    print("[3/3] Verifying columns exist...")
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'v_stock_rimec'
          AND column_name IN ('cajas_disponibles', 'pares_vendidos', 'saldo_pares')
        ORDER BY column_name
    """)
    cols = cur.fetchall()
    print(f"Columnas nuevas: {[c[0] for c in cols]}")

    if len(cols) == 3:
        print("\n[EXITO] Vista aplicada correctamente")

        # Verificar caso 7320/239
        print("\n[VERIFICACION] Modelo 7320/239:")
        cur.execute("""
            SELECT det_id, descp_color, cantidad_cajas, pares_vendidos,
                   saldo_pares, cajas_disponibles
            FROM v_stock_rimec
            WHERE linea_codigo = '7320' AND referencia_codigo = '239'
            ORDER BY cajas_disponibles DESC, descp_color
            LIMIT 10
        """)
        rows = cur.fetchall()
        if rows:
            print(f"  Filas encontradas: {len(rows)}")
            print("  det_id | color           | cj_tot | vendidos | saldo | cj_disp")
            print("  " + "-" * 70)
            for r in rows:
                print(f"  {r[0]:6} | {r[1]:15} | {r[2]:6} | {r[3]:8} | {r[4]:5} | {r[5]:7}")
        else:
            print("  No se encontraron filas (puede ser OK si no hay stock)")
    else:
        print(f"\n[ADVERTENCIA] Faltan columnas. Esperadas: 3, encontradas: {len(cols)}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
