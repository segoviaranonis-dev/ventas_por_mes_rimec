# RIMEC — Nomenclatura canónica de pilares (P0)

**Aprobado por Dirección — 2026-05-19**  
**Regla Cursor:** `.cursor/rules/rimec-nomenclatura-pilares-p0.mdc` (`alwaysApply: true`)

Un solo léxico en Nexus Core, Motor, PP, Retail, SQL y webs. Los agentes **no** inventan sinónimos.

---

## Modelo mental (lo que el Director describió)

Cada pilar tiene **exactamente tres capas**:

```text
┌─────────────────────────────────────────────────────────┐
│  id              →  ID propio Nexus (PK / FK bigint)    │
│  codigo_proveedor →  Número del proveedor (entero)      │
│  descp_*          →  Descripción legible (texto)        │
└─────────────────────────────────────────────────────────┘
```

| Pilar | Tabla | PK | Código proveedor | Descripción típica |
|-------|-------|-----|------------------|-------------------|
| Línea | `linea` | `id` | `codigo_proveedor` | nombre / atributos en `linea` / `linea_referencia` |
| Referencia | `referencia` | `id` | `codigo_proveedor` | idem |
| Material | `material` | `id` | `codigo_proveedor` | `material.descripcion` o equivalente |
| Color | `color` | `id` | `codigo_proveedor` | … |
| Grada | `talla` | `id` | `codigo_proveedor` | … |

**Triplete de precio (Motor / `precio_lista`):** `(linea_id, referencia_id, material_id)` — fuente de verdad.  
Los códigos proveedor son **copia denormalizada** para pantalla e imports, no para JOIN.

---

## Nombres canónicos (usar SIEMPRE en código nuevo)

### Foreign keys (en cualquier tabla)

```text
linea_id
referencia_id
material_id
color_id
talla_id          -- grada en negocio; tabla catálogo = talla
```

### Código numérico del proveedor

| Contexto | Nombre |
|----------|--------|
| Columna en tabla `linea`, `referencia`, … | `codigo_proveedor` |
| Copia en `precio_lista`, staging, JSON | `linea_codigo_proveedor`, `referencia_codigo_proveedor`, … |
| Parámetros Python | `linea_codigo_proveedor: int` (no `linea_cod`, `codi_linea`) |

### Descripciones

Prefijo **`descp_`** en textos de apoyo: `descp_genero`, `descp_estilo`, `descp_tipo_1`, `material_descripcion` (donde ya existe en `precio_lista` — alinear en fase 4 del OT).

### Excel / STYLE

| Columna Excel | Significado | Parseo |
|---------------|-------------|--------|
| STYLE `1184.100` | línea + referencia | `pillar_parse.parsear_linea_referencia` → `(1184, 100)` |
| Bacera A / B | línea y ref separados | enteros directos |
| Material | código material proveedor | `material.codigo_proveedor` |

---

## Legacy permitido (solo lectura — plan de salida)

| Nombre legacy | Dónde | Reemplazo objetivo |
|---------------|-------|-------------------|
| `linea_codigo`, `referencia_codigo` (text) | `v_stock_web` (legacy, mantener) | Migración **056** añade `linea_codigo_proveedor` en vista |
| `linea_code`, `referencia_code` | staging retail (antes 030) | Migración **056** renombra columnas en BD |
| `linea_codigo_proveedor` en `linea_referencia` | migración 042 | ✅ ya canónico en esa tabla |
| `linea_codigo` en JOIN incorrecto | código viejo PP | `pl.linea_id = l.id` |

**Prohibido en código nuevo:** `codigo_linea`, `codi_linea`, `id_linea`, `ref_cod`, `linea_cod` sin sufijo `_proveedor` cuando es el número del importador.

---

## Ejemplos

### SQL — bien

```sql
SELECT pl.linea_id, l.codigo_proveedor AS linea_codigo_proveedor, l.nombre
FROM precio_lista pl
JOIN linea l ON l.id = pl.linea_id
WHERE pl.evento_id = :evento_id;
```

### SQL — mal

```sql
JOIN linea l ON l.id::text = pl.linea_codigo   -- ❌ mezcla FK con texto
```

### Python — bien

```python
linea_id: int
linea_codigo_proveedor: int
_, ref_codigo_proveedor = parsear_linea_referencia(style_raw)
```

### Python — mal

```python
codigo_linea = row["codi_linea"]   # ❌
join on linea_codigo == str(l.id)  # ❌
```

---

## Normalización por fases (OT-NOMENCLATURA-PILARES-001)

| Fase | Alcance | Riesgo |
|------|---------|--------|
| 0 | Esta doc + regla P0 + memoria OT | — |
| 1 | Motor + `pillar_parse` + staging nombres en Python | Bajo |
| 2 | PP + `parse_proforma` + queries PP | Medio |
| 3 | Migración **056** (`v_stock_web` + staging retail) | Director aplica en Supabase |
| 3b | Migración `precio_lista` columnas texto | Pendiente opcional |
| 4 | Retail, scripts sueltos, RPC web | Medio |
| 5 | Auditoría grep + cierre OT | — |

**Regla de oro:** cada PR de nomenclatura toca **un módulo o una migración**, no todo el repo de golpe.

---

## Relación con otros docs

- Pilares de negocio: `RIMEC_PILARES_CINCO.md`
- Arquitectura procesos: `.cursor/rules/rimec-arquitectura-unica-verdad.mdc`
- Unificación parcial previa: migración `018_unificar_nombres_linea_estilo_genero.sql` (vistas web; incompleta en tablas operativas)
