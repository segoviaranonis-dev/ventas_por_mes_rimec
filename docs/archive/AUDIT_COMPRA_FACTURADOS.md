# AUDIT: Compra Legal Facturados Metrics

**Fecha:** 2026-05-17  
**OT:** OT-FI-COMPRA-503-001  
**Objetivo:** Diagnosticar desvíos entre header, PP rows, y acordeón FAC-INT

---

## I1: Audit Script Execution (Proforma 7441-4084 / CL-2026-0001)

### Resultados

| Métrica | Valor | Fuente |
|---------|-------|--------|
| Header "Facturados" | 44 | get_compra_header (VT + FI) |
| PP row "vendido" | 0 | get_pps_de_compra (VT only) |
| FAC-INT expander | 44 | get_compra_hija_facturacion (UNION ALL) |

### Desglose

**Header metrics:**
- VT sum: 0
- FI sum: 44 (5 facturas, estados CONFIRMADA/RESERVADA)
- Total: 0 + 44 = 44

**PP rows (PP-2026-0001):**
- total_pares: 7164
- VT_only: 0
- FI (ignored): 44
- **PP vendido actual:** 0 ← Solo lee VT

**FAC-INT expander:**
- FI rows: 5, pares: 44
- VT rows: 0
- UNION ALL total: 44

**Overlap check:**
- Facturas con VT+FI overlap: 0
- No hay doble conteo en este caso (sin VT data)

---

## I2: Root Cause Analysis

### Query Definitions

#### 1. Header `pares_facturados` (get_compra_header, lines 685-704)

```sql
COALESCE(
    (SELECT SUM(vt.cantidad_vendida)
     FROM venta_transito vt
     WHERE vt.pedido_proveedor_id IN (
         SELECT pedido_proveedor_id FROM compra_legal_pedido
         WHERE compra_legal_id = cl.id
     )),
    0
) +
COALESCE(
    (SELECT SUM(fid.pares)
     FROM factura_interna fi
     JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
     WHERE fi.pp_id IN (
         SELECT pedido_proveedor_id FROM compra_legal_pedido
         WHERE compra_legal_id = cl.id
     )
     AND fi.estado IN ('CONFIRMADA', 'RESERVADA')),
    0
) AS pares_facturados
```

**Lógica:** VT sum + FI sum (CONFIRMADA/RESERVADA)

#### 2. PP row `total_vendido` (get_pps_de_compra, lines 606-611)

```sql
COALESCE(
    (SELECT SUM(vt.cantidad_vendida)
     FROM venta_transito vt
     WHERE vt.pedido_proveedor_id = pp.id),
    0
) AS total_vendido
```

**Lógica:** SOLO VT sum (ignora FI)

#### 3. FAC-INT expander (get_compra_hija_facturacion, lines 765-842)

```sql
-- FI (new RIMEC)
SELECT ...
    SUM(fid.pares) AS pares
FROM factura_interna fi
JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
WHERE fi.pp_id IN (...)
  AND fi.estado IN ('CONFIRMADA', 'RESERVADA')
GROUP BY fi.marca, fi.nro_factura, fi.created_at, ...

UNION ALL

-- VT (legacy)
SELECT ...
    SUM(vt.cantidad_vendida) AS pares
FROM venta_transito vt
WHERE vt.pedido_proveedor_id IN (...)
GROUP BY vt.numero_factura_interna, vt.codigo_cliente, ...
```

**Lógica:** UNION ALL de FI rows + VT rows (GROUP BY diferentes)

---

## I3: Diagnosis - Why 44 vs 0 vs ¿152?

### Case: Proforma 7441-4084, PP-2026-0001

**Scenario:** Solo FI, sin VT (legacy vacio)

1. **Header = 44:**
   - VT: 0
   - FI: 44 (5 facturas CONFIRMADA/RESERVADA)
   - Total: 0 + 44 = 44 ✓

2. **PP row = 0:**
   - Query solo lee VT → 0
   - FI = 44 **IGNORADO**
   - **H-A CONFIRMADO:** get_pps_de_compra ignora factura_interna

3. **Expander = 44 (audit) vs 152 (usuario):**
   - Audit script: FI sum = 44
   - Usuario reportó: 152
   - **DISCREPANCIA:** Posibles causas:
     - Usuario sumó todas las tallas individualmente (t33-t40)?
     - Usuario vio datos de otra compra?
     - Bug en acordeón UI que muestra filas expandidas incorrectas?
     - **REQUIERE VERIFICACIÓN MANUAL EN NEXUS UI**

### Diagrama flujo

```
┌─────────────────────────────────────────────────────────────┐
│ compra_legal                                                 │
│   └─> compra_legal_pedido                                   │
│         └─> pedido_proveedor (PP-2026-0001)                 │
│               ├─> venta_transito (VT) → 0 pares             │
│               └─> factura_interna (FI) → 44 pares (5 FI)    │
└─────────────────────────────────────────────────────────────┘

HEADER:     VT (0) + FI (44) = 44  ✓
PP ROW:     VT (0) = 0             ✗ (ignora FI)
EXPANDER:   FI (44) + VT (0) = 44  ✓ (pero UI muestra 152?)
```

---

## Hypotheses Verification

### H-A: get_pps_de_compra ignora factura_interna → PP muestra 0

**Status:** ✓ CONFIRMADO

**Evidence:**
- PP row query (logic.py:606-611) solo lee `venta_transito`
- FI data (44 pares) existe pero no se cuenta
- Diferencia header (44) vs PP sum (0) = 44 = FI ignorado

**Fix required:** M2/M3 - PP row debe incluir FI en métrica

### H-B: Header mezcla VT+FI con reglas distintas al acordeón

**Status:** ⚠️ PARCIAL

**Evidence:**
- Header: suma simple VT + FI
- Expander: UNION ALL con GROUP BY diferentes
- En caso 7441-4084: header (44) = expander (44) según audit script
- **Pero usuario reporta expander = 152 (inconsistente)**

**Requiere:** Verificación manual en Nexus UI para entender de dónde sale 152

### H-C: Header subcuenta o filtra estados distinto al expander

**Status:** ✗ NO CONFIRMADO

**Evidence:**
- Ambos usan mismo filtro: `estado IN ('CONFIRMADA', 'RESERVADA')`
- En caso 7441-4084: no hay subcuenta (header = expander = 44 según audit)

---

## Next Steps (Phase 2)

1. **M1:** Crear `get_metricas_facturacion_compra(id_cl)` en logic.py
   - Única fuente de verdad para: pares_facturados, pares_f9, pares_deposito
   - Por PP: {pp_id, pares_facturados_vt, pares_facturados_fi, total}

2. **M2:** Definir regla de negocio para pares_facturados:
   - `Σ fid.pares (FI RESERVADA/CONFIRMADA) + Σ vt.cantidad_vendida (líneas sin FI equivalente)`
   - Evitar doble conteo si misma factura está en VT y FI

3. **M3:** Refactorizar consumers:
   - `get_compra_header` → usa M1
   - `get_pps_de_compra` → usa M1 por PP
   - Acordeón FAC-INT subtítulo → usa M1

4. **M4:** Test script para verificar alineación

5. **Resolver discrepancia 44 vs 152:**
   - Revisar UI Nexus manualmente para caso 7441-4084
   - Si 152 es correcto, revisar audit script
   - Si 44 es correcto, reportar bug UI

---

**Archivo:** `docs/AUDIT_COMPRA_FACTURADOS.md`  
**Status:** I1-I2-I3 completado, requiere verificación manual 152 vs 44  
**Script:** `scripts/auditar_compra_facturados.py`  
**JSON:** `scripts/audit_compra_1_7441-4084.json`
