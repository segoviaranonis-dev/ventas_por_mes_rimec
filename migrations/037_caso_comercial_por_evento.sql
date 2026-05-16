-- ═══════════════════════════════════════════════════════════════════════════
-- 037 — Caso comercial desacoplado del pilar linea
--
-- Arquitectura: precio_evento (listado/temporada) + precio_evento_caso +
-- precio_evento_linea_excepcion + precio_lista. linea.caso_id queda legacy.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

COMMENT ON COLUMN public.linea.caso_id IS
  'LEGACY · No escribir en producción (2026-05). Caso comercial por precio_evento '
  'y precio_evento_linea_excepcion; plantillas en caso_precio_biblioteca.lineas.';

-- Índice para resolver excepciones por evento (Paso 2 / reportes)
CREATE INDEX IF NOT EXISTS idx_pele_caso_linea
    ON public.precio_evento_linea_excepcion (caso_id, linea_id);

CREATE INDEX IF NOT EXISTS idx_pec_evento
    ON public.precio_evento_caso (evento_id);

COMMIT;

SELECT '037 aplicada: caso comercial por evento (linea.caso_id legacy)' AS estado;

-- Siguiente paso recomendado: migrations/038_null_linea_caso_id_legacy.sql
