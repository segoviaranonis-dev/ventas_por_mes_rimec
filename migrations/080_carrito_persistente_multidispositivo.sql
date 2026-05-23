-- MIG-080 — Carrito persistente multidispositivo (server-side).
-- Reemplaza localStorage. Una sesión de venta por usuario. Items vinculados.
-- Sin reserva de stock: la verdad se define en CONFIRMAR con FOR UPDATE.

BEGIN;

-- ──────────────────────────────────────────────────────────────────────
-- Cabecera: una fila por usuario activo.
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.carrito_sesion (
  id_usuario       bigint PRIMARY KEY REFERENCES public.usuario_v2(id_usuario) ON DELETE CASCADE,
  cliente_id       bigint NOT NULL REFERENCES public.cliente_v2(id_cliente),
  cliente_nombre   text   NOT NULL,
  plazo_id         bigint NULL,
  plazo_nombre     text   NULL,
  lista_precio_id  smallint NOT NULL DEFAULT 1 CHECK (lista_precio_id IN (1,2,3,4)),
  descuentos       numeric[] NOT NULL DEFAULT ARRAY[0,0,0,0]::numeric[],
  descuentos_lote  jsonb   NOT NULL DEFAULT '{}'::jsonb,
  iniciada_en      timestamptz NOT NULL DEFAULT now(),
  actualizada_en   timestamptz NOT NULL DEFAULT now(),
  validada_en      timestamptz NULL,
  validacion_token uuid NULL,
  validacion_estado text NULL CHECK (validacion_estado IN ('OK','DIFERENCIAS','BLOQUEADO'))
);

COMMENT ON TABLE public.carrito_sesion IS
  'MIG-080: sesión de venta activa por vendedor. Un cliente a la vez (contrato Héctor).';

CREATE INDEX IF NOT EXISTS idx_carrito_sesion_cliente
  ON public.carrito_sesion (cliente_id);

-- ──────────────────────────────────────────────────────────────────────
-- Items: PK compuesta (id_usuario, det_id).
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.carrito_item (
  id_usuario        bigint NOT NULL REFERENCES public.carrito_sesion(id_usuario) ON DELETE CASCADE,
  det_id            bigint NOT NULL REFERENCES public.pedido_proveedor_detalle(id),
  pp_id             bigint NOT NULL,
  cantidad_cajas    integer NOT NULL CHECK (cantidad_cajas > 0),
  precio_snapshot   numeric NOT NULL,
  caso_snapshot     text    NOT NULL,
  caso_id_snapshot  bigint  NULL,
  marca_snapshot    text    NOT NULL,
  marca_id_snapshot bigint  NULL,
  agregado_en       timestamptz NOT NULL DEFAULT now(),
  actualizado_en    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id_usuario, det_id)
);

COMMENT ON TABLE public.carrito_item IS
  'MIG-080: ítems del carrito activo. precio_snapshot congelado al agregar (referencia al snapshot PPD).';

CREATE INDEX IF NOT EXISTS idx_carrito_item_det
  ON public.carrito_item (det_id);

-- ──────────────────────────────────────────────────────────────────────
-- Trigger actualizada_en en sesión cuando cambia item.
-- ──────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.fn_carrito_touch_sesion()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE public.carrito_sesion
  SET actualizada_en = now(),
      validada_en = NULL,
      validacion_token = NULL,
      validacion_estado = NULL
  WHERE id_usuario = COALESCE(NEW.id_usuario, OLD.id_usuario);
  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_carrito_item_touch ON public.carrito_item;
CREATE TRIGGER trg_carrito_item_touch
AFTER INSERT OR UPDATE OR DELETE ON public.carrito_item
FOR EACH ROW EXECUTE FUNCTION public.fn_carrito_touch_sesion();

-- ──────────────────────────────────────────────────────────────────────
-- Permisos: solo service_role. RLS bloquea acceso desde anon/authenticated.
-- ──────────────────────────────────────────────────────────────────────
ALTER TABLE public.carrito_sesion ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.carrito_item   ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS carrito_sesion_service_only ON public.carrito_sesion;
CREATE POLICY carrito_sesion_service_only ON public.carrito_sesion
  FOR ALL USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS carrito_item_service_only ON public.carrito_item;
CREATE POLICY carrito_item_service_only ON public.carrito_item
  FOR ALL USING (false) WITH CHECK (false);

GRANT ALL ON public.carrito_sesion TO service_role;
GRANT ALL ON public.carrito_item   TO service_role;

-- ──────────────────────────────────────────────────────────────────────
-- Realtime: publicar tablas para suscripción multidispositivo.
-- ──────────────────────────────────────────────────────────────────────
DO $$
BEGIN
  PERFORM 1
  FROM pg_publication_tables
  WHERE pubname = 'supabase_realtime'
    AND schemaname = 'public'
    AND tablename = 'carrito_sesion';
  IF NOT FOUND THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.carrito_sesion';
  END IF;

  PERFORM 1
  FROM pg_publication_tables
  WHERE pubname = 'supabase_realtime'
    AND schemaname = 'public'
    AND tablename = 'carrito_item';
  IF NOT FOUND THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.carrito_item';
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'Realtime publication no disponible o ya configurada: %', SQLERRM;
END $$;

COMMIT;

SELECT 'MIG-080 OK: carrito_sesion + carrito_item + RLS + Realtime' AS estado;
