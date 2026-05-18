# Audit: Traspaso Duplicados — UniqueViolation (traspaso_id, combinacion_id)

> Histórico OT-TRASPASO-504-001. Estado: **CERRADA** — ver `docs/OT_REGISTRO_ESTADO.md`

**OT:** OT-TRASPASO-504-001 Fase 1  
**Fecha:** 2026-05-17  
**Compra:** CL-2026-0001 (proforma 7441-4084, estado PENDIENTE)

---

## Resumen Ejecutivo

**Problema:** Al llamar `finalizar_compra(1)` → `_crear_traspasos_para_pp`, la función itera sobre FI detalles y crea traspaso_detalle. Cuando **múltiples fid rows** del mismo SKU (linea+ref+mat+col) tienen **tallas overlapeadas**, resuelven al mismo `combinacion_id` y el segundo INSERT falla con:

```
UniqueViolation: duplicate key value violates unique constraint "traspaso_detalle_traspaso_id_combinacion_id_key"
Detail: Key (traspaso_id, combinacion_id)=(1, 3) already exists.
```

**Root Cause:**  
`crear_traspaso_por_factura` (logic.py:209-229) hace INSERT directo por cada talla de cada item en `items_tallas`, sin agrupar cantidades por `combinacion_id` primero. Efecto colateral del saneo módulo 500: múltiples fid con misma molécula/curva → duplicados.

---

## Caso Detectado: CL-2026-0001

### Inventario FI

- **Total FI:** 5 facturas internas (CONFIRMADA/RESERVADA)
- **Total fid rows:** 5
- **Total SKU groups:** 4
- **Total talla expansions:** 23

### SKU con Problema

**SKU:** 4202-500-39-53  
**Fid rows:** 2

| fid_id | Tallas |
|--------|--------|
| 1 | t35, t36, **t37, t38, t39, t40** |
| 2 | **t37, t38, t39, t40** |

**Overlap:** t37, t38, t39, t40 → **4 tallas duplicadas**

Cuando `_crear_traspasos_para_pp` procesa la FI:
1. **Primer item (fid=1):**  
   - Resuelve combinacion_id para (4202, 500, 39, 53, t37) → comb_id=X  
   - INSERT traspaso_detalle (1, X, qty)  
   - Igual para t38, t39, t40

2. **Segundo item (fid=2):**  
   - Resuelve las mismas combinaciones → **mismo comb_id**  
   - INSERT (1, X, qty) → **UniqueViolation** porque (1, X) ya existe

---

## Flujo Actual (Buggy)

```python
# crear_traspaso_por_factura (logic.py:209-229)
for rec in items_tallas:              # Cada rec = 1 fid row
    for col, qty_val in rec.get("tallas", {}).items():
        qty = int(qty_val or 0)
        if qty <= 0:
            continue
        t = col.replace("t", "")
        comb_id = _resolve_combinacion_id(...)
        if comb_id is None:
            continue
        # ❌ DIRECTO INSERT sin verificar si ya existe
        conn.execute(sqlt("""
            INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
            VALUES (:trp_id, :comb_id, :qty)
        """), {"trp_id": trp_id, "comb_id": comb_id, "qty": qty})
```

**Problema:** Si `items_tallas[0]` y `items_tallas[1]` resuelven al mismo `comb_id` para la misma talla → segundo INSERT choca con UNIQUE constraint.

---

## Solución Propuesta (Fase 2)

### Opción A: Agrupar antes del INSERT

```python
# Acumular qty por combinacion_id
comb_qty_map = {}  # {comb_id: total_qty}

for rec in items_tallas:
    for col, qty_val in rec.get("tallas", {}).items():
        qty = int(qty_val or 0)
        if qty <= 0:
            continue
        t = col.replace("t", "")
        comb_id = _resolve_combinacion_id(...)
        if comb_id is None:
            continue
        comb_qty_map[comb_id] = comb_qty_map.get(comb_id, 0) + qty

# Insertar una sola vez por combinacion_id
for comb_id, total_qty in comb_qty_map.items():
    conn.execute(sqlt("""
        INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
        VALUES (:trp_id, :comb_id, :qty)
    """), {"trp_id": trp_id, "comb_id": comb_id, "qty": total_qty})
```

### Opción B: UPSERT (ON CONFLICT)

```python
conn.execute(sqlt("""
    INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
    VALUES (:trp_id, :comb_id, :qty)
    ON CONFLICT (traspaso_id, combinacion_id)
    DO UPDATE SET cantidad = traspaso_detalle.cantidad + EXCLUDED.cantidad
"""), {"trp_id": trp_id, "comb_id": comb_id, "qty": qty})
```

**Recomendación:** **Opción A** (agrupar primero) es más eficiente y explícito. Opción B es segura como fallback pero hace más queries.

### Opción C: Merge en _crear_traspasos_para_pp

Antes de pasar `items_tallas` a `crear_traspaso_por_factura`, agrupar por SKU (linea+ref+mat+col) y sumar tallas:

```python
# Merge items_tallas por SKU
merged = {}  # {(linea, ref, mat, col): {"linea": ..., "tallas": {t37: N, ...}}}
for item in items_tallas:
    key = (item["linea"], item["referencia"], item["id_material"], item["id_color"])
    if key not in merged:
        merged[key] = {**item, "tallas": {}}
    for talla, qty in item["tallas"].items():
        merged[key]["tallas"][talla] = merged[key]["tallas"].get(talla, 0) + qty

items_tallas_merged = list(merged.values())
```

Luego pasar `items_tallas_merged` a `crear_traspaso_por_factura`.

**Recomendación:** Aplicar **Opción A en crear_traspaso_por_factura** (genérico) + **Opción C en _crear_traspasos_para_pp** (específico para FI) para doble protección.

---

## Script de Reparación

Si un traspaso quedó a medias (ej. traspaso_id=1 con filas parciales):

```bash
python scripts/reparar_traspaso_parcial.py --traspaso-id 1
```

El script debe:
1. Verificar si `traspaso_detalle` tiene duplicados (GROUP BY + HAVING COUNT(*) > 1)
2. Si hay duplicados, consolidar cantidades:
   ```sql
   WITH dups AS (
       SELECT traspaso_id, combinacion_id, SUM(cantidad) AS total_qty
       FROM traspaso_detalle
       WHERE traspaso_id = 1
       GROUP BY traspaso_id, combinacion_id
   )
   DELETE FROM traspaso_detalle WHERE traspaso_id = 1;
   
   INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad)
   SELECT traspaso_id, combinacion_id, total_qty FROM dups;
   ```
3. Log acción en `flujo_actividad`

---

## Checklist Fase 2 (Fix)

- [ ] R1: Implementar agrupación en `crear_traspaso_por_factura` (Opción A)
- [ ] R2: Agregar merge de items_tallas en `_crear_traspasos_para_pp` (Opción C)
- [ ] R3: Crear `reparar_traspaso_parcial.py` para limpiar traspaso_id=1 si quedó a medias
- [ ] R4: Test: `finalizar_compra(1)` debe completar sin error
- [ ] R5: Validar: 0 duplicados en `traspaso_detalle`, pares traspaso ≈ 44

---

**Archivo:** `docs/AUDIT_TRASPASO_DUPLICADOS.md`  
**Status:** Fase 1 completa — Fase 2 pendiente
