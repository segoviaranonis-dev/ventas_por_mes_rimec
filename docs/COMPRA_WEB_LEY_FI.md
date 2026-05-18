# Compra Web — Ley Factura Interna

**OT-COMPRA-WEB-507-001** — **CERRADA** 2026-05-17 · evidencia `OT-COMPRA-WEB-507-001-EVIDENCIA.json`  
**Registro OT:** `docs/OT_REGISTRO_ESTADO.md`

## Regla de negocio

> El **traspaso** es logística; la **verdad comercial** es la **Factura Interna**.

Compra Web (estación 4: Recepción Bazar) muestra traspasos que vienen de Facturación RIMEC. Cada traspaso está vinculado a una FAC-INT mediante `traspaso.documento_ref`.

**La vista del detalle del traspaso debe ser idéntica a la de Facturación y Compra Legal:**
- Mismo card visual (`render_fi_card`)
- Mismo caso comercial (`factura_interna.caso`)
- Mismas moléculas (5 pilares + grada/tallas)
- Misma imagen de calzado

## Implementación

### UI: `modules/compra_web/ui.py`

Función `_render_detalle_traspaso(id_trp)`:

```python
# 1. Obtener documento_ref del traspaso
doc_ref = detail.get("factura") or detail.get("documento_ref", "")

# 2. Buscar factura_interna
fi_row = get_fi_registro_por_numero(doc_ref)

# 3. Si existe, mostrar card FI
if fi_row:
    render_fi_card(
        fi_row,
        detalles=get_fi_detalles_canonico(fi_row["id"]),
        mostrar_detalle=True,
        detalle_colapsado=False,
        key_prefix=f"cw_fi_{id_trp}",
        mostrar_descuentos=True,
    )
```

### Caso comercial

**Correcto:** `factura_interna.caso` (el caso que formó el precio de esa FAC-INT específica).  
Post **OT-508 Fase 1:** backfill `1-PV001` → `lista_precio_id=8`, caso `BR-VZ-MD-ML-MKA-O`.  
**OT-508 Fase 2 pendiente:** persistir caso al crear nuevas FI (`crear_factura_interna`).

**Incorrecto:** JOIN suelto a `precio_lista` por línea+referencia (puede duplicar filas si hay múltiples casos en el listado)

### Vista técnica opcional

La tabla plana `get_traspaso_detalle_lines` (1 fila por talla, ~19-198 líneas) se mantiene como **expander colapsado** con caption "Vista técnica: Stock por talla" para operadores que necesitan ver combinacion_id.

**No es la vista principal.**

## Arquitectura

```
Facturación RIMEC  →  Compra Legal  →  Traspaso  →  Compra Web (Recepción)
      ↓                    ↓              ↓               ↓
  FAC-INT             FAC-INT         espejo FI      muestra FI
   (caso)              (caso)        (logística)      (card)
```

## Paridad visual

| Módulo | Vista FAC-INT | Caso visible |
|--------|--------------|--------------|
| Facturación | ✓ `render_fi_card` | ✓ `fi.caso` |
| Compra Legal | ✓ `render_fi_card` | ✓ `fi.caso` |
| **Compra Web** | ✓ `render_fi_card` | ✓ `fi.caso` |

## Smoke test

1. Nexus → **Facturación** → FAC-INT `1-PV001`
   - Capturar: caso, pares, moléculas

2. Nexus → **Compra Legal** → CL-2026-0001 → FAC `1-PV001`
   - Verificar: mismo caso, mismos pares

3. Nexus → **Compra Web** → T-2026-0001
   - Verificar: mismo card, mismo caso, mismos pares
   - Esperado: 4 moléculas, 44 pares, caso `ACT-BRSPORT` (o el que corresponda)

## Referencias

- `.cursor/rules/rimec-ley-fi-card.mdc`
- `core/fi_card.py::render_fi_card`
- `modules/facturacion/logic.py::get_fi_registro_por_numero`
- `modules/pedido_proveedor/logic.py::get_fi_detalles_canonico`
