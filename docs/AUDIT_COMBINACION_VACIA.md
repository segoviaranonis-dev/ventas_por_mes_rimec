# Audit: Combinacion Vacía — traspaso_detalle sin pares

> Histórico OT-COMBINACION-505-001. Estado actual: **CERRADA** — ver `docs/OT_REGISTRO_ESTADO.md`

**OT:** OT-COMBINACION-505-001 Fase 1  
**Fecha:** 2026-05-17  
**Traspaso:** T-2026-0001 (id=2, estado BORRADOR)  
**Compra:** CL-2026-0001 (DISTRIBUIDA)

---

## Resumen Ejecutivo

**Problema:** Traspaso T-2026-0001 creado sin filas en `traspaso_detalle` (0 rows, 0 pares).  
**Impacto:** Facturación → Bazar no puede mover stock. Ciclo bloqueado.

**Root Cause (doble):**
1. **Tabla `combinacion` VACIA** (0 rows total) → `_resolve_combinacion_id()` siempre NULL → INSERT traspaso_detalle se skippea
2. **Referencias faltantes:** linea_referencia no tiene rows para `codigo_proveedor` 500, 565 (linea_id=459)

---

## Inventario Traspaso T-2026-0001

### Header
- **Numero:** T-2026-0001 (id=2)
- **Estado:** BORRADOR
- **Documento:** 1-PV001 (Factura Interna)
- **Snapshot items:** 4
- **traspaso_detalle rows:** 0
- **traspaso_detalle pares:** 0

### Snapshot Items

| Idx | SKU | Tallas | linea_id | ref_id | Issue |
|-----|-----|--------|----------|--------|-------|
| 0 | 4202-500-39-53 | t35-t40 (6 tallas) | 459 ✓ | **NOT FOUND** | referencia codigo=500 missing |
| 1 | 4202-500-37-51 | t37-t40 (4 tallas) | 459 ✓ | **NOT FOUND** | referencia codigo=500 missing |
| 2 | 4202-500-37-50 | t37-t40 (4 tallas) | 459 ✓ | **NOT FOUND** | referencia codigo=500 missing |
| 3 | 4202-565-49526-75 | t36-t40 (5 tallas) | 459 ✓ | **NOT FOUND** | referencia codigo=565 missing |

**Total tallas expansion:** ~19 tallas (6+4+4+5)  
**Pares esperados:** ~20-44 pares (según snapshot qty)

---

## Diagnóstico Detallado

### Issue 1: Tabla `combinacion` Vacía

```sql
SELECT COUNT(*) FROM combinacion;
-- Result: 0
```

**Consecuencia:**  
Aunque `linea`, `material`, `color` existan, sin rows en `combinacion` la resolución siempre falla:

```python
# _resolve_combinacion_id(cur, "4202", "500", "39", "53", "37")
# → Busca combinacion WHERE linea_id=459, ref_id=?, mat_id=39, col_id=53, talla_id=?
# → 0 rows → retorna NULL
```

**Por qué está vacía:**  
Tabla `combinacion` no se pobló durante migraciones iniciales. Debería haberse backfilled desde `pedido_proveedor_detalle.grades_json` al crear las entidades base.

---

### Issue 2: Referencias Faltantes

**Resultado audit:**
- `linea` 4202 → **OK** (linea_id=459, proveedor_id=654)
- `referencia` 500 (linea_id=459) → **NOT FOUND**
- `referencia` 565 (linea_id=459) → **NOT FOUND**

**Query diagnóstico:**
```sql
SELECT lr.id, lr.codigo_proveedor
FROM linea_referencia lr
WHERE lr.linea_id = 459
  AND lr.codigo_proveedor::text IN ('500', '565');
-- Result: 0 rows
```

**Por qué faltan:**  
Las referencias no fueron creadas durante la importación del PP. Posibles causas:
1. `pedido_proveedor_detalle` solo tiene `referencia` (código string), no FK `linea_referencia_id`
2. El proceso de importación no crea automáticamente entradas en `linea_referencia`
3. Las referencias son implícitas desde la proforma (no existen como entidades base)

---

## Estrategia de Resolución

### Opción R1: Backfill combinacion desde PPD (RECOMENDADO)

**Fuente:** `pedido_proveedor_detalle` (PP-2026-0001, 273 moléculas)

**Algoritmo:**
1. Para cada row en `ppd` WHERE `pedido_proveedor_id = 1`:
   - Parsear `grades_json` → {talla: qty}
   - Verificar/crear `linea` (codigo_proveedor)
   - Verificar/crear `linea_referencia` (codigo_proveedor, linea_id)
   - Verificar/crear `material` (id, codigo_proveedor, proveedor_id)
   - Verificar/crear `color` (id, codigo_proveedor, proveedor_id)
   - Para cada talla en grades_json:
     - Verificar/crear `talla` (numero)
     - INSERT combinacion (linea_id, ref_id, mat_id, col_id, talla_id, proveedor_id) ON CONFLICT DO NOTHING

**Ventajas:**
- Cubre todas las 273 moléculas del PP
- Genera combinaciones reales desde datos de proforma
- Idempotente (ON CONFLICT DO NOTHING)

**Script:** `scripts/backfill_combinacion_desde_ppd.py --pp-id 1 --yes`

---

### Opción R2: Crear entidades mínimas en crear_traspaso_por_factura

**Modificar:** `modules/compra_legal/logic.py:crear_traspaso_por_factura`

```python
# Si comb_id es NULL pero hay snapshot item válido:
if comb_id is None:
    # OT-2026-023 style: crear entidades mínimas + combinacion
    linea_id = _get_or_create_linea(conn, rec["linea"], proveedor_id)
    ref_id = _get_or_create_referencia(conn, rec["referencia"], linea_id)
    mat_id = rec.get("id_material") or _get_or_create_material(...)
    col_id = rec.get("id_color") or _get_or_create_color(...)
    talla_id = _get_or_create_talla(conn, t)
    
    comb_id = _insert_combinacion(conn, proveedor_id, linea_id, ref_id, mat_id, col_id, talla_id)
```

**Ventajas:**
- Self-healing: crea combinaciones on-the-fly
- No requiere backfill previo

**Desventajas:**
- Solo crea combinaciones para items facturados (subset del PP)
- Lógica más compleja en crear_traspaso
- No resuelve backfill global

---

### Opción R3: Rehidratar traspaso_detalle desde snapshot

**Script:** `scripts/rehidratar_traspaso_detalle.py --traspaso-id 2 --yes`

**Pre-requisito:** R1 o R2 ya ejecutado (combinacion poblada)

**Algoritmo:**
1. Leer `traspaso.snapshot_json`
2. Para cada item + talla:
   - Resolver `combinacion_id` (ahora debería funcionar)
   - INSERT traspaso_detalle (traspaso_id, comb_id, qty) ON CONFLICT DO UPDATE

**Post-validación:**
```sql
SELECT COUNT(*), SUM(cantidad)
FROM traspaso_detalle
WHERE traspaso_id = 2;
-- Esperado: ~19 rows, ~20-44 pares
```

---

## Plan de Acción (Fase 2)

### Paso 1: Backfill combinacion (R1)
```bash
python scripts/backfill_combinacion_desde_ppd.py --pp-id 1 --dry-run
python scripts/backfill_combinacion_desde_ppd.py --pp-id 1 --yes
```

**Validar:**
- `SELECT COUNT(*) FROM combinacion WHERE proveedor_id = 654` > 0
- Referencias 500, 565 creadas en `linea_referencia`

### Paso 2: Rehidratar traspaso (R3)
```bash
python scripts/rehidratar_traspaso_detalle.py --traspaso-id 2 --yes
```

**Validar:**
- `traspaso_detalle` rows > 0
- `SUM(cantidad)` ≈ 40-44 pares

### Paso 3: Audit final
```bash
python scripts/auditar_combinacion_traspaso.py --traspaso-id 2 --compra-id 1
```

**Checks:**
- `combinacion_total_count` > 0
- `traspaso_detalle_rows` >= 15
- `traspaso_detalle_pares` >= 40

---

## Checks Cierre OT-505-001

```json
{
  "C1": "combinacion count > 0 para SKUs FI",
  "C2": "traspaso_detalle pares >= 40",
  "C3": "0 duplicate (traspaso_id, combinacion_id)"
}
```

---

**Archivo:** `docs/AUDIT_COMBINACION_VACIA.md`  
**Status:** Fase 1 completa — Fase 2 backfill pendiente
