# OT-COMPRA-WEB-507-001 — Compra Web = mismo formato FI (5 pilares + caso precio)

**Estado:** ✅ CERRADA (2026-05-17) — evidencia `OT-COMPRA-WEB-507-001-EVIDENCIA.json`  
**Fecha:** 2026-05-17  
**Disparador:** Detalle traspaso en Compra Web muestra **~198 filas planas** (1 fila × talla); Facturación / Compra Legal muestran **Ley FI** (moléculas + grada + tallas + **caso**).

## Regla de negocio (usuario)

> Es la **misma Factura Interna**, solo en otra estación (distribución abierta / recepción Bazar).  
> El **formato visual debe ser idéntico** al de Facturación y Compra Legal: **5 pilares + grada/tallas**, y **siempre** el **caso que formó el precio** (ej. `ACT-BRSPORT`).

Referencia normativa existente: `.cursor/rules/rimec-ley-fi-card.mdc`

---

## Síntoma actual

| Pantalla | Vista detalle FI / traspaso |
|----------|----------------------------|
| Facturación | `render_fi_card` + `get_fi_detalles_canonico` ✓ |
| Compra Legal (FAC-INT) | `render_fi_card` ✓ |
| **Compra Web** (T-2026-0001) | `st.dataframe` plano: Línea, Ref, Material, Color, **Talla**, Pares, Caso — **1 fila por talla** (~19–198 líneas) ✗ |

**Efectos:**

1. UX distinta a FI (no es “la misma factura”).
2. **Caso** puede salir mal: `get_traspaso_detalle_lines` hace `LEFT JOIN precio_lista` solo por `linea+referencia` → **duplica filas** si hay varios casos en el listado.
3. El **caso correcto** está en `factura_interna.caso` / `caso_id` (el que formó el precio de esa FAC-INT), no en un join genérico a `precio_lista`.

---

## Causa raíz técnica

| Archivo | Problema |
|---------|----------|
| `modules/compra_web/ui.py` L172-208 | Usa `get_traspaso_detalle_lines` + tabla plana; **no** usa Ley FI |
| `modules/compra_legal/logic.py` `get_traspaso_detalle_lines` | Formato largo (talla × fila); JOIN `precio_lista` sin agregar por molécula |
| Ley FI | `compra_web` **no** listado en módulos alineados (`rimec-ley-fi-card.mdc`) |

---

## Objetivo

1. En detalle de traspaso Compra Web: mostrar la **FAC-INT vinculada** (`traspaso.documento_ref` → `get_fi_registro_por_numero`) con **`render_fi_card`** y **`get_fi_detalles_canonico(fi_id)`**.
2. Header FI debe mostrar **`caso`** (nombre del caso que formó el precio) igual que Facturación.
3. Tabla operativa de recepción (opcional): resumen por molécula vía `get_factura_lineas(nro_factura)` + `render_tabla_5pilares` **solo como complemento**, no reemplazo del card.
4. Corregir `get_traspaso_detalle_lines`: caso desde `fi.caso`; eliminar duplicación por `precio_lista` (usar subquery / `DISTINCT ON (td.id)` o quitar join lista para UI).
5. Actualizar regla `rimec-ley-fi-card.mdc`: incluir `compra_web/ui.py`.

---

## Fase 1 — Código UI Compra Web

| ID | Tarea |
|----|--------|
| R1 | En `_render_detalle_traspaso`: obtener `doc_ref = detail['factura']` o `documento_ref` del traspaso |
| R2 | `fi_row = get_fi_registro_por_numero(doc_ref)` (`modules/facturacion/logic.py`) |
| R3 | Si `fi_row`: `render_fi_card(fi_row, detalles=get_fi_detalles_canonico(fi_row['id']), mostrar_detalle=True, detalle_colapsado=False, key_prefix=f'cw_fi_{id_trp}', mostrar_descuentos=True)` |
| R4 | **Eliminar** o colapsar por defecto el expander tabla plana de 198 filas; si se mantiene, caption "Vista técnica (stock/combinacion_id)" |
| R5 | Legacy: si no hay fila `factura_interna`, fallback `get_factura_lineas(doc_ref)` + `render_tabla_5pilares` + banner "legacy" |

**Imports esperados en `compra_web/ui.py`:**

```python
from core.fi_card import render_fi_card
from modules.facturacion.logic import get_fi_registro_por_numero, get_factura_lineas
from modules.pedido_proveedor.logic import get_fi_detalles_canonico
from core.tabla_articulos import render_tabla_5pilares
```

---

## Fase 2 — Logic: caso + sin duplicados

| ID | Tarea |
|----|--------|
| L1 | En `get_traspaso_detalle_lines`: agregar `COALESCE(fi.caso, '—') AS caso_nombre` desde `factura_interna fi` por `fi.nro_factura = t.documento_ref` |
| L2 | **Quitar** join que multiplica filas: `LEFT JOIN precio_lista pl ON ... linea_codigo AND referencia_codigo` (o limitar a 1 fila con `DISTINCT ON (td.id)`) |
| L3 | Quitar `print(DEBUG...)` de producción |
| L4 | (Opcional) Nueva función `get_traspaso_lineas_molecula(id_trp)` → delega a `get_factura_lineas(documento_ref)` para totales que coincidan con FI |

---

## Fase 3 — Documentación

| ID | Tarea |
|----|--------|
| D1 | Actualizar `.cursor/rules/rimec-ley-fi-card.mdc` — fila Compra Web |
| D2 | Crear `docs/COMPRA_WEB_LEY_FI.md` (1 página: traspaso = espejo FI, caso obligatorio) |

---

## Fase 4 — Verificación

| ID | Criterio |
|----|----------|
| V1 | Compra Web → T-2026-0001 → FAC **1-PV001**: card FI visible (imagen, pilares, gradas) |
| V2 | Caso mostrado = el de `factura_interna.caso` (ej. **ACT-BRSPORT**), mismo que Facturación |
| V3 | **4 moléculas** (no 198 filas) en vista principal |
| V4 | Σ pares en card = **44** (alineado OT-505-002) |
| V5 | Compra Legal → misma FI: mismo caso y mismos totales (paridad visual) |

**JSON:** `OT-COMPRA-WEB-507-001-EVIDENCIA.json`

```json
{
  "ot_id": "OT-COMPRA-WEB-507-001",
  "traspaso": "T-2026-0001",
  "fi": "1-PV001",
  "checks": [
    {"id": "C1", "pass": true, "expected": "render_fi_card en compra_web", "actual": "..."},
    {"id": "C2", "pass": true, "expected": "caso = fi.caso", "actual": "ACT-BRSPORT"},
    {"id": "C3", "pass": true, "expected": "moleculas vista principal", "actual": 4},
    {"id": "C4", "pass": true, "expected": "sin duplicacion filas UI", "actual": "..."},
    {"id": "C5", "pass": true, "expected": "paridad facturacion", "actual": "OK"}
  ]
}
```

---

## Orden ejecución Claude Code

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main

# Editar modules/compra_web/ui.py (R1-R5)
# Editar modules/compra_legal/logic.py (L1-L3)
# Editar .cursor/rules/rimec-ley-fi-card.mdc

# Smoke manual Nexus:
#   Facturación 1-PV001  vs  Compra Web T-2026-0001  vs  Compra Legal CL-2026-0001
# Captura o nota: caso, 4 SKUs, 44 pares

# Evidencia JSON
```

**No pedir confirmación.** Reportar PASS/FAIL con captura mental: caso visible y 4 ítems molécula.

---

## Fuera de alcance

- Cambios en `rimec-web` tienda pública.
- Rehidratar traspaso / stock (OT-506-001).
- Recalcular precios del listado.

---

## Nota arquitectura

**Distribución abierta** = el traspaso es logística; la **verdad comercial** sigue siendo la **FAC-INT**. Por eso la UI de recepción debe anclarse a `factura_interna` + `render_fi_card`, no reinventar tabla desde `traspaso_detalle` fila a fila.
