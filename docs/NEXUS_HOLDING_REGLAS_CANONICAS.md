# Nexus Holding — Reglas Canónicas

Políticas y reglas de negocio fundamentales del ecosistema Nexus.

---

## 1. Política de Clientes — Tránsito y Canales de Venta

### 1.1 Universo de Clientes RIMEC

**Mercadería en Tránsito / Compra Previa**:
- Pertenece al universo general de clientes **RIMEC**
- NO es exclusiva de un único cliente
- Disponible para venta a cualquier cliente autorizado RIMEC

### 1.2 Cliente 5000 — Bazar Web Virtual EXCLUSIVO

**Identificación**:
- `cliente_v2.id_cliente = 5000`
- Nombre: (verificar en base de datos)

**Función**:
- **Único cliente autorizado** para alimentar **Bazar Web** (tienda virtual)
- Flujo: Compra Web → Depósito Web → Bazar Web página

**Restricción**:
- Solo mercadería asignada/vendida a cliente 5000 aparece en catálogo web público
- Otros clientes RIMEC NO alimentan la tienda virtual

### 1.3 Clientes Físicos Bazzar (Tiendas Físicas)

**Clientes**:
- `2100` — Fernando Adultos
- `2900` — Fernando Niños
- `2400` — San Martin Adultos
- `2700` — San Martin Niños
- `3100` — Palma Adultos
- `3200` — Palma Niños

**Características**:
- Clientes **RIMEC** (no Bazar Web)
- Representan tiendas físicas de la red Bazzar
- **NO alimentan** la tienda virtual
- Futuro: módulo de logística / confirmación de entregas

**Restricción**:
- Mercadería asignada a estos clientes NO debe aparecer en catálogo web
- Son clientes internos para gestión de stock físico

### 1.4 Implementación Técnica

**Obligatorio**:
- Todo flujo que alimente **Bazar Web** debe filtrar `WHERE cliente_id = 5000`
- Vistas de stock web (`v_stock_web`) deben excluir otros clientes
- Movimientos a `ALM_WEB_01` deben validar cliente 5000

**Verificar**:
- `modules/compra_web/`
- `modules/deposito_web/`
- `modules/pedido_web/`
- Vistas relacionadas a stock web

---

## 2. Ley de Pilares — Todo dato externo pasa por pilares

### 2.1 Principio Fundamental

**Todo dato externo que ingresa al holding debe normalizarse por los 5 pilares antes de alimentar sistemas operativos, reportes o decisiones comerciales.**

### 2.2 Fuentes Externas

Datos que ingresan al ecosistema:
- Excel de proveedor (listados de precio)
- CSV / planillas manuales
- Proformas de proveedor
- Facturas de proveedor
- Datos del sistema viejo (legacy)
- Retail multi-tienda
- Report / ventas históricas
- Stock físico / inventarios
- Imágenes de productos

### 2.3 Los 5 Pilares

| Pilar | Tabla maestra | Descripción |
|-------|---------------|-------------|
| **Línea** | `linea` | Línea de producto del proveedor |
| **Referencia** | `referencia` | Modelo/referencia dentro de la línea |
| **Material** | `material` | Material de fabricación |
| **Color** | `color` | Color del producto |
| **Grada** | `talla` / `curva` | Gradación de tallas (curva cerrada) |

**Clave molecular única**: `linea + referencia + material + color + grada`

### 2.4 Atributos Derivados (No Pilares)

Estos atributos se obtienen **desde** los pilares, no los reemplazan:

| Atributo | Origen | Tabla |
|----------|--------|-------|
| Marca | `linea.marca_id` | `marca_v2` |
| Género | `linea.genero_id` | `genero` |
| Estilo | `linea_referencia.grupo_estilo_id` | `grupo_estilo_v2` |
| Tipo_1 | `linea_referencia.tipo_1_id` | `tipo_1` |
| Caso comercial | `precio_evento_caso.caso_id` | `caso` |

### 2.5 Regla de Filtros y Headers UI

**Prohibido**:
- Inventar headers/filtros en frontend sin origen en pilares
- Agrupar datos sin normalización molecular
- Usar nombres/códigos sin validar contra maestras
- Crear dropdown values desde texto libre

**Obligatorio**:
- Headers de tablas vienen de pilares o maestras relacionadas
- Filtros de catálogo se construyen desde pilares enriquecidos
- Agrupaciones respetan identidad molecular (5 pilares)
- Toda UI refleja única verdad de maestras

### 2.6 Aplicación en RIMEC Web

**Estadísticas** (✅ correcto):
```typescript
// Lee de tabla base, enriquece con pilares, normaliza molecularmente
molKeyFila = [pp_id, linea, referencia, material_code, color_code, grada].join('|')
normalizarFilasMolecula(filas) // Agrupa por 5 pilares
```

**Catálogo** (⚠️ requiere alineación):
```typescript
// Lee de vista, agrupa parcialmente
buildSkuId = `${lineaId}:${referenciaId}:${materialCode}` // Solo 3 pilares
// Falta color y grada en agrupación
```

**Consecuencia**: Estadísticas y Catálogo pueden divergir porque usan diferente granularidad molecular.

### 2.7 Implementación Técnica

**Funciones canónicas**:
- `lib/controlStock/buildTree.ts` → `molKeyFila()` (5 pilares)
- `lib/controlStock/buildTree.ts` → `normalizarFilasMolecula()` (agrupación molecular)
- `lib/atributosLinea.ts` → `cargarAtributosDesdePilar()` (enriquecimiento)
- `lib/atributosLinea.ts` → `enriquecerMetaConPilar()` (aplicación)

**Vista canónica**:
- `v_stock_rimec` — stock normalizado con 5 pilares + atributos derivados

**Responsabilidad**:
- Todo módulo que consuma stock DEBE usar normalización molecular
- Todo catálogo/reporte DEBE respetar identidad de 5 pilares
- Toda agrupación DEBE explicitar qué pilares conserva

### 2.8 Caso PP-2026-0012

**Problema identificado**:
- Estadísticas: 9,904 pares (agrupación molecular correcta)
- Catálogo: 8,340 pares (agrupación parcial + límite 1000 filas)

**Causas**:
1. Supabase JS limitaba a 1,000 filas (resuelto con `.range()`)
2. Catálogo agrupa por SKU (3 pilares) vs Estadísticas por molécula (5 pilares)
3. Diferentes fuentes: `v_stock_rimec` vs `pedido_proveedor_detalle`

**Fix arquitectónico pendiente**: Alinear catálogo para usar normalización molecular completa.

---

## 3. (Espacio para otras reglas canónicas)

---

**Documento**: NEXUS_HOLDING_REGLAS_CANONICAS.md  
**Última actualización**: 2026-06-01  
**OR**: OR-NEXUS-POLITICA-CLIENTE-5000-BAZAR-WEB-001
