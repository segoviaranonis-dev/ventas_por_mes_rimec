---
name: NEXUS CORE - Estado Actual y Hoja de Ruta
description: Qué está construido, qué funciona, bugs conocidos, próximos módulos y decisiones de arquitectura pendientes
type: project
---

# RIMEC NEXUS — Estado al 2026-03-31

## Módulos Activos

| # | Módulo | Estado | Descripción |
|---|---|---|---|
| 1 | `home` | ✅ Activo | Landing post-login, KPIs globales |
| 2 | `sales_report` | ✅ Activo | Inteligencia de ventas — arteria principal |
| 3 | `import_data` | 🟡 Declarado | MODULE_INFO registrado, UI pendiente |
| 4 | `system_status` | 🟡 Declarado | MODULE_INFO registrado, UI pendiente |

---

## Módulo Sales Report — Capacidades Actuales

### Filtros operativos:
- Departamento (tipo) — selectbox desde tipo_v2
- Categorías — multiselect desde categoria_v2 (dinámico, TTL 1h)
- Meses — botones 1er/2do semestre + multiselect manual
- Marcas, Cadenas, Vendedores, Clientes — multiselect desde datos cargados
- Código cliente exacto — text input → filtra por codigo_cliente en BD
- Objetivo % — select_slider 0-100%
- **Todos los filtros son borradores hasta presionar EJECUTAR ORDEN**

### 5 Arterias de datos:
1. **Evolución mensual** — AgGrid con groupby Semestre, treeData
2. **Cartera crecimiento** — clientes con variación ≥ 0, treeData Cadena→Cliente→Marca
3. **Cartera riesgo** — clientes con variación < 0
4. **Cartera sin compra** — clientes con obj>0 y real=0
5. **Ranking marcas** + detalle treeData Marca→Cadena→Cliente→Vendedor
6. **Ranking vendedores** + detalle treeData Vendedor→Cadena→Cliente→Marca→Mes

### KPIs:
- Clientes activos 2026
- % Atendimiento (clientes activos / clientes con historial 2025)
- Variación global %

### Export:
- PDF individual por tabla (botón PDF en cada tabla)
- PDF batch ZIP por Marca o por Vendedor
- Estilo IMF: Navy/Gold, subtotales piano, fila TOTAL GENERAL

### Variación ∞:
- Cuando `monto_objetivo = 0` y hay venta 2026 → muestra `∞` (NaN internamente)
- Aplica tanto en filas individuales como en filas agrupadas de AgGrid
- Aplica también en PDF

---

## Vista de BD: v_ventas_pivot

```sql
-- Creada: 2026-03-30
-- Columnas: tipo, marca, cliente, codigo_cliente, vendedor, cadena,
--           mes_idx, id_categoria, categoria,
--           monto_26, monto_25, cant_26, cant_25
-- Agrupa: 8 dimensiones + mes
-- Reemplaza: query de 7 JOINs + separación de años en Python
```

---

## Refactorizaciones Aplicadas (historial decisiones)

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-03-26 | 4 bugs críticos corregidos (Piano keys, logic/ui contract, PDF params, KPI keys) | Contratos desincronizados entre sesiones de AI |
| 2026-03-27 | PDF_PALETTE centralizado en settings.py | Colores PDF y UI independientes pero desde mismo core |
| 2026-03-27 | TOTAL row en PDFs (excepto Evolución, Ranking Marcas, Ranking Vendedores) | Pedido de negocio |
| 2026-03-27 | Registry + BaseModule + navigation v2 | Escalabilidad: módulo N = 1 línea en registry.py |
| 2026-03-27 | DataSanitizer genérico con protocolo legacy | Compatibilidad + extensibilidad |
| 2026-03-27 | ThemeManager lee desde settings (PIANO_GEOMETRY_MAP) | Fuente única de verdad para colores |
| 2026-03-28 | Supabase MCP configurado | Acceso directo a BD desde Claude Code |
| 2026-03-30 | Vista v_ventas_pivot creada en Supabase | Matemáticas en BD, no en Python |
| 2026-03-30 | queries.py refactorizado (83 líneas, helper _in()) | Limpieza y patrón DRY |
| 2026-03-30 | logic.py v104: distribuidor puro | Sin matemáticas, solo groupby + _path |
| 2026-03-30 | CATEGORIA_MAP eliminado → categoria_v2 dinámica | Fuente única de verdad |
| 2026-03-30 | sidebar_fn en MODULE_INFO | Cada módulo dueño de su sidebar |
| 2026-03-30 | core/sidebar.py → dispatcher genérico 35 líneas | Core agnóstico de módulos |
| 2026-03-30 | MES_MAP/MES_NOMBRES → constants.py fuente única | Elimina redefinición en 3 archivos |
| 2026-03-30 | Tablas v1 eliminadas de Supabase (17 tablas, ~14MB) | Limpieza de BD |
| 2026-03-30 | Variación 100% → ∞ cuando base=0 | Honestidad matemática |
| 2026-03-30 | Botones semestre → solo draft, no ejecutan query | Rendimiento y RAM |
| 2026-03-31 | Diseño arquitectural Ciclo de Abastecimiento cerrado | 4 capas + 8 tablas + 2 funciones atómicas |

---

## Tablas BD — Estado Actual (2026-03-31)

### Tablas activas (v2) — ERP ventas:
```
cadena_v2, vendedor_v2, tipo_v2, categoria_v2, cliente_v2, marca_v2
cliente_cadena_v2, usuario_v2, registro_ventas_general_v2
comision_v2, vendedor_marca_v2, producto_v2, grupo_v2, grupo_estilo_v2
proveedor_v2, listado_de_precio_v2, plazo_v2
```

### Tablas activas — Bazzar e-commerce:
```
proveedor_web, linea, referencia, material, color, talla, almacen
combinacion, lista_precio, precio, imagen_extra
gradacion_plantilla, gradacion_plantilla_detalle
movimiento, movimiento_detalle
pedido_web, pedido_web_detalle
```

### Tablas a ELIMINAR (próxima migración):
```
pedido_encabezado  ← tabla instinto sin uso real, será reemplazada por ric+pedido_proveedor
pedido_detalle     ← ídem
```

### Tablas a CREAR — Ciclo Abastecimiento (diseño cerrado):
```
proveedor_importacion   ← fábricas internacionales
ric                     ← Registro de Intención de Compra
pedido_proveedor        ← proforma + bandera PROGRAMADO|COMPRA_PREVIA|STOCK
pedido_proveedor_detalle← 5 pilares + precio USD full
compra_legal            ← invoice legal + estado OBSERVADO
compra_legal_pedido     ← puente N:M
compra_legal_detalle    ← cirugía descuentos por línea + costo landed
traspaso                ← nota de remisión PDF + JSON inmutable
traspaso_detalle        ← stock inter-empresa con trazabilidad de costo
```

### Almacenes a INSERTAR:
```
ALM_TRANSITO_01      tipo='TRANSITO'
ALM_DEPOSITO_RIMEC   tipo='DEPOSITO'
```

---

## Próximos Módulos (orden de valor de negocio)

### Prioridad INMEDIATA: Bazzar FASE 2-5
Ver NEXUS_OBJETIVO_ACTUAL.md — Track A. El CSV maestro desbloquea FASE 2.

### Módulo Siguiente: Ciclo de Abastecimiento (ERP)
```
modules/abastecimiento/
    __init__.py      MODULE_INFO order=3, ADMIN only
    ui.py            Tabs: RIC | Pedido Proveedor | Compra Legal | Traspaso
    logic.py         Consultas + máquinas de estado
    sidebar.py       Filtros por estado, proveedor, período
    pdf_remision.py  ReportLab → Nota de Remisión legal
```
**Base de datos:** 8 tablas nuevas + 2 funciones atómicas (diseño cerrado).
**Desbloquea:** gestión real del ciclo importación → stock → tienda. Mata primer módulo PHP.

### Módulo 3: Gestión de Clientes
**Valor:** CRM básico — cartera, historial, deuda, última compra.
**Tablas disponibles:** cliente_v2, cliente_cadena_v2, registro_ventas_general_v2.

### Módulo 4: Comisiones de Vendedores
**Tabla disponible:** comision_v2, vendedor_marca_v2.

### Módulo 5: Inventario / Stock ERP
**Tablas disponibles:** producto_v2, grupo_v2, grupo_estilo_v2 (ERP legacy).
**Nota:** el stock real de la tienda vive en movimiento/movimiento_detalle (nuevo sistema).

---

## Deuda Técnica Conocida (no crítica)

| Archivo | Issue | Prioridad |
|---|---|---|
| settings.py | Mezcla branding + colores + schema + layout en 1 archivo | Baja |
| sales_report/ui.py | render_fragmented_grid() tiene 140+ líneas | Baja |
| sales_report/logic.py | get_full_analysis_package() tiene 200+ líneas | Baja |
| filters.py | initialize_filters() llamado en cada método estático | Baja |
| auth.py | role_map hardcodeado (DIRECTOR→ADMIN) | Media |
| Todos | Sin tests unitarios automáticos | Media |

---

## Reglas de Oro para Nuevas Sesiones

1. **Leer siempre** `NEXUS_MISION.md`, `NEXUS_ARQUITECTURA.md` y este archivo antes de proponer código
2. **Verificar contratos** logic→ui→export antes de cualquier cambio en esas capas
3. **No tocar core/** sin razón arquitectural — el core es estable
4. **Las tablas _v2 son la BD ERP**. Las tablas sin sufijo son e-commerce + ciclo importación.
5. **La vista `v_ventas_pivot` es el origen de todos los datos de ventas**
6. **Filtros → draft primero, EJECUTAR ORDEN → SQL** — nunca al revés
7. **∞ no es 100%** — respetar la honestidad matemática de la variación
8. **Cada módulo nuevo** sigue el patrón: MODULE_INFO → sidebar_fn → render_fn → _register()
9. **Todo en español** — código, comentarios, mensajes de error, logs, todo
10. **El objetivo es el PHP muerto en 24 meses** — cada decisión apunta ahí
11. **pedido_encabezado y pedido_detalle son tablas obsoletas** — no referenciarlas en código nuevo
12. **El ciclo importación es la siguiente frontera**: RIC → PP → Compra Legal → Traspaso
