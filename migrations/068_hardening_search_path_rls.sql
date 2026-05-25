-- MIG-068: Hardening de Seguridad - search_path y RLS
-- Autor: Claude Code bajo directiva de Héctor Segovia
-- Fecha: 2026-05-21
-- Objetivo: Neutralizar vulnerabilidad de inyección en funciones SECURITY DEFINER
--           y auditar políticas RLS para bloquear escritura con anon_key

-- ============================================================================
-- PARTE 1: Fijar search_path en función SECURITY DEFINER
-- ============================================================================

-- Recrear función con search_path explícito para prevenir schema injection
-- NOTA: No usamos DROP porque constraints dependen de esta función
CREATE OR REPLACE FUNCTION public.fn_es_usuario_vendedor_o_admin(usr_id bigint)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp  -- HARDENING: Previene injection via search_path
AS $$
DECLARE
    v_rol text;
BEGIN
    SELECT r.nombre_rol INTO v_rol
    FROM public.usuario_v2 u
    JOIN public.maestro_rol_acceso r ON u.rol_id = r.id
    WHERE u.id_usuario = usr_id;

    RETURN v_rol IN ('VENDEDOR', 'ADMIN');
END;
$$;

COMMENT ON FUNCTION public.fn_es_usuario_vendedor_o_admin(bigint) IS
  'MIG-068: Función hardenizada con search_path fijo. '
  'Evalúa si un usuario tiene rol VENDEDOR o ADMIN para gobernanza transaccional.';

-- ============================================================================
-- PARTE 2: Auditoría y Hardening de RLS (Row-Level Security)
-- ============================================================================

-- DIRECTIVA DEL DIRECTOR:
-- "Queda terminantemente prohibido que la anon_key posea privilegios de
--  escritura (INSERT/UPDATE/DELETE)"

-- Verificar estado actual de RLS en tablas críticas
DO $$
BEGIN
    -- Habilitar RLS en usuario_v2 si no está habilitado
    IF NOT (SELECT relrowsecurity FROM pg_class WHERE relname = 'usuario_v2' AND relnamespace = 'public'::regnamespace) THEN
        ALTER TABLE public.usuario_v2 ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE 'RLS habilitado en usuario_v2';
    END IF;

    -- Habilitar RLS en pedido_venta_rimec si no está habilitado
    IF NOT (SELECT relrowsecurity FROM pg_class WHERE relname = 'pedido_venta_rimec' AND relnamespace = 'public'::regnamespace) THEN
        ALTER TABLE public.pedido_venta_rimec ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE 'RLS habilitado en pedido_venta_rimec';
    END IF;

    -- Habilitar RLS en factura_interna si no está habilitado
    IF NOT (SELECT relrowsecurity FROM pg_class WHERE relname = 'factura_interna' AND relnamespace = 'public'::regnamespace) THEN
        ALTER TABLE public.factura_interna ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE 'RLS habilitado en factura_interna';
    END IF;
END $$;

-- Política para usuario_v2: Bloquear INSERT/UPDATE/DELETE con anon role
-- Solo permitir SELECT para roles anónimos (catálogo de vendedores)
DROP POLICY IF EXISTS policy_usuario_v2_anon_readonly ON public.usuario_v2;
CREATE POLICY policy_usuario_v2_anon_readonly
    ON public.usuario_v2
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- Bloquear modificaciones con anon
DROP POLICY IF EXISTS policy_usuario_v2_anon_no_write ON public.usuario_v2;
CREATE POLICY policy_usuario_v2_anon_no_write
    ON public.usuario_v2
    FOR INSERT
    TO anon
    WITH CHECK (false);

DROP POLICY IF EXISTS policy_usuario_v2_anon_no_update ON public.usuario_v2;
CREATE POLICY policy_usuario_v2_anon_no_update
    ON public.usuario_v2
    FOR UPDATE
    TO anon
    USING (false);

DROP POLICY IF EXISTS policy_usuario_v2_anon_no_delete ON public.usuario_v2;
CREATE POLICY policy_usuario_v2_anon_no_delete
    ON public.usuario_v2
    FOR DELETE
    TO anon
    USING (false);

-- Política para pedido_venta_rimec: Bloquear escritura con anon
DROP POLICY IF EXISTS policy_pedido_venta_anon_readonly ON public.pedido_venta_rimec;
CREATE POLICY policy_pedido_venta_anon_readonly
    ON public.pedido_venta_rimec
    FOR SELECT
    TO anon, authenticated
    USING (true);

DROP POLICY IF EXISTS policy_pedido_venta_anon_no_write ON public.pedido_venta_rimec;
CREATE POLICY policy_pedido_venta_anon_no_write
    ON public.pedido_venta_rimec
    FOR INSERT
    TO anon
    WITH CHECK (false);

DROP POLICY IF EXISTS policy_pedido_venta_anon_no_update ON public.pedido_venta_rimec;
CREATE POLICY policy_pedido_venta_anon_no_update
    ON public.pedido_venta_rimec
    FOR UPDATE
    TO anon
    USING (false);

DROP POLICY IF EXISTS policy_pedido_venta_anon_no_delete ON public.pedido_venta_rimec;
CREATE POLICY policy_pedido_venta_anon_no_delete
    ON public.pedido_venta_rimec
    FOR DELETE
    TO anon
    USING (false);

-- Política para factura_interna: Bloquear escritura con anon
DROP POLICY IF EXISTS policy_factura_interna_anon_readonly ON public.factura_interna;
CREATE POLICY policy_factura_interna_anon_readonly
    ON public.factura_interna
    FOR SELECT
    TO anon, authenticated
    USING (true);

DROP POLICY IF EXISTS policy_factura_interna_anon_no_write ON public.factura_interna;
CREATE POLICY policy_factura_interna_anon_no_write
    ON public.factura_interna
    FOR INSERT
    TO anon
    WITH CHECK (false);

DROP POLICY IF EXISTS policy_factura_interna_anon_no_update ON public.factura_interna;
CREATE POLICY policy_factura_interna_anon_no_update
    ON public.factura_interna
    FOR UPDATE
    TO anon
    USING (false);

DROP POLICY IF EXISTS policy_factura_interna_anon_no_delete ON public.factura_interna;
CREATE POLICY policy_factura_interna_anon_no_delete
    ON public.factura_interna
    FOR DELETE
    TO anon
    USING (false);

-- ============================================================================
-- PARTE 3: Comentarios de auditoría
-- ============================================================================

COMMENT ON TABLE public.usuario_v2 IS
  'MIG-068: RLS habilitado. anon_key bloqueada para INSERT/UPDATE/DELETE.';

COMMENT ON TABLE public.pedido_venta_rimec IS
  'MIG-068: RLS habilitado. anon_key bloqueada para INSERT/UPDATE/DELETE.';

COMMENT ON TABLE public.factura_interna IS
  'MIG-068: RLS habilitado. anon_key bloqueada para INSERT/UPDATE/DELETE.';
