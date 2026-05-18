# OT-DEPOSITO-WEB-510-001 — Depósito Web: LPN + Precio venta (= galería Bazar)

**Estado:** PENDIENTE EJECUCIÓN (Claude Code)  
**Fecha:** 2026-05-17  
**Depende de:** OT-WEB-PRECIO-509-001 (tabla `caso_precio_web_regla`, `fn_precio_venta_web`, `v_stock_rimec.precio_web`)  
**Disparador:** Depósito Web solo muestra Stock; usuario exige **LPN** y **Precio venta** — el mismo que ve el cliente en `rimec-web`.

## Regla de negocio (cerrada)

| Columna Nexus Depósito Web | Significado | Debe coincidir con |
|----------------------------|-------------|-------------------|
| **LPN** | Precio lista importadora (costo base) | `precio_lista.lpn` del evento vigente del PP |
| **Precio venta** | LPN + markup % del caso | `v_stock_rimec.precio_web` = `fn_precio_venta_web(lpn, caso)` |
| **Stock** | Pares en ALM_WEB_01 | `movimiento_detalle` (sin cambio) |

**Una sola fuente de verdad para precio venta:** `fn_precio_venta_web` + diccionario `caso_precio_web_regla` (Nexus → Diccionario Web).

El precio en la **página web** (`rimec-web`, lista 1) **debe ser idéntico** al **Precio venta** del Depósito Web para el mismo SKU (línea + ref + material + color).

---

## Estado actual

| Módulo | Fuente datos | Precios |
|--------|--------------|---------|
| `deposito_web` | `movimiento_detalle` → combinación | Solo `stock_total` |
| `rimec-web` | `v_stock_rimec` | `lpn`, `precio_web` (OT-509) |

**Gap:** Depósito no resuelve LPN/caso para SKUs del almacén web; no hay paridad visible operador ↔ tienda.

---

## Objetivo

1. Tabla resumen Depósito Web: columnas **LPN**, **Caso**, **Markup %**, **Precio venta**, **Stock**.
2. Desglose por talla (opcional): mismas columnas a nivel talla si aplica, o solo stock por talla.
3. Script auditoría **paridad** Depósito ↔ `rimec-web`.
4. Documentación operativa actualizada.

---

## Fase 1 — Logic (`modules/deposito_web/logic.py`)

| ID | Tarea |
|----|--------|
| L1 | Resolver **evento de precio** por traspaso/PP: `traspaso.snapshot_json->>'id_pp'` → `intencion_compra_pedido.precio_evento_id` o `pedido_proveedor` evento vigente (mismo criterio que `get_skus_con_precio_para_fi`) |
| L2 | Por molécula `(linea, referencia, material, color)` en stock web, JOIN `precio_lista` ON `evento_id` + match línea/material (y ref si aplica) |
| L3 | Columnas en `get_resumen_web()`: `lpn`, `caso_precio`, `markup_pct`, `precio_venta` donde `precio_venta = fn_precio_venta_web(lpn, caso_precio)` en SQL |
| L4 | `get_stock_web()`: opcional `lpn`, `precio_venta` por fila talla (mismo join) |
| L5 | Si no hay LPN: `lpn`/`precio_venta` NULL + flag; no inventar precio |

**Query referencia (esqueleto):**

```sql
-- Tras obtener filas de movimiento_detalle agrupadas, enriquecer:
LEFT JOIN LATERAL (
  SELECT pl.lpn, pl.nombre_caso_aplicado AS caso_precio
  FROM precio_lista pl
  WHERE pl.evento_id = :evento_id
    AND pl.linea_codigo = l.codigo_proveedor::text  -- ajustar a columnas reales de precio_lista
    AND ... match material ...
  LIMIT 1
) pl ON true
-- precio_venta = fn_precio_venta_web(pl.lpn, pl.caso_precio)
```

Ajustar nombres de columnas `precio_lista` según esquema real (puede ser `linea_id`/`material_id`).

---

## Fase 2 — UI (`modules/deposito_web/ui.py`)

| ID | Tarea |
|----|--------|
| U1 | Tabla principal (expander marca): columnas orden |

`Línea | Ref. | Material | Color | LPN | Caso | Markup % | Precio venta | Stock`

| U2 | Formato número: `Gs. %,.0f` para LPN y Precio venta |
| U3 | Caption bajo tabla: *"Precio venta = LPN + markup del caso (Diccionario Web). Mismo valor que la galería Bazar."* |
| U4 | Link mental al módulo: *"Editar markup: 🌐 Diccionario Web"* |
| U5 | Desglose por talla: mantener stock por talla; opcional columna precio venta (misma para todas las tallas de la molécula) |

---

## Fase 3 — Paridad con rimec-web

| ID | Tarea |
|----|--------|
| P1 | Crear `scripts/auditar_paridad_deposito_web_rimec.py` |
| P2 | Para cada molécula en `get_resumen_web()` con stock > 0: buscar en `v_stock_rimec` por `linea_codigo`, `referencia_codigo`, `descp_material`, `descp_color` |
| P3 | Comparar `precio_venta` (depósito) vs `precio_web` (vista) — tolerancia 0 |
| P4 | Reportar: OK / MISMATCH / MISSING_LPN / MISSING_EN_WEB |
| P5 | Si MISMATCH > 0 → FAIL evidencia |

**Criterio:** ACTVITTA 4 artículos (44 pares) — 0 mismatches.

---

## Fase 4 — Diccionario Web (verificación, no reimplementar)

| ID | Tarea |
|----|--------|
| D1 | Confirmar 6 reglas en `caso_precio_web_regla` activas (509 seed) |
| D2 | `scripts/auditar_precio_web_casos.py` sigue PASS (268 SKUs) |
| D3 | No duplicar tabla diccionario — solo consumir |

---

## Fase 5 — Documentación

| ID | Archivo |
|----|---------|
| DOC1 | Actualizar `docs/DICCIONARIO_PRECIO_WEB.md` — sección "Depósito Web vs Bazar" |
| DOC2 | `OT-DEPOSITO-WEB-510-001-EVIDENCIA.json` |
| DOC3 | `docs/OT_REGISTRO_ESTADO.md` — entrada 510 |

---

## Checks cierre

```json
{
  "ot_id": "OT-DEPOSITO-WEB-510-001",
  "checks": [
    {"id": "C1", "pass": true, "expected": "UI columnas LPN + Precio venta", "actual": "..."},
    {"id": "C2", "pass": true, "expected": "precio_venta = fn_precio_venta_web", "actual": "..."},
    {"id": "C3", "pass": true, "expected": "paridad deposito vs v_stock_rimec 0 mismatch ACTVITTA", "actual": "..."},
    {"id": "C4", "pass": true, "expected": "ejemplo 82500 LPN -> 124000 venta (+50%)", "actual": "..."}
  ]
}
```

---

## Orden ejecución Claude Code

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main

# Implementar logic.py + ui.py
python scripts/auditar_paridad_deposito_web_rimec.py
python scripts/auditar_precio_web_casos.py

# Smoke Nexus: Depósito Web -> ACTVITTA -> ver LPN y Precio venta
# Smoke rimec-web: mismo SKU -> mismo Precio venta
```

**No pedir confirmación.** Reportar evidencia JSON + 3 ejemplos numéricos (LPN, caso, precio venta).

---

## Fuera de alcance

- Cambiar fórmula `fn_precio_venta_web` (ya en 509).
- Reescribir módulo Diccionario Web.
- Precios en Compra Legal / FI card (solo depósito + paridad web).

---

## Nota para auditoría Auto (post-ejecución)

El director validará:

1. Captura Depósito Web con columnas LPN + Precio venta.  
2. Captura misma molécula en Bazar.  
3. Salida `auditar_paridad_deposito_web_rimec.py` = 0 MISMATCH.  
4. Editar CHINELO 40%→45% en Diccionario → ambos reflejan cambio tras refresh.
