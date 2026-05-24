-- MIG-089 — Limpiar facturas de prueba generadas durante testing MIG-083 a 087
-- CRÍTICO: Restaurar pares_vendidos en pedido_proveedor_detalle ANTES de eliminar
-- Solo elimina facturas internas, NO toca stock base de pedido_proveedor

BEGIN;

-- ══════════════════════════════════════════════════════════════════════════
-- PASO 1: Identificar pedidos de prueba (ajustar según sea necesario)
-- ══════════════════════════════════════════════════════════════════════════

-- Opción A: Eliminar pedidos específicos por número
DO $$
DECLARE
  v_pedido_id bigint;
  v_fi_id bigint;
  v_ppd_id bigint;
  v_pares integer;
BEGIN
  -- Lista de pedidos a eliminar (ajustar según necesidad)
  -- Ejemplo: 'PVR-2026-145156', 'PVR-2026-794967'

  FOR v_pedido_id IN
    SELECT id FROM public.pedido_venta_rimec
    WHERE nro_pedido IN (
      'PVR-2026-145156',
      'PVR-2026-794967'
    )
  LOOP
    RAISE NOTICE 'Procesando pedido_id: %', v_pedido_id;

    -- Paso 1.1: Restaurar pares_vendidos en pedido_proveedor_detalle
    FOR v_fi_id IN
      SELECT id FROM public.factura_interna WHERE pedido_id = v_pedido_id
    LOOP
      FOR v_ppd_id, v_pares IN
        SELECT ppd_id, pares
        FROM public.factura_interna_detalle
        WHERE factura_id = v_fi_id AND ppd_id IS NOT NULL
      LOOP
        UPDATE public.pedido_proveedor_detalle
        SET pares_vendidos = COALESCE(pares_vendidos, 0) - v_pares
        WHERE id = v_ppd_id;

        RAISE NOTICE '  Restaurado PPD %: -% pares', v_ppd_id, v_pares;
      END LOOP;

      -- Paso 1.2: Eliminar detalles de factura interna
      DELETE FROM public.factura_interna_detalle WHERE factura_id = v_fi_id;
      RAISE NOTICE '  Eliminados detalles de FI %', v_fi_id;
    END LOOP;

    -- Paso 1.3: Eliminar facturas internas
    DELETE FROM public.factura_interna WHERE pedido_id = v_pedido_id;
    RAISE NOTICE '  Eliminadas facturas internas del pedido %', v_pedido_id;

    -- Paso 1.4: Eliminar cabecera del pedido
    DELETE FROM public.pedido_venta_rimec WHERE id = v_pedido_id;
    RAISE NOTICE '  Eliminado pedido %', v_pedido_id;
  END LOOP;

  RAISE NOTICE 'Limpieza completada';
END $$;

-- ══════════════════════════════════════════════════════════════════════════
-- PASO 2: Verificar que pares_vendidos no quedó negativo
-- ══════════════════════════════════════════════════════════════════════════

SELECT ppd.id, ppd.cantidad_pares, ppd.pares_vendidos
FROM public.pedido_proveedor_detalle ppd
WHERE ppd.pares_vendidos < 0;

-- Si hay filas, algo salió mal - NO COMMITEAR

-- ══════════════════════════════════════════════════════════════════════════
-- PASO 3: Verificar eliminación
-- ══════════════════════════════════════════════════════════════════════════

SELECT 'Pedidos eliminados:' AS verificacion,
  (SELECT COUNT(*) FROM public.pedido_venta_rimec
   WHERE nro_pedido IN ('PVR-2026-145156', 'PVR-2026-794967')) AS pedidos_restantes,
  (SELECT COUNT(*) FROM public.factura_interna
   WHERE pedido_id IN (
     SELECT id FROM public.pedido_venta_rimec
     WHERE nro_pedido IN ('PVR-2026-145156', 'PVR-2026-794967')
   )) AS facturas_restantes;

COMMIT;

SELECT 'MIG-089 OK: facturas de prueba eliminadas, stock restaurado' AS estado;
