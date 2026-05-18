import psycopg2

conn_params = {
    "host": "aws-1-sa-east-1.pooler.supabase.com",
    "port": 6543,
    "database": "postgres",
    "user": "postgres.extrlcvcgypwazxipvqm",
    "password": "IJoFJbT8Qj0Q0w5m"
}

SQL = r"""
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
    COALESCE(mv.descp_marca, '—') AS marca,
    
    -- TRIANGULACIÓN DE IDs: Prioridad absoluta al match numérico con linea_referencia
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
    COALESCE(d.descp_material, '') AS material_descripcion,
    COALESCE(d.color_code, '') AS color_code,
    COALESCE(d.descp_color, '') AS color_nombre,
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
    COALESCE(lr.descp_grupo_estilo, ge.descp_grupo_estilo, 'ESTILO ' || COALESCE(lr.grupo_estilo_id, d.cast_style_id)::text, '') AS estilo,
    COALESCE(lr.descp_tipo_1, '') AS tipo_1
FROM decoded d
JOIN pedido_proveedor pp ON pp.id = d.pedido_proveedor_id
LEFT JOIN marca_v2 mv ON mv.id_marca = d.id_marca
LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
LEFT JOIN material m ON m.codigo_proveedor::text = d.material_code
-- SOLDADURA: Join por IDs casteados (Triangulación)
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
"""

try:
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()
    cur.execute("DROP VIEW IF EXISTS v_stock_rimec CASCADE")
    cur.execute(SQL)
    conn.commit()
    print("OK — v_stock_rimec recreada con Soldadura de IDs.")
    
    # Check 2126 / 526
    print("\n--- VERIFICACIÓN LINEA 2126 / REF 526 ---")
    cur.execute("SELECT det_id, linea_codigo, referencia_codigo, linea_id, referencia_id, grupo_estilo_id, estilo FROM v_stock_rimec WHERE linea_codigo ~ '2126' AND referencia_codigo ~ '526' LIMIT 5")
    rows = cur.fetchall()
    if rows:
        print("Fila encontrada:")
        for r in rows:
            print(r)
    else:
        print("No se encontró la combinación 2126/526 en ABIERTO/ENVIADO con pares.")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
