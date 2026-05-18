# Trazabilidad PP → Listado RIMEC (precio_evento)

**OT:** OT-COMPRA-501-002  
**Fecha:** 2026-05-17

---

## Arquitectura

```
pedido_proveedor (PP)
       ↑
       | (vía intencion_compra_pedido)
       |
intencion_compra (IC) ←── precio_evento_id
       ↑                      ↓
       |                  precio_evento
       |                      ↓
       |                  precio_lista
```

### Tablas involucradas

1. **pedido_proveedor**: Pedido a proveedor (proforma importada)
   - `id`: PK
   - **NO tiene** `precio_evento_id` (no está en schema)

2. **intencion_compra_pedido**: Tabla puente IC → PP
   - `intencion_compra_id`: FK a intencion_compra (UNIQUE - una IC solo puede estar en un PP)
   - `pedido_proveedor_id`: FK a pedido_proveedor
   - **`precio_evento_id`**: FK a precio_evento (puede ser NULL)
   - `nro_pedido_fabrica`: número Beira Rio (obligatorio)

3. **precio_evento**: Listado de precios RIMEC
   - `id`: PK
   - `nombre_evento`: ej. "PRIMAVERA-VERANO 2026"
   - `estado`: ABIERTO, CERRADO, DISTRIBUIDO
   - `proveedor_id`: FK

4. **precio_lista**: Detalle del listado
   - `evento_id`: FK a precio_evento
   - `linea_codigo`, `referencia_codigo`: códigos proveedor
   - `lpn`, `lpc02`, `lpc03`, `lpc04`: precios por caso

---

## Query: PP → precio_evento_id

```sql
SELECT
    pp.id AS pp_id,
    pp.numero_registro AS pp_nro,
    pp.numero_proforma,
    icp.precio_evento_id,
    pe.nombre_evento,
    pe.estado AS evento_estado
FROM pedido_proveedor pp
LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
LEFT JOIN precio_evento pe ON pe.id = icp.precio_evento_id
WHERE pp.id = :pp_id;
```

**Casos:**
- `precio_evento_id` IS NULL → PP sin listado vinculado
- `precio_evento_id` NOT NULL → PP vinculado a listado

---

## Impacto en Facturación Interna

Cuando un PP tiene `precio_evento_id`:
1. `factura_interna_detalle.lpn/lpc02/lpc03/lpc04` se calculan desde `precio_lista`
2. Si se cambia el listado vinculado, las FI en estado RESERVADA deben recalcularse
3. FI CONFIRMADA = histórica, no se recalcula

**Función:** `recalcular_facturas_internas_pp(pp_id, nuevo_evento_id)`
- Actualiza `intencion_compra_pedido.precio_evento_id`
- Re-calcula FI RESERVADA para ese PP
- No toca FI CONFIRMADA

---

## UI: Panel Listado RIMEC

**Ubicación:** modules/pedido_proveedor/ui.py (detalle PP)

**Mostrar:**
- Listado actual vinculado (nombre_evento, estado)
- Botón "Vincular listado" si NULL
- Botón "Cambiar listado" si ya vinculado
- **⚠️ Aviso crítico:** "Este PP se enviará a Compra Legal sin listado RIMEC. Las FI no tendrán precios de casos comerciales."

**Regla:**
- Compra Legal puede aceptar PP sin listado (cajas/pares OK)
- Pero Facturación no puede calcular precio_evento sin listado
- Usuario debe ser advertido ANTES de create_compra_legal

---

## Smoke Test: Vincular evento → recalcular FI

**Caso:** PP-2026-0001 (7164 pares, 748 cajas)

1. **Estado inicial:**
   - PP sin precio_evento_id (NULL)
   - Compra CL-2026-0001 creada (44 pares facturados en FI RESERVADA)

2. **Acción:**
   - Vincular evento de prueba a PP-2026-0001
   - `UPDATE intencion_compra_pedido SET precio_evento_id = :evento_id WHERE pedido_proveedor_id = 1`

3. **Recalcular FI:**
   - `recalcular_facturas_internas_pp(1)` debe actualizar lpn/lpc en FI RESERVADA
   - FI CONFIRMADA no se toca (histórica)

4. **Validar:**
   - Totales compra: 7164 pares, 748 cajas (sin cambio)
   - Facturados: 44 pares (sin cambio en cantidad, solo precios)
   - FI RESERVADA: lpn/lpc actualizados desde precio_lista

---

## Validación create_compra_legal

**Entrada:**
- PP-2026-0001: 273 moléculas, 7164 pares, 748 cajas

**Después de create_compra_legal(proforma='7441-4084'):**
- CL-2026-0001 creada
- compra_legal_pedido vincula CL ↔ PP
- **Totales NO cambian:**
  - `SUM(ppd.cantidad_pares) = 7164` (intacto)
  - `SUM(ppd.cantidad_cajas) = 748` (intacto)
- **Facturados desde FI:**
  - pares_facturados = 44 (5 FI CONFIRMADA/RESERVADA)
  - No se crean nuevas FI automáticamente
  - FI existen porque usuario las creó manualmente

**Invariante:**
```sql
-- Antes y después de create_compra_legal:
SELECT
    SUM(cantidad_pares) AS pares,
    SUM(cantidad_cajas) AS cajas
FROM pedido_proveedor_detalle
WHERE pedido_proveedor_id = 1;
-- Resultado: 7164 pares, 748 cajas (sin cambio)
```

---

**Archivo:** `docs/TRAZABILIDAD_PP_LISTADO.md`  
**Status:** Documentación completa Task 1
