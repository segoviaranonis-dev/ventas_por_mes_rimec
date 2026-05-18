# OT-FI-CASO-508-001 — Persistir y mostrar caso que formó el precio en FI

**Estado:** ✅ FASE 1 CERRADA (2026-05-17) · 📋 FASE 2 PENDIENTE (persistir al crear FI) — evidencia `OT-FI-CASO-508-001-EVIDENCIA.json`  
**Fecha:** 2026-05-17  
**Disparador:** Card FI muestra **"Caso: Sin caso"** en 1-PV001, pero el PP tiene listado vigente **evento #8** (CP 7447-4085x) con biblioteca de casos y precios aplicados (Gs. 5.894.800 correctos).

## Regla de negocio

> El **caso comercial** que formó el LPN (ej. `ACT-BRSPORT`) debe quedar **grabado en `factura_interna`** y verse en **todas** las pantallas Ley FI (Facturación, Compra Legal, Compra Web, PP).

"No tiene caso" en UI = `fi.caso` NULL en BD, **no** que falte el listado.

---

## Causa raíz (código)

| Flujo | Archivo | ¿Graba `caso` / `caso_id` / `marca`? |
|-------|---------|--------------------------------------|
| **crear_factura_interna** (1-PV001) | `pedido_proveedor/logic.py` ~L2710 | **NO** — solo `lista_precio_id` |
| **save_factura_manual** (Facturación carga) | `pedido_proveedor/logic.py` ~L1134 | **NO** |
| **recalcular_facturas_internas_pp** | `pedido_proveedor/logic.py` ~L2428 | **NO** — solo totales + `lista_precio_id` |
| **confirmar preventa** | `aprobacion_pedidos/logic.py` ~L486 | **SÍ** (`marca`, `caso`) |

`render_fi_card` (`core/fi_card.py` L113): `caso = fi.get("caso") or "Sin caso"` → placeholder cuando columna vacía.

**Conclusión:** Los precios vienen de `precio_lista.nombre_caso_aplicado` del evento, pero **nunca se copian** al header de la FI al crear/recalcular.

---

## Objetivo

1. **Backfill** FI existentes del PP-2026-0001 (mínimo `1-PV001`).
2. **Persistir** `marca`, `caso`, `caso_id` (y `marca_id` si resoluble) en `crear_factura_interna` y en `recalcular_facturas_internas_pp`.
3. **Fallback lectura** en `get_fi_registro_por_numero` si `fi.caso` sigue NULL (join evento/listado).
4. Verificar card: **Caso: ACT-BRSPORT** (o el caso dominante del evento #8).

---

## Fase 1 — Backfill datos (1-PV001)

| ID | Tarea |
|----|--------|
| B1 | Crear `scripts/reparar_fi_caso_desde_listado.py` |
| B2 | Para cada `factura_interna` con `lista_precio_id` (evento) y `caso` NULL/empty: |

```sql
-- Resolver caso dominante del evento (modo más frecuente en precio_lista de líneas de la FI)
SELECT pl.nombre_caso_aplicado, pl.caso_biblioteca_id  -- ajustar nombre columna real
FROM precio_lista pl
WHERE pl.evento_id = fi.lista_precio_id
  AND pl.nombre_caso_aplicado IS NOT NULL
GROUP BY 1, 2
ORDER BY COUNT(*) DESC
LIMIT 1;
```

| B3 | `UPDATE factura_interna SET caso = ..., caso_id = ..., marca = COALESCE(marca, ...)` para `nro_factura IN ('1-PV001')` o `pp_id=1` |
| B4 | Dry-run + `--yes`; log por FI |

**Criterio:** `SELECT caso, caso_id, marca FROM factura_interna WHERE nro_factura='1-PV001'` ≠ NULL.

---

## Fase 2 — Persistir al crear / recalcular FI

| ID | Tarea | Archivo |
|----|--------|---------|
| P1 | Función `_resolver_caso_marca_fi(conn, evento_id, items)` → `(caso_nombre, caso_id, marca_nombre, marca_id)` desde `precio_lista` + `marca_v2` / línea del primer ítem o moda por líneas del detalle | `pedido_proveedor/logic.py` |
| P2 | En `crear_factura_interna`: incluir en INSERT `marca, caso, marca_id, caso_id` | mismo |
| P3 | En `recalcular_facturas_internas_pp` UPDATE header: además de totales, set `caso`, `caso_id`, `marca` si resoluble | mismo |
| P4 | En `save_factura_manual` INSERT header: mismo patrón (Facturación legacy path) | mismo |
| P5 | Tests manuales: nueva FI de prueba en PP test → caso visible al crear |

**Regla caso dominante:** Si el evento tiene un solo `nombre_caso_aplicado` para las líneas facturadas, usar ese. Si hay varios, usar el **más frecuente** entre las líneas del detalle; si empate, el de mayor `SUM(pares)`.

---

## Fase 3 — Fallback lectura (defensa)

| ID | Tarea |
|----|--------|
| L1 | En `get_fi_registro_por_numero` y `get_facturas_interna_de_pp`: |

```sql
COALESCE(
  NULLIF(TRIM(fi.caso), ''),
  (SELECT pl.nombre_caso_aplicado FROM precio_lista pl
   WHERE pl.evento_id = fi.lista_precio_id
     AND pl.nombre_caso_aplicado IS NOT NULL
   GROUP BY pl.nombre_caso_aplicado
   ORDER BY COUNT(*) DESC LIMIT 1)
) AS caso
```

| L2 | Igual para `caso_id` si existe columna en `precio_lista` o join `caso_precio_biblioteca` |

Así el card no muestra "Sin caso" aunque falte backfill puntual.

---

## Fase 4 — Verificación UI

| ID | Pantalla | Esperado |
|----|----------|----------|
| V1 | PP → Facturas Internas → 1-PV001 | **Caso: ACT-BRSPORT** (o nombre real en listado) |
| V2 | Facturación → misma FI | Mismo caso |
| V3 | Compra Legal → CL → FI | Mismo caso |
| V4 | Compra Web → T-2026-0001 | Mismo caso en card |
| V5 | Listado PP evento #8 | Coherente con caso mostrado |

**JSON:** `OT-FI-CASO-508-001-EVIDENCIA.json`

---

## Orden Claude Code

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main

# Investigar columnas precio_lista
# python -c "..." o query en script

python scripts/reparar_fi_caso_desde_listado.py --pp-id 1 --dry-run
python scripts/reparar_fi_caso_desde_listado.py --pp-id 1 --yes

# Tras cambios logic.py: reiniciar Streamlit si aplica
# Smoke UI V1-V4
```

---

## Checks cierre

```json
{
  "ot_id": "OT-FI-CASO-508-001",
  "fi": "1-PV001",
  "checks": [
    {"id": "C1", "pass": true, "expected": "fi.caso en BD", "actual": "ACT-BRSPORT"},
    {"id": "C2", "pass": true, "expected": "UI no Sin caso", "actual": "..."},
    {"id": "C3", "pass": true, "expected": "crear_factura_interna persiste caso", "actual": "..."},
    {"id": "C4", "pass": true, "expected": "recalc actualiza caso", "actual": "..."}
  ]
}
```

---

## Fuera de alcance

- Reescribir política "caso por línea vs por evento" (migración 025/039).
- Cambiar precios del listado #8.

---

## Nota para el usuario

El listado **sí llegó** (precios y total OK). Lo que **no llegó** es la **copia del nombre del caso al header de la factura** al crear la FI desde Pedido Proveedor / Facturación. OT-507 solo leyó `fi.caso` — estaba vacío por diseño del INSERT, no por error de Compra Web.
