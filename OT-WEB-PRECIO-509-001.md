# OT-WEB-PRECIO-509-001 — Diccionario casos → precio venta Bazar Web (LPN + markup)

**Estado:** ✅ CERRADA (2026-05-17) — evidencia `OT-WEB-PRECIO-509-001-EVIDENCIA.json`  
**Fecha:** 2026-05-17  
**Repos:** `ventas_por_mes_rimec-main` (Nexus) + `rimec-web` (tienda)  
**Prerequisitos:** OT-508 Fase 1 OK (`fi.caso` persistido), Depósito Web con stock visible

## Regla de negocio (usuario)

**Precio de venta en sitio web** = `LPN × (1 + markup%)`, redondeo según política existente (centena si aplica en web).

| Caso (`nombre_caso_aplicado`) | Markup sobre LPN |
|------------------------------|------------------|
| `BR-VZ-MD-ML-MKA-O` | **+50%** |
| `ACT-BRSPORT` | **+50%** |
| `CARTERAS` | **+40%** |
| `CHINELO` | **+40%** |
| `PROMOCIONAL` | **+40%** |

Ejemplo: LPN = 100.000 → precio web = **150.000 Gs** (caso +50%).

**Requisito UX:** reglas **editables** sin tocar código (módulo diccionario en Nexus).

---

## Estado actual (diagnóstico)

| Capa | Hoy |
|------|-----|
| `rimec-web` catálogo | Lee `v_stock_rimec`; precio = `getPrecioActivo` → **LPN crudo** (`sesionVenta.ts` lista 1) |
| `v_stock_*` | `precio_web` suele ser NULL en migraciones recientes |
| Caso en catálogo | `descp_caso` / `caso_id` ya llegan a `CatalogoGrid` (Regla 1 FI) |
| Nexus | No existe tabla/UI de markup web por caso |

**Gap:** falta **diccionario persistente** + **aplicación** del markup al precio mostrado en galería/carrito.

---

## Arquitectura objetivo

```
precio_lista.lpn  +  caso (línea/FI/evento)
        ↓
caso_precio_web_regla (Nexus editable)
        ↓
precio_venta_web = f(lpn, markup_pct)
        ↓
v_stock_rimec.precio_web  (o cálculo en API rimec-web)
        ↓
CatalogoGrid / carrito muestran precio_venta_web
```

**Fuente del caso por SKU en web:** mismo criterio que listado — `nombre_caso_aplicado` del evento vigente del PP / línea (ya en vista o join existente). Si `caso` NULL → usar regla **default** documentada (ver Fase 1).

---

## Fase 1 — Modelo de datos (Supabase)

| ID | Tarea |
|----|--------|
| D1 | Migración `migrations/0XX_caso_precio_web_regla.sql` |

```sql
CREATE TABLE IF NOT EXISTS caso_precio_web_regla (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  caso_codigo     TEXT NOT NULL,          -- match exacto trim upper con nombre_caso_aplicado
  markup_pct      NUMERIC(5,2) NOT NULL,  -- 50.00 = +50%
  descripcion     TEXT,
  activo          BOOLEAN NOT NULL DEFAULT true,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_caso_precio_web_codigo UNIQUE (caso_codigo),
  CONSTRAINT chk_markup_nonneg CHECK (markup_pct >= 0)
);
```

| D2 | Seed inicial (5 filas usuario) + fila `DEFAULT` opcional (`markup_pct=50`, solo si caso desconocido — documentar decisión) |
| D3 | Función SQL `fn_precio_venta_web(p_lpn NUMERIC, p_caso TEXT) RETURNS NUMERIC` |

```sql
-- precio = ROUND(lpn * (1 + markup/100))  -- ajustar redondeo a centena si política web lo exige
```

| D4 | Actualizar vista `v_stock_rimec` (y `v_stock_web` si se usa) columnas:

- `lpn` (base, solo lectura interna si hace falta)
- `descp_caso` / `caso_codigo`
- `precio_web` = `fn_precio_venta_web(lpn, descp_caso)`
- `markup_pct_aplicado` (auditoría)

**Criterio D4:** query de prueba SKU ACTVITTA con LPN 100000 y caso ACT-BRSPORT → `precio_web = 150000`.

---

## Fase 2 — Módulo Nexus “Diccionario precios Web”

| ID | Tarea |
|----|--------|
| N1 | Nuevo módulo `modules/web_precio_caso/` o sección en **Motor de Precios** |
| N2 | UI Streamlit: tabla editable (caso_codigo, markup %, activo, descripción) |
| N3 | CRUD: listar, agregar, editar, desactivar (soft `activo=false`) |
| N4 | Validación: `caso_codigo` único, markup 0–200% |
| N5 | Registrar en `core/registry.py` + sidebar “Diccionario Web” o sub-tab Motor Precios |
| N6 | Sin hardcodear los 5 casos en Python — todo desde tabla |

**Criterio N2:** usuario puede cambiar CHINELO de 40% a 45% y guardar sin deploy.

---

## Fase 3 — rimec-web (catálogo + carrito)

| ID | Tarea |
|----|--------|
| W1 | `app/page.tsx`: leer `precio_web` de `v_stock_rimec` (preferido) o calcular con dictionary API |
| W2 | `CatalogoGrid.tsx`: mostrar **precio de venta** = `precio_web`; tooltip opcional “LPN base / +X% caso” |
| W3 | `store/sesionVenta.ts`: `getPrecioActivo` para lista Bazar → usar `precio_web` si existe, fallback LPN |
| W4 | `lib/cart.ts` / subtotales carrito: mismo precio que galería |
| W5 | No romper listas LPC02–04 si se usan en otros flujos; solo lista 1 (LPN/web) aplica markup por caso |

**Criterio W1:** producto con LPN 100.000 y caso ACT-BRSPORT muestra **150.000 Gs** en home y carrito.

---

## Fase 4 — Trazabilidad Nexus ↔ Web

| ID | Tarea |
|----|--------|
| T1 | En FI card o detalle PP: caption “Precio web estimado: LPN × (1+markup)” solo informativo (opcional) |
| T2 | Script `scripts/auditar_precio_web_casos.py`: lista SKUs sin caso, sin regla, sin LPN |

---

## Fase 5 — Verificación

| ID | Caso | Esperado |
|----|------|----------|
| V1 | Caso BR-VZ-MD-ML-MKA-O, LPN 100k | 150k |
| V2 | Caso ACT-BRSPORT, LPN 80k | 120k |
| V3 | Caso CHINELO, LPN 100k | 140k |
| V4 | Editar markup en Nexus → refresh web | Precio actualizado |
| V5 | Carrito subtotal | coherente con precio mostrado |

**JSON:** `OT-WEB-PRECIO-509-001-EVIDENCIA.json`

```json
{
  "ot_id": "OT-WEB-PRECIO-509-001",
  "reglas_seed": 5,
  "checks": [
    {"id": "C1", "pass": true, "expected": "tabla caso_precio_web_regla", "actual": "..."},
    {"id": "C2", "pass": true, "expected": "v_stock_rimec.precio_web", "actual": "..."},
    {"id": "C3", "pass": true, "expected": "UI Nexus edita markup", "actual": "..."},
    {"id": "C4", "pass": true, "expected": "rimec-web muestra LPN+markup", "actual": "..."}
  ]
}
```

---

## Orden ejecución Claude Code

```powershell
# 1. Nexus — migración + módulo
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main
# Crear migration, aplicar en Supabase
# modules/web_precio_caso/ui.py + logic.py
# Actualizar v_stock_rimec (migration o script vista)

python scripts/auditar_precio_web_casos.py

# 2. Web
cd C:\Users\hecto\Documents\Prg_locales\rimec-web
# page.tsx, CatalogoGrid, sesionVenta, cart.ts

npm run build
```

**No pedir confirmación** salvo credenciales BD. Reportar PASS/FAIL + 2 capturas (Nexus diccionario + web precio).

---

## Decisiones cerradas (no preguntar)

| Tema | Decisión |
|------|----------|
| Match caso | `UPPER(TRIM(caso_codigo))` = `UPPER(TRIM(nombre_caso_aplicado))` |
| Base precio | **LPN** del listado/evento vigente (no LPC02–04 para web) |
| Caso desconocido | Usar fila `DEFAULT` markup 50% + log warning en auditoría |
| Edición | Solo Nexus; web es consumidor |

---

## Fuera de alcance

- Cambiar LPN del motor de precios proveedor.
- Descuentos carrito (% vendedor) — siguen aplicándose **sobre** precio_venta_web si ya existen.
- Multi-moneda.

---

## Entregables albañil

1. `migrations/0XX_caso_precio_web_regla.sql` + seed  
2. `modules/web_precio_caso/` (o equivalente)  
3. Vista `v_stock_rimec` actualizada  
4. Cambios `rimec-web` (4 archivos mín.)  
5. `scripts/auditar_precio_web_casos.py`  
6. `OT-WEB-PRECIO-509-001-EVIDENCIA.json`  
7. `docs/DICCIONARIO_PRECIO_WEB.md` (1 página uso operativo)
