-- ============================================================================
-- MIGRACIÓN 099: Sistema de Notificaciones Internas
-- DESCRIPCIÓN: Tabla de notificaciones + trigger automático cuando FI confirmada
-- AUTOR: Héctor & Claude
-- FECHA: 2026-05-27
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- TABLA: notificaciones
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.notificaciones (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT NOT NULL REFERENCES public.usuario_v2(id_usuario) ON DELETE CASCADE,
    tipo TEXT NOT NULL,  -- 'FI_CONFIRMADA', 'FI_ANULADA', 'PP_LLEGADA', etc.
    titulo TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    entidad_tipo TEXT,  -- 'factura_interna', 'pedido_proveedor', etc.
    entidad_id BIGINT,
    leida BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices para rendimiento
CREATE INDEX IF NOT EXISTS idx_notif_usuario_leida ON public.notificaciones(usuario_id, leida);
CREATE INDEX IF NOT EXISTS idx_notif_created_at ON public.notificaciones(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notif_entidad ON public.notificaciones(entidad_tipo, entidad_id);

COMMENT ON TABLE public.notificaciones IS 'Sistema de mensajería interna - notificaciones para vendedores';
COMMENT ON COLUMN public.notificaciones.tipo IS 'Tipo de notificación para filtros y acciones';
COMMENT ON COLUMN public.notificaciones.entidad_tipo IS 'Tabla relacionada (factura_interna, pedido_proveedor)';
COMMENT ON COLUMN public.notificaciones.entidad_id IS 'ID del registro relacionado';

-- ────────────────────────────────────────────────────────────────────────────
-- FUNCIÓN: Notificar cuando FI es confirmada
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.notificar_fi_confirmada()
RETURNS TRIGGER AS $$
BEGIN
    -- Solo si cambió de RESERVADA a CONFIRMADA
    IF NEW.estado = 'CONFIRMADA' AND OLD.estado = 'RESERVADA' THEN
        INSERT INTO public.notificaciones (
            usuario_id,
            tipo,
            titulo,
            mensaje,
            entidad_tipo,
            entidad_id
        ) VALUES (
            NEW.vendedor_id,
            'FI_CONFIRMADA',
            'Factura Confirmada ✅',
            'Tu factura ' || NEW.nro_factura || ' ha sido confirmada por el administrador. Ya puedes ver y compartir el PDF.',
            'factura_interna',
            NEW.id
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.notificar_fi_confirmada() IS 'Crea notificación automática cuando FI cambia a CONFIRMADA';

-- ────────────────────────────────────────────────────────────────────────────
-- TRIGGER: Ejecutar notificación al confirmar FI
-- ────────────────────────────────────────────────────────────────────────────

DROP TRIGGER IF EXISTS trigger_notificar_fi_confirmada ON public.factura_interna;

CREATE TRIGGER trigger_notificar_fi_confirmada
    AFTER UPDATE OF estado ON public.factura_interna
    FOR EACH ROW
    EXECUTE FUNCTION public.notificar_fi_confirmada();

COMMENT ON TRIGGER trigger_notificar_fi_confirmada ON public.factura_interna IS
    'Trigger que crea notificación cuando FI pasa de RESERVADA a CONFIRMADA';

-- ────────────────────────────────────────────────────────────────────────────
-- FUNCIÓN: Notificar cuando FI es anulada
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.notificar_fi_anulada()
RETURNS TRIGGER AS $$
BEGIN
    -- Solo si cambió de RESERVADA a ANULADA
    IF NEW.estado = 'ANULADA' AND OLD.estado = 'RESERVADA' THEN
        INSERT INTO public.notificaciones (
            usuario_id,
            tipo,
            titulo,
            mensaje,
            entidad_tipo,
            entidad_id
        ) VALUES (
            NEW.vendedor_id,
            'FI_ANULADA',
            'Factura Anulada ❌',
            'Tu factura ' || NEW.nro_factura || ' fue rechazada. Motivo: ' || COALESCE(NEW.notas, 'Sin motivo especificado'),
            'factura_interna',
            NEW.id
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION public.notificar_fi_anulada() IS 'Crea notificación cuando FI es rechazada/anulada';

-- ────────────────────────────────────────────────────────────────────────────
-- TRIGGER: Ejecutar notificación al anular FI
-- ────────────────────────────────────────────────────────────────────────────

DROP TRIGGER IF EXISTS trigger_notificar_fi_anulada ON public.factura_interna;

CREATE TRIGGER trigger_notificar_fi_anulada
    AFTER UPDATE OF estado ON public.factura_interna
    FOR EACH ROW
    EXECUTE FUNCTION public.notificar_fi_anulada();

-- ────────────────────────────────────────────────────────────────────────────
-- GRANTS: Permisos para rimec-web
-- ────────────────────────────────────────────────────────────────────────────

-- RLS: Usuarios solo ven sus propias notificaciones
ALTER TABLE public.notificaciones ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS notificaciones_select_own ON public.notificaciones;
CREATE POLICY notificaciones_select_own ON public.notificaciones
    FOR SELECT
    USING (usuario_id = current_setting('app.current_user_id', TRUE)::BIGINT);

DROP POLICY IF EXISTS notificaciones_update_own ON public.notificaciones;
CREATE POLICY notificaciones_update_own ON public.notificaciones
    FOR UPDATE
    USING (usuario_id = current_setting('app.current_user_id', TRUE)::BIGINT)
    WITH CHECK (usuario_id = current_setting('app.current_user_id', TRUE)::BIGINT);

-- Grant para service_role (rimec-web)
GRANT SELECT, UPDATE ON public.notificaciones TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.notificaciones_id_seq TO service_role;

-- ────────────────────────────────────────────────────────────────────────────
-- VALIDACIÓN
-- ────────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
    RAISE NOTICE 'Migración 099 aplicada exitosamente';
    RAISE NOTICE '  - Tabla: notificaciones';
    RAISE NOTICE '  - Triggers: notificar_fi_confirmada, notificar_fi_anulada';
    RAISE NOTICE '  - RLS: Activo (usuarios solo ven sus notificaciones)';
END $$;
