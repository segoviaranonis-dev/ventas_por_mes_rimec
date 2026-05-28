# DIAGNÓSTICO: Problema de Descuentos en FIs

## Fecha: 2026-05-28
## Reportado por: Usuario (vendedor + admin)

## SÍNTOMAS

1. **Vendedor** configura descuentos específicos por factura (PP×Marca×Caso):
   - Ej: FI 1 → 10%, 30%, 0%, 0%
   - Ej: FI 2 → 0%, 30%, 0%, 0%

2. **Sistema** muestra estos descuentos correctamente en rimec-web ANTES de confirmar

3. **Al confirmar**, los descuentos NO se guardan correctamente en las FIs

4. **Admin** ve en control_central "Sin descuento" en lugar de los descuentos configurados

5. **PDF** no muestra los descuentos aplicados correctamente

## CAUSA RAÍZ

### Flujo Actual (INCORRECTO):

```
rimec-web (vendedor)
  ↓
  Configura descuentos por factura en carrito_sesion.descuentos_lote
  {
    facturas: [
      { pp_id: 1, marca: "BR SPORT", caso: "ACT", descuentos: [10, 30, 0, 0] },
      { pp_id: 2, marca: "GONPAL", caso: "ACT", descuentos: [0, 30, 0, 0] }
    ]
  }
  ↓
  Al confirmar, llama confirmar_pedido_web() con:
  - p_descuento_1: 10  (GLOBAL para TODO el pedido)
  - p_descuento_2: 30  (GLOBAL para TODO el pedido)
  - p_payload: { lotes: [...items con precios YA calculados...] }
  ↓
confirmar_pedido_web (PostgreSQL)
  ↓
  Crea MÚLTIPLES facturas_interna (una por PP×Marca×Caso)
  PERO usa los mismos descuentos globales para TODAS:
  
  INSERT INTO factura_interna (descuento_1, descuento_2, ...)
  VALUES (p_descuento_1, p_descuento_2, ...)  <-- GLOBAL
  ↓
RESULTADO: Todas las FIs tienen los mismos descuentos
```

### El Problema:

1. **rimec-web** calcula precios correctos usando descuentos específicos por factura
2. **PERO** al confirmar, solo envía descuentos GLOBALES
3. **confirmar_pedido_web** crea FIs con descuentos globales (ignora los específicos)
4. **Los precios quedan correctos** (porque se calcularon antes con descuentos correctos)
5. **Pero los campos descuento_1..4 quedan incorrectos** en las FIs

## SOLUCIÓN

### Opción 1: Pasar descuentos específicos en payload ✅ ELEGIDA

1. Modificar payload de rimec-web para incluir descuentos por factura:
   ```typescript
   facturas: [{
     marca: "BR SPORT",
     caso: "ACT",
     descuentos: [10, 30, 0, 0],  // <-- AGREGAR ESTO
     items: [...]
   }]
   ```

2. Modificar confirmar_pedido_web() para usar descuentos específicos:
   ```sql
   -- En lugar de usar p_descuento_1..4 global
   -- Extraer descuentos de cada factura del payload:
   v_desc1 := COALESCE((v_factura_data->>'descuento_1')::NUMERIC, 0)
   ```

### Opción 2: Editar FIs después de crearlas (PARCHE)

- Leer descuentos_lote del pedido
- Actualizar cada FI con sus descuentos correctos
- PROBLEMA: Requiere replicar lógica, más frágil

### Opción 3: No guardar descuentos en FIs (NO VIABLE)

- Solo guardar precios netos
- PROBLEMA: Admin necesita VER los descuentos, no solo los precios

## TAREA ADICIONAL: Permitir Editar FIs CONFIRMADAS

El admin necesita poder:
1. "Reabrir" una FI CONFIRMADA para editarla
2. Cambiar descuentos
3. Recalcular precios
4. Volver a confirmar

**Implementación:**
- Botón "Editar descuentos" en FI CONFIRMADA
- Cambiar estado temporalmente a RESERVADA
- Aplicar nueva función actualizar_fi_encabezado()
- Volver a CONFIRMADA

## ARCHIVOS INVOLUCRADOS

1. `rimec-web/app/carrito/page.tsx` - Agregar descuentos a payload
2. `migrations/010_rpc_confirmar_pedido_web.sql` - Modificar función SQL
3. `control_central/modules/aprobacion_pedidos/logic.py` - Agregar función de edición
4. `control_central/modules/aprobacion_pedidos/ui.py` - Agregar UI de edición
5. `rimec-web/lib/pdfGenerator.ts` - Verificar que use descuentos correctos
