# Diccionario precio venta Web (Bazar)

> **OT:** [OT-WEB-PRECIO-509-001](../OT-WEB-PRECIO-509-001.md) — **CERRADA** (2026-05-17).  
> Migración `048_caso_precio_web_regla.sql` · módulo Nexus `web_precio_caso` · `rimec-web` lista 1.

---

## Fórmula

```
precio_venta_web = LPN × (1 + markup_pct / 100)
```

Redondeo: según política web (centena si se alinea con motor de precios).

---

## Reglas iniciales (seed)

| `caso_codigo` | Markup |
|---------------|--------|
| `BR-VZ-MD-ML-MKA-O` | +50% |
| `ACT-BRSPORT` | +50% |
| `CARTERAS` | +40% |
| `CHINELO` | +40% |
| `PROMOCIONAL` | +40% |

Ejemplo: LPN 100.000 + caso ACT-BRSPORT (+50%) → **150.000 Gs** en galería.

---

## Dónde se edita

- **Nexus:** sidebar → **🌐 Diccionario Web** → tabla `caso_precio_web_regla`
- Roles: ADMIN / DIRECTOR / ROOT
- Cambio de markup → efecto inmediato en catálogo (vista `v_stock_rimec`)
- **No editar** markup en código salvo nuevos casos seed en migración

---

## Dónde se consume

- Vista `v_stock_rimec.precio_web` (Nexus / Supabase)
- `rimec-web`: catálogo (`app/page.tsx`, `CatalogoGrid.tsx`) y carrito (`store/sesionVenta.ts`)

---

## Caso por SKU

El caso viene del **listado de precios** (`nombre_caso_aplicado` / `descp_caso` en línea), mismo criterio que Factura Interna.

Si no hay regla para el caso → fila `DEFAULT` (+50%) + auditoría (`scripts/auditar_precio_web_casos.py`).

---

## Relación con LPN

| Concepto | Uso |
|----------|-----|
| **LPN** | Precio costo/lista importadora (interno) |
| **precio_web** | Precio mostrado al cliente en Bazar |
| Descuentos vendedor (carrito) | Se aplican **sobre** `precio_web`, no sobre LPN crudo |

---

## Depósito Web vs Bazar (OT-510)

| Pantalla | Qué muestra |
|----------|-------------|
| **Depósito Web** (Nexus) | Stock ALM_WEB_01 + **LPN** + **Precio venta** (misma fórmula) |
| **Galería Bazar** (`rimec-web`) | `precio_web` del catálogo |

Operador y cliente deben ver el **mismo Precio venta** por molécula (línea + ref + material + color).  
Auditoría: `scripts/auditar_paridad_deposito_web_rimec.py` (OT-DEPOSITO-WEB-510-001).
