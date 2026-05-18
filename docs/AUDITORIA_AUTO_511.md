# Checklist auditoría Auto — OT-RESET-TRANSACCIONAL-511-001

> Ejecutar **después** de Claude Code. Comparar con `OT-RESET-TRANSACCIONAL-511-001-EVIDENCIA.json`.

---

## 1. Anti-regresión pilares (CRÍTICO)

```sql
SELECT 'linea' t, COUNT(*) FROM linea
UNION ALL SELECT 'referencia', COUNT(*) FROM referencia
UNION ALL SELECT 'linea_referencia', COUNT(*) FROM linea_referencia
UNION ALL SELECT 'material', COUNT(*) FROM material
UNION ALL SELECT 'color', COUNT(*) FROM color
UNION ALL SELECT 'talla', COUNT(*) FROM talla;
```

| Check | PASS |
|-------|------|
| Cada COUNT = `pre_snapshot` en evidencia | |
| `linea` con `caso_id` NOT NULL sigue existiendo si había antes | |

---

## 2. Biblioteca + diccionario intactos

```sql
SELECT COUNT(*) FROM caso_precio_biblioteca;
SELECT COUNT(*) FROM biblioteca_precio;
SELECT COUNT(*) FROM biblioteca_caso_linea;
SELECT COUNT(*) FROM caso_precio_web_regla WHERE activo;
```

| Check | PASS |
|-------|------|
| Biblioteca COUNT = pre | |
| Web reglas = 6 (o pre) | |

---

## 3. Sales Report blindado

```sql
SELECT COUNT(*) FROM registro_ventas_general_v2;
```

| Check | PASS |
|-------|------|
| COUNT = pre (ej. 104665) | |

---

## 4. Operativa en cero

```sql
SELECT 'intencion_compra' t, COUNT(*) FROM intencion_compra
UNION ALL SELECT 'pedido_proveedor', COUNT(*) FROM pedido_proveedor
UNION ALL SELECT 'precio_evento', COUNT(*) FROM precio_evento
UNION ALL SELECT 'precio_lista', COUNT(*) FROM precio_lista
UNION ALL SELECT 'factura_interna', COUNT(*) FROM factura_interna
UNION ALL SELECT 'traspaso', COUNT(*) FROM traspaso
UNION ALL SELECT 'movimiento_detalle', COUNT(*) FROM movimiento_detalle
UNION ALL SELECT 'combinacion', COUNT(*) FROM combinacion
UNION ALL SELECT 'pedido_web', COUNT(*) FROM pedido_web
UNION ALL SELECT 'pedido_venta_rimec', COUNT(*) FROM pedido_venta_rimec
UNION ALL SELECT 'compra_legal', COUNT(*) FROM compra_legal;
```

Todos **0** (o tabla omitida si no existe).

---

## 5. Depósito Web + Bazar

- Nexus Depósito Web: **0 pares**
- rimec-web: sin productos de la simulación PP-2026-0001 (catálogo vacío OK)

---

## 6. Errores que indican FAIL inmediato

- `linea` COUNT bajó → se usó CASCADE sobre biblioteca (**revertir backup**)
- `caso_precio_biblioteca` = 0 si pre > 0 → script usó `purgar_todas_las_listas`
- `registro_ventas_general_v2` cambió → **incidente grave**

---

## Veredicto

| | |
|-|-|
| **PASS** | C1–C7 evidencia + checklist |
| **FAIL** | Pegar evidencia + diff pre/post |
