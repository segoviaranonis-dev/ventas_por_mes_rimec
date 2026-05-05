# POLÍTICAS BLINDADAS — CICLO DE IMPORTACIÓN RIMEC
> Documento de precedente. Aprobado por Dirección el 21/04/2026.
> Estas políticas NO se discuten. Se implementan.
> Cualquier desarrollo que contradiga este documento es un error a corregir.

---

## LEY 1 — EL ADN DE LA INTENCIÓN DE COMPRA

Toda Intención de Compra nace con dos clasificaciones obligatorias e inamovibles:

**TIPO** (División operacional):
- `Tipo 1 — CALZADOS`: proveedor 654 (Beira Rio). Motor actual.
- `Tipo 2 — CONFECCIONES`: estructura preparada, proveedores futuros.

**CATEGORÍA** (Estrategia de compra):
- `COMPRA PREVIA`: mercadería que se compra para la importadora. Se ofrece mediante catálogo a mayoristas durante los 90 días de tránsito. Tiene sector de stock disponible Y sector de facturas.
- `PROGRAMADO`: intermediación directa fábrica → cliente mayorista. La importadora es el puente de gestión. NO tiene sector de stock. Solo tiene facturas.

> Ningún registro de IC puede existir sin estos dos campos definidos.

---

## LEY 2 — EL STOCK NO SE ELIGE, SE GANA

La categoría STOCK (ID 3) **nunca** se selecciona manualmente.
Es un resultado automático que ocurre cuando:

1. La mercadería llega al depósito después de los 90 días de tránsito
2. El sistema calcula: `saldo = cantidad_comprada - cantidad_facturada_en_tránsito`
3. Si `saldo > 0` → ese saldo ingresa al depósito con `categoria_id = STOCK`

La IC original queda como COMPRA PREVIA para siempre.
El ingreso al depósito crea un movimiento nuevo con categoría STOCK.
Así el Sales Report puede responder ambas preguntas:
- "¿Cuánto compramos como Compra Previa?"
- "¿Cuánto de eso terminó en Stock?"

---

## LEY 3 — EL MÓDULO DE FACTURACIÓN DEFINE LA CATEGORÍA

El módulo de facturación lee el `categoria_id` del pedido proveedor padre
y lo hereda en cada factura. No hay intervención manual.

```
IC (categoria_id) → Pedido Proveedor (hereda categoria_id) → Factura (hereda categoria_id)
```

**Comportamiento por categoría en el Pedido Proveedor:**

| Categoría | Sector Stock visible | Sector Facturas |
|-----------|---------------------|-----------------|
| COMPRA PREVIA | ✅ Sí — cantidad disponible para vender en tránsito | ✅ Sí |
| PROGRAMADO | ❌ No — no hay stock disponible | ✅ Sí — solo facturas directas |

---

## LEY 4 — HERENCIA DE TRAZABILIDAD (LOS CABLES)

Cada tabla del flujo operativo hereda `categoria_id` de su padre:

```
intencion_compra.categoria_id
        ↓ hereda
pedido_proveedor.categoria_id
        ↓ hereda
compra_legal.categoria_id (o facturacion)
        ↓ hereda
movimiento / venta_transito.categoria_id
        ↓ alimenta
registro_ventas_general_v2 (Sales Report)
```

Esta cadena es lo que permite al Sales Report distinguir en el futuro:
- Ventas de Compra Previa (vendido en tránsito)
- Ventas de Programado (intermediación)
- Ventas de Stock (saldo que llegó al depósito)

---

## LEY 5 — MÓDULO ADMINISTRATIVO DE ASIGNACIÓN (FUTURO)

Una vez refinado el módulo de Intención de Compra, se creará un módulo
administrativo de asignación y administración de las IC al Pedido Proveedor.

**Este módulo NO se desarrolla hasta que el Director lo indique.**
El desarrollo sigue el orden que marca la Dirección, no el que conviene técnicamente.

---

## ORDEN DE DESARROLLO VIGENTE

```
1. ✅ Intención de Compra V2 — refinamiento UI (ACTUAL)
2. ⏳ Módulo administrativo IC → Pedido Proveedor (DESPUÉS)
3. ⏳ Módulo de Depósito — lógica de saldo → Stock automático
4. ⏳ Facturación — herencia de categoría
5. ⏳ Sales Report — absorción completa (ES LO ÚLTIMO)
```

---

> "El sistema no dicta las reglas. El Director las dicta.
> El sistema las implementa sin cuestionarlas."
