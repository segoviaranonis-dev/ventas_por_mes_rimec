# ORDEN AL ALBAÑIL — MÓDULO DE ADMINISTRACIÓN DE DIGITACIONES
**De:** Maestro de Obras / Dirección
**Prioridad:** Alta. Este es el único módulo nuevo del flujo.
**Referencia obligatoria:** `docs\RIMEC_POLITICAS_BLINDADAS.md`

---

## CONTEXTO — QUÉ ES Y QUÉ NO ES ESTE MÓDULO

Este módulo es el puente entre la Intención de Compra y el Pedido Proveedor.
NO carga productos. NO hace cálculos financieros. NO muestra crédito.
Solo asigna identidad externa a las ICs autorizadas y las agrupa en Pedidos Proveedor.

El digitador es un operador logístico. Su pantalla debe ser simple y funcional.

---

## PASO 0 — VERIFICACIÓN PREVIA

Antes de escribir código, verificar en Supabase:

```sql
-- 1. Confirmar estados existentes en intencion_compra
SELECT DISTINCT estado FROM intencion_compra;

-- 2. Confirmar que precio_evento existe y tiene registros
SELECT id, nombre_evento, estado FROM precio_evento
WHERE estado = 'cerrado' ORDER BY created_at DESC LIMIT 5;

-- 3. Verificar si ya existe tabla puente
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name ILIKE '%intencion%pedido%';
```

Reportar resultados antes de continuar.

---

## PASO 1 — MIGRACIÓN SQL

### 1a. Nuevo estado en Intención de Compra

```sql
-- Agregar precio_evento_id a intencion_compra
ALTER TABLE intencion_compra
    ADD COLUMN IF NOT EXISTS precio_evento_id BIGINT
    REFERENCES precio_evento(id);

-- Verificar que estado 'AUTORIZADO' es válido en el sistema
-- Si hay un CHECK CONSTRAINT en estado, agregarlo:
-- ALTER TABLE intencion_compra DROP CONSTRAINT IF EXISTS check_estado;
-- ALTER TABLE intencion_compra ADD CONSTRAINT check_estado
--     CHECK (estado IN ('BORRADOR','AUTORIZADO','DIGITADO','VINCULADO_PP','CERRADO'));
```

### 1b. Tabla puente — el corazón del módulo

```sql
CREATE TABLE IF NOT EXISTS intencion_compra_pedido (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    intencion_compra_id     BIGINT NOT NULL REFERENCES intencion_compra(id),
    pedido_proveedor_id     BIGINT NOT NULL REFERENCES pedido_proveedor(id),
    nro_pedido_fabrica      TEXT NOT NULL,
    precio_evento_id        BIGINT REFERENCES precio_evento(id),
    asignado_por            BIGINT REFERENCES usuario_v2(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(intencion_compra_id)  -- una IC solo puede estar en un PP
);
```

### 1c. Campo factura en Pedido Proveedor

```sql
ALTER TABLE pedido_proveedor
    ADD COLUMN IF NOT EXISTS nro_factura_importacion TEXT,
    ADD COLUMN IF NOT EXISTS estado_digitacion TEXT
        DEFAULT 'ABIERTO'
        CHECK (estado_digitacion IN ('ABIERTO','CERRADO'));
```

---

## PASO 2 — UI: MÓDULO DE DIGITACIÓN

### Estructura del módulo

```
modules/digitacion/
├── __init__.py
├── bandeja.py        ← Vista principal: pendientes + en proceso
└── asignacion.py     ← Vista de trabajo: asignar IC a PP
```

### Vista principal — Bandeja de trabajo

**Sección superior: PENDIENTES** (lo más importante)

Tabla de ICs autorizadas sin `nro_pedido_fabrica` asignado:

```python
# ICs autorizadas sin asignación en tabla puente
pendientes = supabase.table('intencion_compra')\
    .select('id, nro_ic, marca, categoria_id, precio_evento_id, created_at')\
    .eq('estado', 'AUTORIZADO')\
    .is_('id', 'NOT IN (SELECT intencion_compra_id FROM intencion_compra_pedido)')\
    .execute()
```

Columnas visibles: `Nro IC · Marca · Categoría · Evento de Precio · Fecha · Acción`
Métrica destacada: **"X ICs pendientes de procesar"** — número grande, visible.

**Sección inferior: EN PROCESO**

Pedidos Proveedor en estado ABIERTO con cantidad de ICs asignadas:

```python
# PPs abiertos con conteo de ICs
pp_abiertos = supabase.table('pedido_proveedor')\
    .select('id, nro_pp, nro_factura_importacion, estado_digitacion, created_at')\
    .eq('estado_digitacion', 'ABIERTO')\
    .execute()
```

Columnas: `Nro PP · Factura · ICs asignadas · Fecha apertura · Acción`

### Vista de asignación — el trabajo del digitador

Al hacer clic en una IC pendiente, se abre esta vista.
El digitador ve solo lo necesario:

```
┌─────────────────────────────────────────────────┐
│  IC-2026-0001  │  VIZZANO  │  COMPRA PREVIA     │
├─────────────────────────────────────────────────┤
│  Evento de precio asignado: [selector dropdown] │
│  (muestra eventos cerrados — puede cambiar)     │
├─────────────────────────────────────────────────┤
│  Nro. Pedido Fábrica (Beira Rio): [___________] │
├─────────────────────────────────────────────────┤
│  Asignar a Pedido Proveedor:                    │
│  ○ PP existente: [selector de PPs ABIERTOS]     │
│  ○ Crear PP nuevo                               │
├─────────────────────────────────────────────────┤
│  [ Cancelar ]              [ Asignar → ]        │
└─────────────────────────────────────────────────┘
```

**Reglas de validación:**
- `nro_pedido_fabrica` obligatorio — no se puede asignar sin él
- `precio_evento_id` obligatorio — debe estar seleccionado
- Si crea PP nuevo: solo pide confirmación, el número se genera automáticamente

**Al confirmar:**
1. Inserta en `intencion_compra_pedido`
2. Actualiza `intencion_compra.estado` → `'DIGITADO'`
3. Si PP nuevo: crea registro en `pedido_proveedor` con `estado_digitacion = 'ABIERTO'`
4. Vuelve a la bandeja — la IC desaparece de pendientes

### Cierre de Pedido Proveedor

Desde la sección "EN PROCESO", el digitador puede cerrar un PP:
- Debe ingresar `nro_factura_importacion` antes de cerrar
- Al cerrar: `estado_digitacion → 'CERRADO'`
- El PP cerrado pasa automáticamente al módulo de Compra Legal
- No se pueden agregar más ICs a un PP cerrado

---

## PASO 3 — TRAZABILIDAD

El `precio_evento_id` seleccionado en digitación debe propagarse:

```python
# Al asignar IC a PP, guardar precio_evento_id en la tabla puente
# Ese ID determina en el PP:
#   · FOB de cada producto
#   · LPN / LPC03 / LPC04 (estrategia comercial)
#   · Márgenes de utilidad esperados
# Ver: docs\RIMEC_POLITICAS_BLINDADAS.md — LEY 4
```

---

## LO QUE EL DIGITADOR NO VE

- Límites de crédito del cliente
- Parte financiera de la IC
- Módulo de precios
- Módulo de compra legal

El digitador ve: qué IC tiene, qué número de fábrica le pone, y a qué PP la manda.

---

## CRITERIO DE ENTREGA

```
MÓDULO DE DIGITACIÓN COMPLETADO

□ Migración SQL ejecutada:
  · intencion_compra.precio_evento_id → creado
  · intencion_compra_pedido → tabla puente creada
  · pedido_proveedor.nro_factura_importacion → creado
  · pedido_proveedor.estado_digitacion → creado

□ UI — Bandeja:
  · Sección PENDIENTES → ICs autorizadas sin asignar
  · Métrica de pendientes visible y destacada
  · Sección EN PROCESO → PPs abiertos con conteo de ICs

□ UI — Asignación:
  · Selector de evento de precio funcionando
  · Campo nro_pedido_fabrica obligatorio
  · Opción PP existente / PP nuevo funcionando
  · Al asignar: IC desaparece de pendientes

□ Cierre de PP:
  · Requiere nro_factura_importacion
  · Al cerrar: pasa a Compra Legal

□ RIMEC_CONTEXTO.md → actualizado
```

El Director opera el módulo y valida. No avanzar sin confirmación.

---

## ORDEN DE PRIORIDAD RECORDATORIO

```
1. ✅ IC V2 con Tipo + Categoría — refinado
2. 🔄 Módulo de Digitación — ESTA ORDEN
3. ⏳ PP V2 — comportamiento por categoría (COMPRA PREVIA vs PROGRAMADO)
4. ⏳ Depósito — lógica saldo → Stock automático
5. ⏳ Sales Report — absorción completa (LO ÚLTIMO)
```

---

*Política blindada. No se discute. Se implementa.*
*Referencia: docs\RIMEC_POLITICAS_BLINDADAS.md*
