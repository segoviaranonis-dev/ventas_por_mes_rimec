es-- =============================================================================
-- 031 · Políticas RLS para retail_multitienda_staging (Supabase)
-- Ejecutar DESPUÉS de 030 si activaste "Run and enable RLS" sin políticas.
-- Idempotente: DROP POLICY IF EXISTS + CREATE.
-- =============================================================================

ALTER TABLE public.retail_multitienda_staging ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS retail_staging_authenticated_rw ON public.retail_multitienda_staging;
CREATE POLICY retail_staging_authenticated_rw
    ON public.retail_multitienda_staging
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS retail_staging_service_rw ON public.retail_multitienda_staging;
CREATE POLICY retail_staging_service_rw
    ON public.retail_multitienda_staging
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

COMMENT ON POLICY retail_staging_authenticated_rw ON public.retail_multitienda_staging IS
  'Permite CRUD vía rol authenticated (API JWT). Ajustar si querés reglas por usuario.';
COMMENT ON POLICY retail_staging_service_rw ON public.retail_multitienda_staging IS
  'Backend con service_role (bypass típico en API; política explícita por claridad).';
