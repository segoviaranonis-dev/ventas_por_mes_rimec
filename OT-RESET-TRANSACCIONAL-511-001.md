# OT-RESET-TRANSACCIONAL-511-001 — Nueva etapa: vaciar operativa, conservar pilares + biblioteca + diccionarios

**Estado:** ✅ CERRADA (2026-05-18) — evidencia `OT-RESET-TRANSACCIONAL-511-001-EVIDENCIA.json`  
**Fecha:** 2026-05-17 · ejecutada 2026-05-18  
**Disparador:** El flujo mayo 2026 (PP→listado→FI→traspaso→Bazar) es **correcto en proceso** pero **incorrecto en contenido**. Reinicio limpio antes de la **carga final**.  
**Repos:** `ventas_por_mes_rimec-main` (Supabase) · `rimec-web` sin cambios de código salvo verificación catálogo vacío.

---

## Objetivo

Borrar **todos los datos transaccionales** de la simulación actual y dejar la BD lista para una nueva corrida end-to-end, **sin perder**:

| Capa | Conservar |
|------|-----------|
| **5 pilares** | `linea`, `referencia`, `linea_referencia`, `material`, `color`, `talla` |
| **Maestras comerciales** | `marca_v2`, `genero`, `grupo_estilo_v2`, `tipo_v2`, `categoria_v2`, `cliente_v2`, `vendedor_v2`, `plazo_v2`, `usuario_v2`, `producto_v2`, `grupo_v2`, `comision_v2`, `proveedor_importacion`, `almacen`, … |
| **Biblioteca de casos** | `biblioteca_precio`, `caso_precio_biblioteca`, `biblioteca_caso_linea` + asignaciones `linea.caso_id` |
| **Diccionario Web (OT-509)** | `caso_precio_web_regla`, función `fn_precio_venta_web` |
| **Sales Report (BLINDADO)** | `registro_ventas_general_v2` — **jamás tocar** |
| **Catálogo LPN canónico** | `listado_precio` (si existe filas — política histórica 024/027) |
| **Lista precio config** | `lista_precio` (fila config — NO truncar) |

---

## Borrar (transaccional)

### Flujo importadora

| Área | Tablas |
|------|--------|
| Intenciones | `intencion_compra_detalle` (si existe), `intencion_compra_pedido`, `intencion_compra` |
| Listados evento | `precio_auditoria`, `precio_evento_linea_excepcion`, `precio_lista`, `precio_evento_caso`, `precio_evento` |
| Pedidos proveedor | `snapshot_costos`, `pedido_proveedor_detalle`, `pedido_proveedor` |
| Facturas internas | `factura_interna_detalle`, `factura_interna` |
| Compras legales | `compra_legal_detalle`, `compra_legal_pedido`, `compra_legal` |
| Traspasos / depósito RIMEC | `traspaso_detalle`, `traspaso` |
| Movimientos (incl. **ALM_WEB_01** y depósito RIMEC) | `movimiento_detalle`, `movimiento` |
| Combinaciones derivadas | `combinacion` |
| Legacy FAC-INT | `venta_transito` |
| Auditoría flujo | `flujo_auditoria` |

### Web Bazar

| Área | Tablas |
|------|--------|
| Pedidos tienda | `pedido_web_detalle`, `pedido_web` |
| Pedidos Nexus (RPC web) | `pedido_venta_rimec` |
| Clientes web prueba | `cliente_web` (si existe y solo tiene datos de prueba) |

### Retail staging

| Área | Tablas |
|------|--------|
| Excel tiendas | `retail_multitienda_staging` |

### Legacy opcional (si existen y están vacías o son prueba)

`precio`, `linea_caso`, `listado_de_precio_v2` — truncar **solo** si `to_regclass` confirma existencia; **no** truncar `listado_precio`.

---

## Errores de la vez pasada — NO REPETIR

| Error | Migración / código | Consecuencia | Regla OT-511 |
|-------|-------------------|--------------|--------------|
| `TRUNCATE caso_precio_biblioteca CASCADE` | 039 | **Borró `linea`, `referencia`, `linea_referencia`** por FK `linea.caso_id` | **PROHIBIDO** truncar biblioteca con CASCADE |
| `DELETE FROM caso_precio_biblioteca` en reset “total” | 039/041 | Vació biblioteca que el usuario **ahora quiere conservar** | **NO borrar** `caso_precio_biblioteca` ni `biblioteca_*` |
| Reset sin desvincular IC | 039 | FK falla o datos huérfanos | **Siempre** `UPDATE intencion_compra SET precio_evento_id = NULL` y `intencion_compra_pedido` antes de truncar eventos |
| Asumir que `precio_evento` es “pilar” | 023 comentarios viejos | Confusión biblioteca vs evento | **Eventos** = transaccional · **Biblioteca** = permanente |
| Tocar `registro_ventas_general_v2` | — | Pérdida histórico ventas | **Blindado** — verificar COUNT antes/después igual |

**Patrón correcto eventos de precio** (copiar de `migrations/041_fix_reset_sin_tocar_pilares.sql` + `modules/rimec_engine/logic.py::purgar_solo_eventos_precio`):

```sql
UPDATE intencion_compra SET precio_evento_id = NULL WHERE precio_evento_id IS NOT NULL;
UPDATE intencion_compra_pedido SET precio_evento_id = NULL WHERE precio_evento_id IS NOT NULL;
-- Si existe columna:
UPDATE precio_evento SET biblioteca_precio_id = NULL WHERE biblioteca_precio_id IS NOT NULL;

TRUNCATE TABLE
  precio_auditoria,
  precio_evento_linea_excepcion,
  precio_lista,
  precio_evento_caso,
  precio_evento
RESTART IDENTITY CASCADE;
-- SIN tocar caso_precio_biblioteca / biblioteca_precio / biblioteca_caso_linea
```

**Patrón correcto operativa** (extender `migrations/023_reset_operativo_demo.sql`):

- Una sola transacción `BEGIN` … `COMMIT`
- Lista dinámica con `to_regclass` (tablas que no existen → omitir)
- `TRUNCATE … RESTART IDENTITY` **sin** incluir tablas pilar en la lista
- Post-check: COUNT pilares **idéntico** a pre-check

---

## Fase 1 — Script idempotente

Crear: `scripts/reset_transaccional_etapa_511.py`

| ID | Requisito |
|----|-----------|
| S1 | Args: `--dry-run` (solo reporte), `--execute` (requiere token `RESET-511-CONFIRMADO`) |
| S2 | **Pre-snapshot** JSON: counts de todas las tablas a borrar + pilares + `caso_precio_web_regla` + `registro_ventas_general_v2` |
| S3 | Desvincular FKs a `precio_evento` (IC, ICP, `precio_evento.biblioteca_precio_id`) |
| S4 | Truncar operativa (lista Fase 1 arriba) en orden seguro o multi-tabla atómica |
| S5 | Truncar eventos precio (lista separada, sin biblioteca) |
| S6 | **Post-snapshot** + diff; FAIL si cualquier pilar cambió COUNT |
| S7 | FAIL si `caso_precio_web_regla` ≠ count pre (esperado 6) |
| S8 | FAIL si `registro_ventas_general_v2` cambió |
| S9 | Escribir `OT-RESET-TRANSACCIONAL-511-001-EVIDENCIA.json` |

**No usar** el botón Nexus “Purgar todas las listas” (`purgar_todas_las_listas`) — borra biblioteca.

---

## Fase 2 — Migración SQL opcional (reproducible)

Crear: `migrations/049_reset_transaccional_etapa_511.sql`

- Mismo contenido que el script, para aplicar en Supabase SQL Editor si hace falta
- Comentario cabecera: referencia OT-511 y anti-patrones 039/041
- **No** incluir `DELETE FROM caso_precio_biblioteca`

---

## Fase 3 — Verificación funcional post-reset

| Pantalla Nexus | Esperado |
|----------------|----------|
| Intención compra | Sin IC activas (o solo histórico vacío) |
| Motor precios → Eventos | 0 eventos; biblioteca **intacta** |
| Diccionario Web | 6 reglas activas |
| Pedido proveedor | Sin PP |
| Facturación / FI | Sin FI |
| Compra Legal | Sin CL |
| Depósito Web | **0 pares** ALM_WEB_01 |
| Compra Web | Sin traspasos pendientes |

| rimec-web | Esperado |
|-----------|----------|
| Home Bazar | Catálogo vacío o sin stock (sin error 500) |
| `v_stock_rimec` | 0 filas con saldo o sin SKUs de la simulación vieja |

---

## Fase 4 — Documentación

| Archivo | Acción |
|---------|--------|
| `docs/OT_REGISTRO_ESTADO.md` | OT-511 PENDIENTE; OT-510 **EN PAUSA** hasta nueva carga |
| `docs/RIMEC_CONTEXTO.md` | Sección “Etapa mayo 2026 archivada — reset 511” |
| `OT-RESET-TRANSACCIONAL-511-001-EVIDENCIA.json` | Entregar al cerrar |

---

## Checks cierre (evidencia)

```json
{
  "ot_id": "OT-RESET-TRANSACCIONAL-511-001",
  "checks": [
    {"id": "C1", "pass": true, "expected": "pedido_proveedor=0, intencion_compra=0", "actual": "..."},
    {"id": "C2", "pass": true, "expected": "precio_evento=0, precio_lista=0", "actual": "..."},
    {"id": "C3", "pass": true, "expected": "movimiento_detalle=0 (depósito web y RIMEC)", "actual": "..."},
    {"id": "C4", "pass": true, "expected": "linea COUNT pre=post", "actual": "..."},
    {"id": "C5", "pass": true, "expected": "caso_precio_biblioteca COUNT pre=post", "actual": "..."},
    {"id": "C6", "pass": true, "expected": "caso_precio_web_regla=6", "actual": "..."},
    {"id": "C7", "pass": true, "expected": "registro_ventas_general_v2 sin cambio", "actual": "..."}
  ]
}
```

---

## Orden ejecución Claude Code

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main

# 1) Dry-run obligatorio primero
python scripts/reset_transaccional_etapa_511.py --dry-run

# 2) Ejecutar solo tras revisar dry-run (usuario/director autoriza)
python scripts/reset_transaccional_etapa_511.py --execute --confirm RESET-511-CONFIRMADO

# 3) Queries verificación (script las incluye o duplicar en evidencia)
```

**No pedir confirmación intermedia.** Reportar evidencia JSON + tabla pre/post counts.

**No ejecutar** en producción sin autorización explícita del director (usuario).

---

## Fuera de alcance

- Re-importar pilares Excel (siguiente OT / operación manual)
- Nueva IC / listado / PP (carga final — etapa posterior)
- OT-DEPOSITO-WEB-510-001 (columnas LPN en depósito) — **después** del reset y nueva carga
- OT-FI-CASO-508 Fase 2 — recomendado antes de la carga final, no bloqueante del reset
- Cambiar reglas `caso_precio_web_regla`
- `TRUNCATE linea` / reimport pilares

---

## Nota para auditoría Auto (post-ejecución)

Validar evidencia C1–C7, captura Depósito Web = 0 pares, Motor eventos = 0, biblioteca con filas, Diccionario Web = 6 reglas, y que `SELECT COUNT(*) FROM linea` = valor del pre-snapshot.
