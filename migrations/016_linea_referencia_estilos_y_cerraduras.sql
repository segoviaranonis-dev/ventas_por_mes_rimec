-- ═══════════════════════════════════════════════════════════════════════════
-- 016 — Poblar linea_referencia (lógica v_stock_rimec), cerraduras, verificación
--
-- Lógica de negocio (Héctor):
--   · Línea + Referencia = estilo (grupo_estilo_id en linea_referencia).
--   · Resolución de estilo (esta BD no tiene linea.grupo_estilo_id):
--       (1) grupo_estilo_v2 por nombre = linea.descripcion (lower+btrim)
--       (2) si NULL: grupo_estilo_v2 por nombre = referencia.descripcion
--     ORDER BY id_grupo_estilo LIMIT 1 en cada match (estable).
--
-- referencia: UNIQUE (proveedor_id, linea_id, codigo_proveedor) — migración 004.
-- El bloque final es idempotente (solo crea el constraint si falta).
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- Función inline vía subconsulta repetida (PostgreSQL no requiere función persistida).
-- ge_por_linea_nombre(l_id) → id o NULL
-- ge_por_ref_nombre(r_id) → id o NULL

-- 1) Completar grupo_estilo_id en filas ya existentes de linea_referencia
UPDATE linea_referencia lr
SET grupo_estilo_id = COALESCE(
    (SELECT ge.id_grupo_estilo
     FROM grupo_estilo_v2 ge
     WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
     ORDER BY ge.id_grupo_estilo
     LIMIT 1),
    (SELECT ge.id_grupo_estilo
     FROM grupo_estilo_v2 ge
     JOIN referencia r0 ON r0.id = lr.referencia_id
     WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r0.descripcion))
     ORDER BY ge.id_grupo_estilo
     LIMIT 1)
)
FROM linea l
WHERE l.id = lr.linea_id
  AND lr.grupo_estilo_id IS NULL
  AND COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         JOIN referencia r0 ON r0.id = lr.referencia_id
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r0.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
      ) IS NOT NULL;

-- 2) INSERT — cohorte misma geometría que v_stock_rimec (PP ABIERTO/ENVIADO + pares)
INSERT INTO linea_referencia (linea_id, referencia_id, proveedor_id, grupo_estilo_id, tipo_1_id)
SELECT DISTINCT
    ref_j.linea_id,
    ref_j.id,
    ref_j.proveedor_id,
    COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(ref_j.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
    ),
    NULL::bigint
FROM pedido_proveedor_detalle ppd
JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
JOIN linea l ON l.codigo_proveedor::text = ppd.linea
JOIN referencia ref_j
  ON ref_j.codigo_proveedor::text = ppd.referencia
 AND ref_j.linea_id = l.id
WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
  AND COALESCE(ppd.cantidad_pares, 0) > 0
  AND COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(ref_j.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
      ) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM linea_referencia x
    WHERE x.linea_id = ref_j.linea_id AND x.referencia_id = ref_j.id
  );

-- 3) INSERT — resto del maestro referencia (par línea×ref sin fila lr)
INSERT INTO linea_referencia (linea_id, referencia_id, proveedor_id, grupo_estilo_id, tipo_1_id)
SELECT
    r.linea_id,
    r.id,
    r.proveedor_id,
    COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
    ),
    NULL::bigint
FROM referencia r
JOIN linea l ON l.id = r.linea_id
WHERE COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
      ) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM linea_referencia x
    WHERE x.linea_id = r.linea_id AND x.referencia_id = r.id
  );

-- 4) INSERT — pares en precio_lista aún sin lr
INSERT INTO linea_referencia (linea_id, referencia_id, proveedor_id, grupo_estilo_id, tipo_1_id)
SELECT DISTINCT
    pl.linea_id,
    pl.referencia_id,
    r.proveedor_id,
    COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
    ),
    NULL::bigint
FROM precio_lista pl
JOIN referencia r ON r.id = pl.referencia_id
JOIN linea l ON l.id = pl.linea_id
WHERE COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
      ) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM linea_referencia x
    WHERE x.linea_id = pl.linea_id AND x.referencia_id = pl.referencia_id
  );

-- 5) INSERT — pares en combinacion aún sin lr
INSERT INTO linea_referencia (linea_id, referencia_id, proveedor_id, grupo_estilo_id, tipo_1_id)
SELECT DISTINCT
    c.linea_id,
    c.referencia_id,
    r.proveedor_id,
    COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
    ),
    NULL::bigint
FROM combinacion c
JOIN referencia r ON r.id = c.referencia_id
JOIN linea l ON l.id = c.linea_id
WHERE COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
      ) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM linea_referencia x
    WHERE x.linea_id = c.linea_id AND x.referencia_id = c.referencia_id
  );

-- 5b) INSERT — pares en stock_bazar (si la tabla existe en el proyecto)
INSERT INTO linea_referencia (linea_id, referencia_id, proveedor_id, grupo_estilo_id, tipo_1_id)
SELECT DISTINCT
    sb.linea_id,
    sb.referencia_id,
    r.proveedor_id,
    COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
    ),
    NULL::bigint
FROM stock_bazar sb
JOIN referencia r ON r.id = sb.referencia_id
JOIN linea l ON l.id = sb.linea_id
WHERE COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
      ) IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM linea_referencia x
    WHERE x.linea_id = sb.linea_id AND x.referencia_id = sb.referencia_id
  );

-- 6) Segundo pase UPDATE por si quedaron NULL (tras inserts 5b)
UPDATE linea_referencia lr
SET grupo_estilo_id = COALESCE(
    (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
     WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
     ORDER BY ge.id_grupo_estilo LIMIT 1),
    (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
     JOIN referencia r0 ON r0.id = lr.referencia_id
     WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r0.descripcion))
     ORDER BY ge.id_grupo_estilo LIMIT 1)
)
FROM linea l
WHERE l.id = lr.linea_id
  AND lr.grupo_estilo_id IS NULL
  AND COALESCE(
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1),
        (SELECT ge.id_grupo_estilo FROM grupo_estilo_v2 ge
         JOIN referencia r0 ON r0.id = lr.referencia_id
         WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r0.descripcion))
         ORDER BY ge.id_grupo_estilo LIMIT 1)
      ) IS NOT NULL;

-- 7) Dedupe: conservar id mínimo por (linea_id, referencia_id)
DELETE FROM linea_referencia lr
USING linea_referencia keep
WHERE lr.linea_id = keep.linea_id
  AND lr.referencia_id = keep.referencia_id
  AND lr.id > keep.id;

-- 8) UNIQUE (linea_id, referencia_id) en linea_referencia
ALTER TABLE linea_referencia
    DROP CONSTRAINT IF EXISTS uq_linea_referencia_linea_ref;

ALTER TABLE linea_referencia
    ADD CONSTRAINT uq_linea_referencia_linea_ref
    UNIQUE (linea_id, referencia_id);

-- 9) referencia — triple UNIQUE migración 004 (idempotente)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_referencia_proveedor_linea_codigo'
          AND conrelid = 'public.referencia'::regclass
    ) THEN
        ALTER TABLE referencia
            ADD CONSTRAINT uq_referencia_proveedor_linea_codigo
            UNIQUE (proveedor_id, linea_id, codigo_proveedor);
    END IF;
END $$;

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN — ejecutar después (o copiar al editor SQL de Supabase)
-- Cohortes "activas": tránsito RIMEC + precio_lista + combinacion
-- Esperado: activos_con_lr_sin_estilo = 0
-- ═══════════════════════════════════════════════════════════════════════════

WITH activos AS (
    SELECT DISTINCT ref_j.linea_id, ref_j.id AS referencia_id
    FROM pedido_proveedor_detalle ppd
    JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
    JOIN linea l ON l.codigo_proveedor::text = ppd.linea
    JOIN referencia ref_j
      ON ref_j.codigo_proveedor::text = ppd.referencia
     AND ref_j.linea_id = l.id
    WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
      AND COALESCE(ppd.cantidad_pares, 0) > 0
    UNION
    SELECT DISTINCT linea_id, referencia_id FROM precio_lista
    UNION
    SELECT DISTINCT linea_id, referencia_id FROM combinacion
    UNION
    SELECT DISTINCT linea_id, referencia_id FROM stock_bazar
    WHERE linea_id IS NOT NULL AND referencia_id IS NOT NULL
)
SELECT
    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1
            FROM linea_referencia lr
            WHERE lr.linea_id = a.linea_id
              AND lr.referencia_id = a.referencia_id
              AND lr.grupo_estilo_id IS NULL
        )
    ) AS activos_con_lr_sin_estilo,
    COUNT(*) FILTER (
        WHERE NOT EXISTS (
            SELECT 1
            FROM linea_referencia lr
            WHERE lr.linea_id = a.linea_id
              AND lr.referencia_id = a.referencia_id
        )
    ) AS activos_sin_fila_lr,
    COUNT(*) AS total_pares_activos_distintos
FROM activos a;
