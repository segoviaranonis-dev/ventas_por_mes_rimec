-- ═══════════════════════════════════════════════════════════════════════════
-- 020 — Poblar public.linea.grupo_estilo_id (bigint)
--
-- Estrategia (en orden):
--   1) Matching por nombre: linea.descripcion ↔ grupo_estilo_v2.descp_grupo_estilo
--      (lower + btrim, estable por id_grupo_estilo).
--   2) Consenso desde linea_referencia: para las líneas que sigan NULL, se toma
--      el grupo_estilo_id más frecuente entre las filas de linea_referencia que
--      apunten a esa línea (desempate por id_grupo_estilo).
--   3) Fallback por descripcion de cualquier referencia hija de la línea.
--
-- Idempotente: solo actualiza filas todavía NULL.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1) Matching directo por descripcion de la línea ─────────────────────────
UPDATE public.linea l
SET grupo_estilo_id = ge.id_grupo_estilo
FROM public.grupo_estilo_v2 ge
WHERE l.grupo_estilo_id IS NULL
  AND l.descripcion IS NOT NULL
  AND lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(l.descripcion))
  AND ge.id_grupo_estilo = (
      SELECT ge2.id_grupo_estilo
      FROM public.grupo_estilo_v2 ge2
      WHERE lower(btrim(ge2.descp_grupo_estilo)) = lower(btrim(l.descripcion))
      ORDER BY ge2.id_grupo_estilo
      LIMIT 1
  );

-- ── 2) Consenso desde linea_referencia (la 016 ya pobló este eje) ──────────
UPDATE public.linea l
SET grupo_estilo_id = sub.grupo_estilo_id
FROM (
    SELECT lr.linea_id, lr.grupo_estilo_id
    FROM (
        SELECT linea_id,
               grupo_estilo_id,
               COUNT(*) AS apariciones,
               ROW_NUMBER() OVER (
                   PARTITION BY linea_id
                   ORDER BY COUNT(*) DESC, grupo_estilo_id
               ) AS rn
        FROM public.linea_referencia
        WHERE grupo_estilo_id IS NOT NULL
        GROUP BY linea_id, grupo_estilo_id
    ) lr
    WHERE lr.rn = 1
) sub
WHERE l.grupo_estilo_id IS NULL
  AND sub.linea_id = l.id;

-- ── 3) Fallback por descripcion de alguna referencia hija de la línea ───────
UPDATE public.linea l
SET grupo_estilo_id = (
    SELECT ge.id_grupo_estilo
    FROM public.grupo_estilo_v2 ge
    JOIN public.referencia r ON r.linea_id = l.id
    WHERE lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
    ORDER BY ge.id_grupo_estilo
    LIMIT 1
)
WHERE l.grupo_estilo_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM public.referencia r
      JOIN public.grupo_estilo_v2 ge
        ON lower(btrim(ge.descp_grupo_estilo)) = lower(btrim(r.descripcion))
      WHERE r.linea_id = l.id
  );

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN
-- ═══════════════════════════════════════════════════════════════════════════
SELECT
    COUNT(*)                                     AS total_lineas,
    COUNT(grupo_estilo_id)                       AS con_estilo,
    COUNT(*) - COUNT(grupo_estilo_id)            AS sin_estilo
FROM public.linea;

-- Top 10 estilos asignados
SELECT ge.descp_grupo_estilo, COUNT(*) AS lineas
FROM public.linea l
JOIN public.grupo_estilo_v2 ge ON ge.id_grupo_estilo = l.grupo_estilo_id
GROUP BY ge.descp_grupo_estilo
ORDER BY lineas DESC
LIMIT 10;
