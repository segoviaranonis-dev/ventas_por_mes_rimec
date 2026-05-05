# /actualizar-objetivo — Actualizar NEXUS_OBJETIVO_ACTUAL.md

Actualiza el archivo `docs/NEXUS_OBJETIVO_ACTUAL.md` con el estado real y actual del proyecto.

## Pasos obligatorios (en orden)

1. **Lee el archivo actual** en `C:\Users\hecto\.claude\projects\c--Users-hecto-Documents-Prg-locales-ventas-por-mes-rimec-main\memory\NEXUS_OBJETIVO_ACTUAL.md`

2. **Consulta el estado real de Supabase** — usa `mcp__supabase__list_tables` y
   `mcp__supabase__execute_sql` para verificar qué tablas, vistas y funciones existen realmente.
   Verifica específicamente:
   - Tablas del e-commerce: `proveedor_web`, `linea`, `referencia`, `material`, `color`, `talla`,
     `almacen`, `combinacion`, `lista_precio`, `precio`, `imagen_extra`,
     `gradacion_plantilla`, `gradacion_plantilla_detalle`,
     `movimiento`, `movimiento_detalle`, `pedido_web`, `pedido_web_detalle`
   - Vistas: `v_stock_actual`, `v_catalogo_web`, `v_ventas_pivot`
   - Función: `reservar_stock`
   - Datos iniciales: `ALM_WEB_01` en `almacen`, `MINORISTA_WEB` en `lista_precio`

3. **Consulta el estado del repositorio GitHub** — usa `mcp__github__search_repositories`
   para ver qué repos existen en `segoviaranonis-dev`.

4. **Reescribe el archivo** con estas reglas:
   - Marca con ✅ cada ítem que ya esté HECHO en producción (verificado en paso 2 y 3)
   - Marca con 🔄 los ítems en progreso
   - Marca con ⬜ los pendientes
   - Actualiza la fecha del sprint al día de hoy
   - Si una FASE entera está completa, agrégale `[COMPLETA ✅]` en el título
   - NO inventes estado — solo marca lo que verificaste con las herramientas

5. **Sección de Rigor de Base de Datos** — esta sección es PERMANENTE e INAMOVIBLE.
   Siempre debe estar presente y nunca debe debilitarse. Si no existe, agrégala:

```markdown
## Reglas de Rigor de Base de Datos (PERMANENTES)

Estas reglas NO son opcionales. Se aplican a todas las tablas, vistas y funciones
de NEXUS ERP y Bazzar Web.

### Inmutabilidad del Stock
- `movimiento_detalle` es APPEND-ONLY. Nunca UPDATE ni DELETE.
- Stock = `SUM(cantidad * signo)` WHERE movimiento.estado = 'CONFIRMADO'
- Para anular: INSERT movimiento tipo AJUSTE con signo opuesto. Nunca tocar filas viejas.

### Precios Históricos
- Tabla `precio` es APPEND-ONLY. Nunca UPDATE.
- Para cambiar precio: INSERT nuevo registro + UPDATE `fecha_hasta` del anterior.
- Un precio vigente siempre tiene `fecha_hasta IS NULL`.

### Concurrencia en Stock
- La función `reservar_stock()` es la ÚNICA puerta de salida de stock para ventas web.
- Debe ejecutarse en transacción SERIALIZABLE. Nunca descontar stock directo con SQL.
- `true` = stock OK y descontado. `false` = sin stock, avisar al cliente.

### Integridad Referencial
- NUNCA usar `ON DELETE CASCADE` en tablas de negocio (solo en tablas de detalle de imagen).
- SIEMPRE usar `ON DELETE RESTRICT` para catálogos y movimientos.
- Las combinaciones son inmutables una vez creadas. No se eliminan, se desactivan (`activo_web = false`).

### Seguridad
- RLS (Row Level Security) debe activarse ANTES de abrir la app al público (FASE 5).
- El panel `/admin` nunca debe leer directamente `movimiento_detalle` sin pasar por la vista.
- Credenciales solo en variables de entorno — nunca en código, nunca en commits.

### Nomenclatura
- Tablas ERP: sufijo `_v2` (ej: `cliente_v2`, `vendedor_v2`)
- Tablas e-commerce: sin sufijo (ej: `combinacion`, `pedido_web`)
- Vistas: prefijo `v_` (ej: `v_stock_actual`, `v_catalogo_web`, `v_ventas_pivot`)
- Funciones: verbo_sustantivo (ej: `reservar_stock`)
```

6. **Guarda el archivo** sobreescribiendo `C:\Users\hecto\.claude\projects\c--Users-hecto-Documents-Prg-locales-ventas-por-mes-rimec-main\memory\NEXUS_OBJETIVO_ACTUAL.md`.

7. Confirma con una línea: `NEXUS_OBJETIVO_ACTUAL.md actualizado — [fecha] — FASE X en curso`.
