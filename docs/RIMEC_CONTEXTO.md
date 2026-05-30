# RIMEC — Contexto del Proyecto
> **Rol actual:** contexto histórico/operativo de mayo 2026.  
> Para sesiones nuevas, entrar por `docs/NEXUS_CORE_INDEX.md`.
> **Norte macro:** `docs/RIMEC_MISION_VISION_POLITICA.md`
> **Memoria estratégica:** `docs/NEXUS_HOLDING_MEMORIA_ESTRATEGICA.md`
> Última actualización: **17/05/2026** — Hilo operativo PP-2026-0001 **cerrado** (traspaso + depósito + precio web Bazar)  
> **Registro OT:** `docs/OT_REGISTRO_ESTADO.md`

---

## Roles

- **Director:** dueño del negocio, valida todo, conoce las políticas.
- **Maestro de Obras (Claude conversacional):** arquitecto, diseña, ordena.
- **Albañil (Claude Code):** construye, reporta, no avanza sin validación.

---

## Protocolo de Documentos (LEY DESDE HOY)

Todos los MD viven en:
`C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main\docs\`

- El albañil actualiza `RIMEC_CONTEXTO.md` después de cada tarea
- El Director sube solo `RIMEC_CONTEXTO.md` al iniciar sesión con el Maestro
- Nunca se borran órdenes anteriores — se agregan al historial

---

## Políticas Blindadas

Ver: `docs\RIMEC_POLITICAS_BLINDADAS.md`
Aprobadas: 21/04/2026 — no se discuten, se implementan.

---

## El Negocio

Holding:
1. **Importadora RIMEC** — calzado desde Brasil. Proveedor principal: Beira Rio (código 654)
2. **Bazar Web** — tienda online del holding

Stack actual: Python + Streamlit + Supabase
Evolución post-mayo: Next.js + Supabase

---

## Hitos Críticos

- **01/05/2026** — Entrega Bazar Web. Sagrado.
- **Post 01/05** — Propuesta Next.js al cliente. Segundo contrato.

---

## Financiero

- Cobrado: USD 3.500 (50% Bazar Web)
- Pendiente: USD 3.500 (contra entrega 01/05)
- Próximo objetivo: plataforma unificada Importadora + Bazar — USD 7.500

---

## Estado de Módulos (17/05/2026)

| Módulo | Estado |
|--------|--------|
| Intención de Compra V3 | ✅ Producción |
| Pedido Proveedor | ✅ Producción — FI `1-PV001`, listado evento **#8** |
| Compra Legal / Facturación | ✅ Producción — Ley FI card, métricas unificadas |
| Traspaso → Compra Web | ✅ **44/44 pares** T-2026-0001 (OT-504–505–507) |
| Depósito Web | ✅ **44 pares** post sync movimiento (OT-506) |
| Compra Web (recepción Bazar) | ✅ Ley FI — `render_fi_card` (OT-507) |
| Rimec-Engine Motor de Precios | ✅ Producción — evento #8 CP 7447-4085x |
| Módulo Digitación | ✅ Producción |
| Bazar Web (`rimec-web`) | ✅ **precio_web** = LPN + markup por caso (OT-509, migr. 048) |
| Diccionario precio Web | ✅ Módulo **🌐 Diccionario Web** — `caso_precio_web_regla` editable |
| FI `caso` en header | ⚠️ Backfill OK (508-F1); crear FI aún sin persistir caso (508-F2) |
| Motor Forense Precios | 📋 Post-mayo |

### Caso de referencia operativo (PP-2026-0001)

- **FI:** `1-PV001` — 44 pares, `lista_precio_id=8`, caso `BR-VZ-MD-ML-MKA-O`
- **CL:** CL-2026-0001 — DISTRIBUIDA
- **Traspaso:** T-2026-0001 — snapshot + detalle alineados (incl. ref 565)

---

## Decisiones Importantes Tomadas Hoy (05/05/2026)

- **Reestructuración Facturas Internas (FI)**:
  - TRUNCATE factura_interna CASCADE (limpieza de pruebas)
  - Nueva nomenclatura: `[PP_ID]-PV[NNN]` (ej: 15-PV001, 15-PV002)
  - El correlativo PV se resetea por cada Pedido Proveedor
  - Estado inicial `RESERVADA` (soft-discount en stock en tránsito)
  - Función `revertir_stock_fi()` para ANULAR y devolver mercadería al tránsito
  - La migración 009 debe ejecutarse antes de usar el sistema

## Decisiones Anteriores

- `combinacion` vaciada en reset — se reconstruye via importación del lunes
- No restaurar backups de datos viejos — re-importación limpia es la fuente de verdad
- Ninguna tabla relacionada con Sales Report se borra jamás
- `tipo_v2` y `categoria_v2` son los "puertos" que conectan IC con Sales Report

---

## Esquema Supabase

### Blindadas — nunca tocar
| Tabla | Filas aprox | Descripción |
|-------|-------------|-------------|
| `registro_ventas_general_v2` | 104.665 | Sales Report — BLINDADO |
| `cliente_v2` | 3.135 | Cartera histórica |
| `tipo_v2` | 2 | Tipo 1=Calzados, Tipo 2=Confecciones |
| `categoria_v2` | 3 | Compra Previa / Programado / Stock |
| `marca_v2` | 15 | Maestro marcas |
| `vendedor_v2` | 20 | Maestro vendedores |
| `producto_v2` | 370 | Maestro productos |
| `grupo_v2` | 29 | Maestro grupos |
| `usuario_v2` | 5 | Usuarios del sistema |
| `linea` | 121 | Pilar 1 |
| `referencia` | 229 | Pilar 2 |
| `material` | 28.881 | Pilar 3 |
| `color` | 118 | Pilar 4 |
| `talla` | 8 | Pilar 5 — **Grada** (catálogo de talles) |
| `proveedor_importacion` | 1 | Proveedor 654 |
| `almacen` | 3 | Configuración |
| `lista_precio` | 1 | NO TOCAR |

### Motor de Precios (vaciado — listo para re-importación)
`precio_evento` · `precio_evento_caso` · `precio_evento_linea_excepcion`
`precio_lista` · `precio_auditoria` → todos en 0, secuencias reseteadas
`linea` → fuente única de verdad. Columnas: id, proveedor_id, marca_id, caso_id (FK→caso_precio_biblioteca), genero_id, descp_estilo, descp_tipo_1..4. (Tabla `linea_caso` ELIMINADA en 025.)
`generar_maestro_lineas_desde_evento()` → se ejecuta automáticamente al cerrar un evento
`caso_precio_biblioteca` → casos permanentes por proveedor (independientes de eventos)
~~`caso_precio_biblioteca_linea`~~ → ELIMINADA en 025 (la asignación caso↔línea vive en `linea.caso_id`)

### Operativas (vaciadas y reseteadas)
`intencion_compra` · `pedido_proveedor` · `pedido_proveedor_detalle`
`compra_legal` · `movimiento` · `traspaso` · `venta_transito`
`pedido_web` · `pedido_web_detalle` · `cliente_web`

---

## Arquitectura de Precios

**5 pilares:** linea · referencia · material · color · grada (`talla`). Ver `docs/RIMEC_PILARES_CINCO.md`.

**Precio:** linea + referencia + material (color/grada no cambian LPN; sí molécula de stock/venta).

**Grada importadora:** caja cerrada `35(1 2 3 3 2 1)40` · **Bazar:** N°35=1, N°36=1… vía `combinacion` + FK.

```
indice        = (dolar_politica × factor_conversion) / 100
fob_ajustado  = fob × (1-D1) × (1-D2) × (1-D3) × (1-D4)
lpn           = floor(fob_ajustado × indice / 100) × 100
lpc03         = floor(lpn × 1.12 / 100) × 100
lpc04         = floor(lpn × 1.20 / 100) × 100
```

Casos parametrizables: PROMOCIONAL · CHINELO · NORMAL · NORMAL/MENOR

### Precio venta Bazar Web (OT-509 — **en producción**)

- Tabla `caso_precio_web_regla` + función `fn_precio_venta_web`
- Vista `v_stock_rimec.precio_web` — auditoría: **268/268 SKUs** con precio
- Edición markup: Nexus → **Diccionario Web** (sin deploy)
- Doc operativo: `docs/DICCIONARIO_PRECIO_WEB.md`

---

## Identidad de Datos

- PKs propias del sistema — nunca el código del proveedor
- `codigo_proveedor` BIGINT separado en cada pilar
- UNIQUE(proveedor_id, codigo_proveedor) en pilares
- UNIQUE(proveedor_id, linea_id, codigo_proveedor) en referencia
- Un evento de precio = un solo proveedor

---

## Intención de Compra V2 — Estructura

```
intencion_compra
├── tipo_id      FK → tipo_v2      (Calzados / Confecciones)
└── categoria_id FK → categoria_v2 (Compra Previa / Programado)
```

UI: Dashboard de navegación → Paso A (Tipo + Categoría) → Paso B (flujo existente)

---

## Intención de Compra V2 — Ajustes de Trazabilidad

- Selector de Categoría muestra solo **PRE VENTA** y **PROGRAMADO** — STOCK excluido (id=1)
- `pedido_proveedor.categoria_id` — columna creada con FK a `categoria_v2(id_categoria)`
- Herencia automática: al crear PP desde IC, `save_pp()` lee y copia `categoria_id` del padre
- Regla de negocio: STOCK nace en gestión de ventas, no en intención de compra

---

## Órdenes al Albañil — Estado

Ver tabla completa: **`docs/OT_REGISTRO_ESTADO.md`**

| OT | Estado | Nota |
|----|--------|------|
| OT-TRASPASO-504-001 | ✅ CERRADA | Merge `traspaso_detalle` |
| OT-COMBINACION-505-001/002 | ✅ CERRADA | Backfill + ref 565 |
| OT-DEPOSITO-WEB-506-001 | ✅ CERRADA | Stock 44 en depósito |
| OT-COMPRA-WEB-507-001 | ✅ CERRADA | Ley FI en Compra Web |
| OT-FI-CASO-508-001 | ✅ Fase 1 / 📋 Fase 2 | Backfill caso; persistir al crear FI pendiente |
| OT-WEB-PRECIO-509-001 | ✅ CERRADA | LPN + markup % — 268 SKUs, módulo Diccionario Web |

### Histórico albañil (pre-mayo)

| Orden | Estado |
|-------|--------|
| Migración 004 / Reset / Digitación / Biblioteca casos / FI PV | ✅ Completadas |

## Arquitectura de Trazabilidad (decisión 22/04/2026)

Cada listado de precios se vincula a la Intención de Compra via `precio_evento_id`.
Esto permite el futuro **Motor Forense de Estrategia de Precios**:
- `caso` = estrategia de negocio (CARTERAS, CHINELO, NORMAL…)
- Cruce: `precio_evento_caso → IC → PP → compra → ventas → margen real`
- Pregunta gerencial: ¿qué estrategia generó más rentabilidad en qué temporada?

**Instrucción directa del Director al albañil (21/04/2026):**
> "No se detenga en `combinacion`. Avance con Bloque 2 y 3.
> La reconstrucción de combinaciones se hará via importación del lunes.
> Quiero ver el Dashboard y los selectores de Tipo y Categoría funcionando ya."

