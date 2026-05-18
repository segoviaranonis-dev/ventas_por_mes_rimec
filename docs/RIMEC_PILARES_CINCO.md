# RIMEC — Los 5 pilares y la trazabilidad molecular

> **Verdad de negocio.** Todo el SO (Nexus, procesos, webs) se apoya en esta jerarquía.  
> Aprobado por Dirección — carga de datos reales y operación del lunes.

---

## Los 5 pilares (identidad del artículo)

| # | Pilar | Tabla catálogo | Rol |
|---|--------|----------------|-----|
| 1 | **Línea** | `linea` | Modelo / línea proveedor (Beira Rio 654) |
| 2 | **Referencia** | `referencia` | Variante dentro de la línea |
| 3 | **Material** | `material` | Acabado / material |
| 4 | **Color** | `color` | Color |
| 5 | **Grada** | `talla` *(catálogo)* | Talle / número de calzado |

**Regla de precio (Motor):** el listado cotiza hasta **línea + referencia + material**. Color y grada **no cambian** LPN/LPC; sí identifican stock y venta a nivel molecular.

**Regla de identidad:** PK propia en cada pilar + `codigo_proveedor` + `UNIQUE(proveedor_id, codigo_proveedor)`.

---

## Dos formas de leer la grada (mismo pilar, distinta notación)

### Importadora — caja cerrada (mayorista / F9 / PP)

Una **caja** lleva la distribución de talles en un solo campo:

```text
35(1 2 3 3 2 1)40
```

- Rango de la caja: del **35** al **40**
- Paréntesis: cantidades por talle dentro de la caja (1+2+3+3+2+1 = pares por caja)
- Operación en **cajas**, no en unidades sueltas por talle en pantalla

En BD: `pedido_proveedor_detalle.grada` (texto) + `grades_json` (desglose molecular para trazabilidad e informes).

### Tiendas — Bazar Web (números abiertos)

Cada talle es una unidad explícita:

```text
N° 35 = 1
N° 36 = 1
N° 37 = 1
…
N° 40 = 1
```

- Stock y venta web por **combinación** atómica (cada talle con cantidad)
- Misma cadena de FK; granularidad distinta en UI y movimientos

---

## Tablas de relacionamiento (todo viaja por FK)

```text
linea ──┐
referencia ──┼── linea_referencia (estilo / tipo 1 — atributos L+R)
         │
         └── combinacion (linea_id + referencia_id + material_id + color_id + talla_id)
                    │
                    ├── movimiento_detalle → movimiento (historia stock)
                    ├── pedido_proveedor_detalle (F9 / tránsito + grada + grades_json)
                    ├── factura_interna_detalle / pedidos web
                    └── retail_multitienda_staging (Excel tiendas → FK pilares)
```

**`combinacion`** = molécula estable del artículo (5 FK).  
Cada **compra**, **estrategia de precio** (`precio_evento` + `precio_lista`), **PP**, **IC** y **movimiento** se enlaza por estas FK — no por texto suelto.

---

## Trazabilidad molecular e histórica

Objetivo: responder, para cualquier par vendido o en tránsito:

- ¿De qué **listado** / **caso** / **evento** salió el precio?
- ¿En qué **IC** y **PP** entró?
- ¿Qué **categoría** (Compra Previa / Programado / Stock)?
- ¿Qué **distribución de gradas** llevaba la caja?

Cadena típica:

```text
precio_evento (+ precio_evento_caso) → precio_lista (L+R+material)
        ↓
intencion_compra (+ precio_evento_id) → digitación → pedido_proveedor
        ↓
pedido_proveedor_detalle (FK ids + grada + grades_json)
        ↓
factura_interna / movimiento_detalle (combinacion_id)
        ↓
historia auditable (core.auditoria, precio_auditoria)
```

Cada capa es **reconstituible** hacia atrás: estrategia → compra → molécula → movimiento.

---

## Qué importa al cargar datos reales (lunes)

1. **Pilares 1–2** primero: `linea.xlsx` + `linea_referencia.xlsx` (`import_pilares_linea_lr_excel.py`).
2. **Material / color / talla** se completan con F9, combinaciones y motor (no solo el Excel de líneas).
3. **Listado de precios** cierra sobre L+R+material; luego IC con el mismo `precio_evento_id`.
4. **F9** trae grada en notación caja cerrada; validar `grades_json` antes de facturar en tránsito.
5. **Retail** Excel: columna `grada` simple o compuesta según tienda — FK a pilares en staging.

---

## Nombres en código (alias)

| Negocio | Técnico en repo |
|---------|------------------|
| Grada (pilar 5) | Tabla `talla`, FK `talla_id` en `combinacion` |
| Grada (notación) | Campo `grada`, `grades_json`, comentarios en retail staging |
| L+R atributos | `linea_referencia` (no confundir con los 5 pilares) |

---

*Sin pilares bien cargados no hay SO: solo pantallas. Con pilares + FK + eventos, la importadora opera con verdad molecular e histórica.*
