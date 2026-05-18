import psycopg2

conn_params = {
    "host": "aws-1-sa-east-1.pooler.supabase.com",
    "port": 6543,
    "database": "postgres",
    "user": "postgres.extrlcvcgypwazxipvqm",
    "password": "IJoFJbT8Qj0Q0w5m"
}

# 1. ACTUALIZACIÓN DE BASE DE DATOS
SQL_STANDARDIZE = [
    # Estandarización de producto_v2
    "ALTER TABLE producto_v2 RENAME COLUMN linea TO linea_id;",
    
    # DROP CASCADE para permitir cambios de nombres de columnas en vistas
    "DROP VIEW IF EXISTS v_stock_web CASCADE;",
    "DROP VIEW IF EXISTS v_stock_rimec CASCADE;",

    # v_stock_web (Estandarizada)
    """
    CREATE OR REPLACE VIEW v_stock_web AS
     WITH mov_agg AS (
             SELECT md.combinacion_id,
                sum(
                    CASE
                        WHEN m.tipo = 'INGRESO_COMPRA'::text AND m.almacen_destino_id = 1 THEN md.cantidad * md.signo
                        WHEN m.tipo = 'VENTA_WEB'::text AND m.almacen_origen_id = 1 THEN - md.cantidad
                        ELSE 0
                    END) AS stock_web,
                max(
                    CASE
                        WHEN m.tipo = 'INGRESO_COMPRA'::text THEN (tr.snapshot_json ->> 'id_marca'::text)::integer
                        ELSE NULL::integer
                    END) AS id_marca_ref
               FROM movimiento_detalle md
                 JOIN movimiento m ON m.id = md.movimiento_id
                 LEFT JOIN traspaso tr ON tr.numero_registro = m.documento_ref
              WHERE m.estado = 'CONFIRMADO'::text AND (m.tipo = 'INGRESO_COMPRA'::text AND m.almacen_destino_id = 1 OR m.tipo = 'VENTA_WEB'::text AND m.almacen_origen_id = 1)
              GROUP BY md.combinacion_id
             HAVING sum(
                    CASE
                        WHEN m.tipo = 'INGRESO_COMPRA'::text AND m.almacen_destino_id = 1 THEN md.cantidad * md.signo
                        WHEN m.tipo = 'VENTA_WEB'::text AND m.almacen_origen_id = 1 THEN - md.cantidad
                        ELSE 0
                    END) > 0
            )
     SELECT c.id AS combinacion_id,
        COALESCE(mv.descp_marca, '—'::text) AS descp_marca,
        l.id AS linea_id,
        l.codigo_proveedor::text AS linea_codigo,
        l.descripcion AS descp_linea,
        r.id AS referencia_id,
        r.codigo_proveedor::text AS referencia_codigo,
        r.descripcion AS descp_referencia,
        c.material_id,
        mat.codigo_proveedor::text AS material_code,
        mat.descripcion AS descp_material,
        c.color_id,
        col.codigo_proveedor::text AS color_code,
        col.nombre AS descp_color,
        col.hex_web,
        ( SELECT ppd.id_material
               FROM pedido_proveedor_detalle ppd
              WHERE ppd.linea = l.codigo_proveedor::text AND ppd.referencia = r.codigo_proveedor::text AND ppd.descp_material = mat.descripcion AND ppd.id_material IS NOT NULL
             LIMIT 1) AS id_material_f9,
        ( SELECT ppd.id_color
               FROM pedido_proveedor_detalle ppd
              WHERE ppd.linea = l.codigo_proveedor::text AND ppd.referencia = r.codigo_proveedor::text AND ppd.descp_color = col.nombre AND ppd.id_color IS NOT NULL
             LIMIT 1) AS id_color_f9,
        tl.talla_etiqueta AS talla_codigo,
        tl.orden_visual AS talla_orden,
        agg.stock_web,
        NULL::numeric AS precio_web,
        COALESCE(ge.descp_grupo_estilo, ''::text) AS descp_grupo_estilo,
        ge.id_grupo_estilo AS grupo_estilo_id
       FROM mov_agg agg
         JOIN combinacion c ON c.id = agg.combinacion_id
         JOIN linea l ON l.id = c.linea_id
         JOIN referencia r ON r.id = c.referencia_id
         LEFT JOIN linea_referencia lr ON lr.linea_id = l.id AND lr.referencia_id = r.id AND lr.proveedor_id = 654
         LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = lr.grupo_estilo_id
         LEFT JOIN material mat ON mat.id = c.material_id
         LEFT JOIN color col ON col.id = c.color_id
         JOIN talla tl ON tl.id = c.talla_id
         LEFT JOIN marca_v2 mv ON mv.id_marca = agg.id_marca_ref;
    """,

    # v_stock_rimec (Estandarizada)
    """
    CREATE OR REPLACE VIEW v_stock_rimec AS
    WITH decoded AS (
        SELECT 
            ppd.*,
            CASE 
                WHEN nullif(btrim(ppd.linea::text), '') ~ '^[0-9]+$' 
                THEN btrim(ppd.linea::text)::int8 
                ELSE NULL 
            END AS cast_linea_id,
            CASE 
                WHEN nullif(btrim(ppd.referencia::text), '') ~ '^[0-9]+$' 
                THEN btrim(ppd.referencia::text)::int8 
                ELSE NULL 
            END AS cast_referencia_id,
            CASE 
                WHEN nullif(btrim(ppd.style_code::text), '') ~ '^[0-9]+$' 
                THEN btrim(ppd.style_code::text)::int8 
                ELSE NULL 
            END AS cast_style_id
        FROM pedido_proveedor_detalle ppd
    )
    SELECT 
        d.id AS det_id,
        pp.id AS pp_id,
        pp.numero_registro AS pp_nro,
        COALESCE(pp.numero_proforma, '') AS proforma,
        (pp.fecha_arribo_estimada)::text AS eta,
        pp.estado AS pp_estado,
        d.id_marca AS marca_id,
        COALESCE(mv.descp_marca, '—') AS descp_marca,
        
        COALESCE(lr.linea_id, d.cast_linea_id) AS linea_id,
        COALESCE(lr.referencia_id, d.cast_referencia_id) AS referencia_id,
        COALESCE(lr.grupo_estilo_id, d.cast_style_id) AS grupo_estilo_id,
        COALESCE(lr.tipo_1_id, 0) AS tipo_1_id,
        
        COALESCE(d.linea, '') AS linea_codigo,
        COALESCE(d.referencia, '') AS referencia_codigo,
        COALESCE(
            (COALESCE(lr.grupo_estilo_id, d.cast_style_id))::text,
            btrim(COALESCE(d.style_code::text, '')),
            ''
        ) AS style_code,
        COALESCE(d.nombre, '') AS nombre,
        COALESCE(d.material_code, '') AS material_code,
        COALESCE(d.descp_material, '') AS descp_material,
        COALESCE(d.color_code, '') AS color_code,
        COALESCE(d.descp_color, '') AS descp_color,
        d.grades_json,
        COALESCE(d.cantidad_cajas, 0) AS cantidad_cajas,
        COALESCE(d.cantidad_pares, 0) AS cantidad_pares,
        CASE
            WHEN COALESCE(d.cantidad_cajas, 0) > 0 THEN d.cantidad_pares / d.cantidad_cajas
            ELSE 0
        END AS pares_por_caja,
        d.unit_fob_ajustado,
        pl.lpn,
        pl.lpc02,
        pl.lpc03,
        pl.lpc04,
        pl.nombre_caso_aplicado AS caso_precio,
        COALESCE(lr.descp_grupo_estilo, ge.descp_grupo_estilo, 'ESTILO ' || COALESCE(lr.grupo_estilo_id, d.cast_style_id)::text, '') AS descp_grupo_estilo,
        COALESCE(lr.descp_tipo_1, '') AS descp_tipo_1
    FROM decoded d
    JOIN pedido_proveedor pp ON pp.id = d.pedido_proveedor_id
    LEFT JOIN marca_v2 mv ON mv.id_marca = d.id_marca
    LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
    LEFT JOIN material m ON m.codigo_proveedor::text = d.material_code
    LEFT JOIN linea_referencia lr 
        ON lr.linea_id = d.cast_linea_id 
       AND lr.referencia_id = d.cast_referencia_id
    LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = COALESCE(lr.grupo_estilo_id, d.cast_style_id)
    LEFT JOIN LATERAL (
        SELECT pl2.lpn, pl2.lpc02, pl2.lpc03, pl2.lpc04, pl2.nombre_caso_aplicado
        FROM precio_lista pl2
        WHERE pl2.evento_id = COALESCE(ic.precio_evento_id, (
            SELECT pe.id FROM precio_evento pe
            WHERE pe.estado = 'cerrado'
            ORDER BY pe.created_at DESC
            LIMIT 1
        ))
        AND pl2.linea_id = COALESCE(lr.linea_id, d.cast_linea_id)
        AND pl2.referencia_id = COALESCE(lr.referencia_id, d.cast_referencia_id)
        AND pl2.material_id = m.id
        LIMIT 1
    ) pl ON true
    WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
      AND COALESCE(d.cantidad_pares, 0) > 0;
    """,

    # Grants
    "GRANT SELECT ON v_stock_web TO anon, authenticated, service_role;",
    "GRANT SELECT ON v_stock_rimec TO anon, authenticated, service_role;"
]

try:
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()
    for sql in SQL_STANDARDIZE:
        try:
            cur.execute(sql)
            print(f"Executed OK: {sql.strip()[:60]}...")
        except Exception as e:
            print(f"FAILED: {sql.strip()[:60]}... -> {e}")
            conn.rollback()
            continue
    conn.commit()
    print("Database standardization complete.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Fatal error: {e}")
