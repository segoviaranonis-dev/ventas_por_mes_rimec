-- =============================================================================
-- MIGRACIÓN: 001_create_v_ventas_pivot (v2 - con categoria)
-- SISTEMA: RIMEC Business Intelligence
-- DESCRIPCIÓN: Vista pivot que pre-agrega ventas 2025/2026 en columnas separadas.
--              Incluye id_categoria y categoria para filtrado correcto.
-- =============================================================================

DROP VIEW IF EXISTS v_ventas_pivot;

CREATE VIEW v_ventas_pivot AS
SELECT
    TRIM(t.descp_tipo)                              AS tipo,
    TRIM(m.descp_marca)                             AS marca,
    TRIM(c.descp_cliente)                           AS cliente,
    v.id_cliente::TEXT                              AS codigo_cliente,
    TRIM(ven.descp_vendedor)                        AS vendedor,
    COALESCE(TRIM(cad.descp_cadena), 'S/C')        AS cadena,
    EXTRACT(MONTH FROM v.fecha)::INTEGER            AS mes_idx,
    v.id_categoria,
    TRIM(cat.descp_categoria)                       AS categoria,
    SUM(CASE WHEN EXTRACT(YEAR FROM v.fecha) = 2026
             THEN COALESCE(v.monto, 0) ELSE 0 END) AS monto_26,
    SUM(CASE WHEN EXTRACT(YEAR FROM v.fecha) = 2025
             THEN COALESCE(v.monto, 0) ELSE 0 END) AS monto_25,
    SUM(CASE WHEN EXTRACT(YEAR FROM v.fecha) = 2026
             THEN COALESCE(v.cantidad, 0) ELSE 0 END) AS cant_26,
    SUM(CASE WHEN EXTRACT(YEAR FROM v.fecha) = 2025
             THEN COALESCE(v.cantidad, 0) ELSE 0 END) AS cant_25
FROM registro_ventas_general_v2 v
JOIN  tipo_v2          t   ON v.id_tipo      = t.id_tipo
JOIN  marca_v2         m   ON v.id_marca     = m.id_marca
JOIN  cliente_v2       c   ON v.id_cliente   = c.id_cliente
JOIN  vendedor_v2      ven ON v.id_vendedor  = ven.id_vendedor
JOIN  categoria_v2     cat ON v.id_categoria = cat.id_categoria
LEFT JOIN cliente_cadena_v2 cc  ON v.id_cliente = cc.id_cliente
LEFT JOIN cadena_v2        cad  ON cc.id_cadena  = cad.id_cadena
GROUP BY
    t.descp_tipo, m.descp_marca, c.descp_cliente, v.id_cliente,
    ven.descp_vendedor, cad.descp_cadena,
    EXTRACT(MONTH FROM v.fecha)::INTEGER,
    v.id_categoria, cat.descp_categoria;
