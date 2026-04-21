# ORDEN DEFINITIVA — RIMEC-ENGINE: Gestión de Eventos de Precio
**Para:** Agente Claude Code (albañil del proyecto)
**De:** Dirección del Proyecto
**Prioridad:** Absoluta. No hay otras tareas activas.

> **NOTA DE ESTADO (21/04/2026):** Migración ejecutada. Módulo construido y en validación.
> Este documento es la especificación de referencia. Lo implementado puede diferir en detalles de UX
> que el Director fue ajustando en sesión. Ver `RIMEC_CONTEXTO.md` para el estado actual real.

---

## FILOSOFÍA QUE DEBÉS INTERNALIZAR

> "El sistema no dicta las reglas. El sistema provee el lienzo y los pinceles para que el Director pinte la estrategia de precios de cada pedido, asegurándose de que cada cuadro quede colgado en la galería de forma inalterable para su análisis futuro."

El Director conoce el negocio. Vos construís la herramienta. Nunca guíes el proceso, nunca supongas que algo está bien porque el código corre. Está bien cuando el Director lo valida.

**Enfoque exclusivo de esta fase:** importar el archivo del proveedor, ejecutar el motor de cálculo, almacenar los resultados, y presentarlos al Director para validación. Nada de web, nada de `v_stock_web`, nada de `precio` existente.

---

## PASO 1 — MIGRACIÓN `migrations/002_create_rimec_engine.sql` ✅

### Tabla `precio_evento`
Registra cada ejecución como un evento único e inmutable.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | bigint PK | |
| `nombre_evento` | text NOT NULL | Nombre libre. Por defecto: nombre del archivo Excel |
| `nombre_archivo` | text NOT NULL | Nombre exacto del archivo cargado |
| `fecha_evento` | timestamptz NOT NULL | `now()` |
| `fecha_vigencia_desde` | date NOT NULL | Desde cuándo rigen estos precios |
| `fecha_vigencia_hasta` | date NULL | Null = vigente actualmente |
| `usuario_id` | bigint NULL | FK → tabla de usuarios del proyecto |
| `estado` | text NOT NULL | `'borrador'` / `'validado'` / `'cerrado'` — default `'borrador'` |
| `created_at` | timestamptz NOT NULL | `now()` |

### Tabla `precio_evento_caso`
Cada caso que el Director define para un evento. Un evento tiene N casos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | bigint PK | |
| `evento_id` | bigint NOT NULL | FK → `precio_evento` |
| `nombre_caso` | text NOT NULL | Ej: `'NORMAL'`, `'CHINELO'`, `'PROMOCIONAL'` |
| `dolar_politica` | numeric NOT NULL | Dólar de referencia para este caso |
| `factor_conversion` | numeric NOT NULL | Factor multiplicador (se guarda como ingresado, ej: 160) |
| `indice_calculado` | numeric NOT NULL | `(dolar_politica × factor_conversion) / 100` — GENERATED STORED |
| `descuento_1..4` | numeric NULL | Fracción (0.18 = 18%). Null = no aplica |
| `genera_lpc03_lpc04` | boolean NOT NULL | true = genera derivados +12% y +20% |
| `regla_redondeo` | text NOT NULL | `'centena'` por defecto |
| `marcas` | text[] NULL | Array de marcas. Null = aplica a líneas específicas |
| `created_at` | timestamptz NOT NULL | `now()` |

### Tabla `precio_evento_linea_excepcion`
Líneas específicas asignadas a un caso (cuando el caso no aplica por marca sino por línea).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | bigint PK | |
| `caso_id` | bigint NOT NULL | FK → `precio_evento_caso` |
| `linea_id` | bigint NOT NULL | FK → `linea` |

### Tabla `precio_lista`
Resultado final calculado. Una fila por SKU por evento.

> **Implementación real:** usa columnas de texto (`linea_codigo`, `referencia_codigo`, `material_descripcion`)
> en lugar de FKs numéricas para evitar inserciones en maestros durante el cálculo.
> JOIN a descripciones se hace en lectura.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | bigint PK | |
| `evento_id` | bigint NOT NULL | FK → `precio_evento` |
| `caso_id` | bigint NOT NULL | FK → `precio_evento_caso` |
| `marca` | text NOT NULL | Nombre de la marca (hoja del Excel) |
| `linea_codigo` | text NOT NULL | Código de línea como texto |
| `referencia_codigo` | text NOT NULL | Código de referencia como texto |
| `material_descripcion` | text NOT NULL | Código de material (JOIN a `material.codigo` en lectura) |
| `fob_fabrica` | numeric NOT NULL | FOB original del Excel — nunca modificar |
| `fob_ajustado` | numeric NOT NULL | FOB después de aplicar descuentos en cascada |
| `lpn` | numeric NOT NULL | Precio lista nominal (redondeado a centena inferior) |
| `lpc02` | numeric NULL | Reservado — NULL por ahora |
| `lpc03` | numeric NULL | LPN × 1.12 redondeado |
| `lpc04` | numeric NULL | LPN × 1.20 redondeado |
| `vigente` | boolean NOT NULL | `true` = precio activo actualmente |
| `created_at` | timestamptz NOT NULL | `now()` |

### Tabla `precio_auditoria`
Log inmutable de modificaciones a eventos ya iniciados.

---

## PASO 2 — MÓDULO `modules/rimec_engine/`

### Paso 0 — Carga e inicialización
1. Usuario sube `.xls`, escribe nombre del evento
2. Sistema lee hojas (marca = nombre de pestaña), detecta marcas y SKUs totales
3. Crea `precio_evento` con estado `borrador`
4. Muestra resumen: marcas detectadas, total SKUs, nombre archivo

### Paso 1 — Memoria del evento anterior
1. Consulta el último evento `cerrado`
2. Presenta sus casos al Director
3. Director puede: usar como plantilla, modificar, o empezar desde cero

### Paso 2 — Configuración de casos
Para cada caso, el Director define:
- Nombre (libre)
- Dólar de política (entero, ej: 7500)
- Factor de conversión (entero, ej: 160) — UI muestra: `7500 × 160 / 100 = 12.000 Gs por USD de FOB`
- Descuentos D1..D4 (en %, UI convierte a fracción al guardar)
- ¿Genera LPC03/LPC04? (toggle)
- Alcance: por marcas (multiselect, excluye ya asignadas) o por líneas (input separado por comas)

El sistema valida que no queden SKUs sin cubrir antes de avanzar.

### Paso 3 — Preview y cálculo
- Muestra tabla preview con ≥5 SKUs representativos
- Director revisa, ajusta si algo no cuadra, y confirma
- Al confirmar: procesa todos los SKUs del caso, guarda en `precio_lista` (bulk INSERT)
- Ese caso queda cerrado — no se reasigna

### Paso 4 — Validación final
- Validación: `len(casos_confirmados) == len(casos_definidos)` (no comparar conteos de SKUs)
- Muestra resumen por caso con cantidad de SKUs confirmados
- Habilita "Validar evento" solo cuando todos los casos están confirmados

### Paso 5 — Cierre del evento
Al hacer clic "Cerrar y activar precios":
1. Estado → `cerrado`
2. `vigente = false` en todos los registros del evento anterior
3. `vigente = true` en todos los del evento nuevo
4. `fecha_vigencia_hasta` del evento anterior = hoy

### Vista de historial (siempre accesible)
- Lista todos los eventos: nombre, fecha, estado, total SKUs
- Eventos no-cerrados: botón 🗑️ para eliminar (cascade delete explícito)
- Eventos cerrados: botón 📦 para generar ZIP de PDFs
  - Un PDF por cada combinación (caso × marca × tipo_precio)
  - Modo "listado": portrait A4, columnas auto-fit al contenido, sin subtotales

---

## MOTOR DE CÁLCULO — IMPLEMENTACIÓN EXACTA

```python
indice = (dolar_politica × factor_conversion) / 100

fob_ajustado = fob_fabrica
if descuento_1: fob_ajustado = fob_ajustado × (1 - descuento_1)
if descuento_2: fob_ajustado = fob_ajustado × (1 - descuento_2)
if descuento_3: fob_ajustado = fob_ajustado × (1 - descuento_3)
if descuento_4: fob_ajustado = fob_ajustado × (1 - descuento_4)

lpn_raw = fob_ajustado × indice
lpn = floor(lpn_raw / 100) × 100

if genera_lpc03_lpc04:
    lpc03 = floor(lpn × 1.12 / 100) × 100
    lpc04 = floor(lpn × 1.20 / 100) × 100
else:
    lpc03 = NULL
    lpc04 = NULL
```

**Nota:** Precios en PYG (guaraníes). FOB en USD. El índice ya incorpora la conversión.

---

## REGLAS QUE NO SE NEGOCIAN

1. No hardcodear nombres de casos, dólares, ni factores en el código
2. No borrar registros históricos de `precio_lista` — solo `vigente = false`
3. No calcular precios en tiempo de consulta — se calculan una vez y se almacenan
4. No habilitar el cierre si hay SKUs sin precio
5. No tocar `combinacion`, `precio` (tabla existente), ni `lista_precio`
6. No avanzar al siguiente módulo — esperar instrucciones del Director

---

## CÓMO REPORTÁS

Cuando termines la migración: mostrar SQL ejecutado + confirmar que las 5 tablas existen en Supabase.

Cuando termines el módulo: no lo des por bueno. Presentalo al Director para que lo opere. Él valida. Vos ajustás.

---

*Fin de la orden.*
