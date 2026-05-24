-- MIG-083 — Descuentos por Factura Interna (Marca × Caso)
-- Director: descuento es atributo del caso comercial, opera a nivel FI.
-- Heredabilidad por defecto + invalidación por edición.

BEGIN;

-- ────────────────────────────────────────────────────────────────────
-- 1. Estructura descuentos_lote en carrito_sesion
-- ────────────────────────────────────────────────────────────────────
-- Formato JSONB:
-- {
--   "facturas": [
--     {
--       "pp_id": 1,
--       "marca": "ACTVITTA",
--       "marca_id": 3,
--       "caso": "ACT-BRSPORT",
--       "caso_id": 3,
--       "lista_precio_id": 1,
--       "descuentos": [10, 5, 0, 0],
--       "pre_autorizado": true
--     }
--   ]
-- }
--
-- Reglas:
-- - Cada factura hereda descuentos globales inicialmente
-- - pre_autorizado = true por defecto
-- - Si usuario edita → pre_autorizado = false
-- - "Ver Totales" → recalcula y marca pre_autorizado = true
-- - "Confirmar" requiere TODAS pre_autorizado = true

COMMENT ON COLUMN public.carrito_sesion.descuentos_lote IS
  'MIG-083: descuentos por Factura Interna (Marca × Caso). Estructura: {facturas: [{pp_id, marca, caso, lista_precio_id, descuentos[4], pre_autorizado}]}';

-- ────────────────────────────────────────────────────────────────────
-- 2. Función auxiliar: inicializar descuentos_lote desde items
-- ────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.carrito_calcular_facturas(p_id_usuario bigint)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_descuentos_globales numeric[];
  v_lista_global smallint;
  v_facturas jsonb := '[]'::jsonb;
  v_factura record;
BEGIN
  -- Leer descuentos globales de sesión
  SELECT descuentos, lista_precio_id
  INTO v_descuentos_globales, v_lista_global
  FROM public.carrito_sesion
  WHERE id_usuario = p_id_usuario;

  -- Agrupar items por PP × Marca × Caso
  FOR v_factura IN
    SELECT
      ci.pp_id,
      ci.marca_snapshot AS marca,
      ci.marca_id_snapshot AS marca_id,
      ci.caso_snapshot AS caso,
      ci.caso_id_snapshot AS caso_id,
      COUNT(*) AS items_count
    FROM public.carrito_item ci
    WHERE ci.id_usuario = p_id_usuario
    GROUP BY ci.pp_id, ci.marca_snapshot, ci.marca_id_snapshot, ci.caso_snapshot, ci.caso_id_snapshot
    ORDER BY ci.pp_id, ci.marca_snapshot, ci.caso_snapshot
  LOOP
    v_facturas := v_facturas || jsonb_build_object(
      'pp_id', v_factura.pp_id,
      'marca', v_factura.marca,
      'marca_id', v_factura.marca_id,
      'caso', v_factura.caso,
      'caso_id', v_factura.caso_id,
      'lista_precio_id', v_lista_global,
      'descuentos', v_descuentos_globales,
      'pre_autorizado', true,
      'items_count', v_factura.items_count
    );
  END LOOP;

  RETURN jsonb_build_object('facturas', v_facturas);
END;
$$;

COMMENT ON FUNCTION public.carrito_calcular_facturas IS
  'MIG-083: calcula división de Facturas Internas (Marca × Caso) con descuentos heredados de sesión.';

-- ────────────────────────────────────────────────────────────────────
-- 3. Trigger: recalcular descuentos_lote al agregar/eliminar items
-- ────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.fn_carrito_sync_facturas()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_id_usuario bigint;
BEGIN
  v_id_usuario := COALESCE(NEW.id_usuario, OLD.id_usuario);

  -- Recalcular división de facturas
  UPDATE public.carrito_sesion
  SET descuentos_lote = public.carrito_calcular_facturas(v_id_usuario),
      actualizada_en = now(),
      validada_en = NULL,
      validacion_token = NULL,
      validacion_estado = NULL
  WHERE id_usuario = v_id_usuario;

  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_carrito_sync_facturas ON public.carrito_item;
CREATE TRIGGER trg_carrito_sync_facturas
AFTER INSERT OR DELETE ON public.carrito_item
FOR EACH ROW EXECUTE FUNCTION public.fn_carrito_sync_facturas();

COMMENT ON FUNCTION public.fn_carrito_sync_facturas IS
  'MIG-083: sincroniza descuentos_lote cuando cambian items del carrito.';

COMMIT;

SELECT 'MIG-083 OK: descuentos por Factura Interna (Marca × Caso)' AS estado;
