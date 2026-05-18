# AUDIT: Pilar FK Consumers

**Fecha:** 2026-05-17  
**OT:** OT-PILAR-502-001  
**Objetivo:** Identificar desvíos entre FK canónica (pilar) y lecturas reales

---

## Matriz: Consumidores vs Fuente Canónica

### Arquitectura canónica (objetivo)

| Atributo | FK Canónica | Tabla Fuente | Descripción |
|----------|-------------|--------------|-------------|
| **Género** | `linea.genero_id` | `genero` | Admin Líneas (editable) |
| **Marca** | `linea.marca_id` | `marca_v2` | Admin Líneas (hoy solo género editable) |
| **Estilo** | `linea_referencia.grupo_estilo_id` | `grupo_estilo_v2` | Línea × Referencia (par L+R) |
| **Tipo 1** | `linea_referencia.tipo_1_id` | `tipo_1` | Línea × Referencia |

---

## I1: Consumidores actuales

### Nexus (Streamlit)

| Pantalla/Módulo | Género | Marca | Estilo | Tipo 1 | Desvío |
|-----------------|--------|-------|--------|--------|--------|
| `/estadisticas` | ❓ | ❓ | ❓ | ❓ | **A investigar** |
| `modules/pedido_proveedor/ui.py` | N/A | `ppd.id_marca` | N/A | N/A | ⚠️ Lee de ppd, no de linea |
| Admin Líneas (`pillar_fk.py`) | ✅ `linea.genero_id` | ❌ No editable | N/A | N/A | Marca no se puede editar |
| Línea × Referencia UI | N/A | N/A | ✅ `lr.grupo_estilo_id` | ✅ `lr.tipo_1_id` | ⚠️ Solo FK, no refresca descp |

### rimec-web (Next.js)

| Archivo/API | Género | Marca | Estilo | Tipo 1 | Desvío |
|-------------|--------|-------|--------|--------|--------|
| `app/page.tsx` (catálogo) | Via `getFiltros()` | Via `getFiltros()` | Via `getFiltros()` | Via `getFiltros()` | Depende de vista |
| `lib/filtros.ts` | Lee `v_stock_rimec` | Lee `v_stock_rimec` | Lee `v_stock_rimec` | Lee `v_stock_rimec` | Depende de vista |
| `lib/controlStock/fetchControl.ts` | ❓ | ⚠️ **`ppd.id_marca`** | ❓ | ❓ | **DESVÍO CRÍTICO** |
| `v_stock_rimec` (vista SQL) | Via linea? | ⚠️ **`ppd.id_marca`** | ✅ `lr.grupo_estilo_id` | ✅ `lr.tipo_1_id` | Marca desde ppd |

---

## I2: SQL caso 5835-100 (estado actual)

### Query investigación

```sql
-- 1. Datos pilar linea
SELECT l.id, l.codigo_proveedor, l.marca_id, mv.descp_marca, l.genero_id, g.descp_genero
FROM linea l
LEFT JOIN marca_v2 mv ON mv.id_marca = l.marca_id
LEFT JOIN genero g ON g.id = l.genero_id
WHERE l.codigo_proveedor::text = '5835';

-- 2. Datos pilar linea_referencia
SELECT lr.id, lr.linea_id, lr.referencia_id,
       lr.grupo_estilo_id, ge.descp_grupo_estilo, lr.descp_grupo_estilo AS lr_descp_estilo,
       lr.tipo_1_id, t1.descp_tipo_1, lr.descp_tipo_1 AS lr_descp_tipo1
FROM linea_referencia lr
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = lr.grupo_estilo_id
LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
WHERE lr.linea_id = (SELECT id FROM linea WHERE codigo_proveedor::text = '5835')
  AND lr.referencia_id = (SELECT id FROM referencia WHERE codigo_proveedor::text = '100'
                           AND linea_id = (SELECT id FROM linea WHERE codigo_proveedor::text = '5835'));

-- 3. Datos en pedido_proveedor_detalle
SELECT ppd.id, ppd.linea, ppd.referencia, ppd.id_marca, mv.descp_marca
FROM pedido_proveedor_detalle ppd
LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
WHERE ppd.linea = '5835' AND ppd.referencia = '100'
LIMIT 5;

-- 4. Vista v_stock_rimec
SELECT linea_codigo, referencia_codigo, marca_id, descp_marca,
       grupo_estilo_id, descp_grupo_estilo, tipo_1_id, descp_tipo_1
FROM v_stock_rimec
WHERE linea_codigo = '5835' AND referencia_codigo = '100'
LIMIT 1;
```

### Resultados (2026-05-17)

**Ejecutado:** `python scripts/investigar_5835_100.py`

#### Datos encontrados

**Pilar (linea):**
- linea.id: 26
- linea.codigo_proveedor: 5835
- linea.marca_id: 4 → MOLECA
- linea.genero_id: 1 → DAMAS

**Pilar (linea_referencia):**
- linea_referencia.id: 48
- linea_referencia.referencia_id: 39 (codigo: 100)
- linea_referencia.grupo_estilo_id: 30000
  - grupo_estilo_v2.descp_grupo_estilo: **TENIS** (maestro)
  - linea_referencia.descp_grupo_estilo: **BOTAS** (desactualizado)
  - !! DESVIO H2 CONFIRMADO
- linea_referencia.tipo_1_id: 2 → CERRADO (sincronizado)

**Consumidor (pedido_proveedor_detalle):**
- ppd.id: 306
- ppd.linea: 5835, ppd.referencia: 100
- ppd.id_marca: 4 → MOLECA
- ✓ Coincide con linea.marca_id (sin desvío H1 en este caso)

**Consumidor (v_stock_rimec):**
- marca_id: 4 → MOLECA
- grupo_estilo_id: 30000 → BOTAS (descp desactualizada)
- tipo_1_id: 2 → CERRADO
- ✓ Marca coincide con pilar (sin desvío H1)
- !! Estilo FK correcto pero descp obsoleta (H2)

#### Diagnóstico

**H1 (ppd.id_marca vs linea.marca_id):** Desvío arquitectónico confirmado, datos actualmente alineados
- **Código actual vista:** `ppd.id_marca::bigint AS marca_id` (línea 18 de aplicar_vista_stock_definitiva.py)
- **Debería leer:** `l.marca_id` (desde tabla linea)
- **Verificación BD (273 filas):** 0 desvíos de datos, ppd.id_marca = linea.marca_id en 100% de casos
- **Problema:** Arquitectura no respeta pilar como única verdad
- **Impacto:** Si Admin Líneas cambia marca_id → NO se refleja en web (vista lee de ppd)
- **Script verificación:** `scripts/verificar_desvio_marca_ppd_linea.py`

**H2 (descp_* desactualizada):** CONFIRMADO
- linea_referencia.descp_grupo_estilo: "BOTAS" 
- grupo_estilo_v2.descp_grupo_estilo: "TENIS"
- Vista v_stock_rimec hereda la descripción obsoleta de linea_referencia

**H3 (pilar mal cargado):** NO aplicable
- FK correctos en pilar, problema es sincronización de descripciones denormalizadas

**JSON evidencia:** `scripts/investigacion_5835_100_resultado.json`

---

## I3: Diagnóstico de desvío

### Hipótesis a verificar

1. **H1**: Pilar `linea.marca_id` correcto, pero consumidores leen `ppd.id_marca`
2. **H2**: Pilar `linea_referencia` tiene FK correcto pero `descp_*` desactualizado
3. **H3**: Pilar mal cargado (MOLECA/BOTAS incorrecto desde origen)

### Método de prueba

1. Ejecutar SQL I2 para caso 5835-100
2. Comparar:
   - `linea.marca_id` vs `ppd.id_marca`
   - `linea_referencia.descp_grupo_estilo` vs `grupo_estilo_v2.descp_grupo_estilo`
   - `v_stock_rimec.marca_id` vs `linea.marca_id`
3. Si difieren: H1 confirmada (consumidor lee mal)
4. Si `lr.descp_*` != maestras: H2 confirmada (no se refresca en UI)

---

## Conclusión Fase 1 (2026-05-17)

### Desvíos confirmados

**H1 - Arquitectónico (CRITICO):**
- v_stock_rimec lee `ppd.id_marca` en lugar de `linea.marca_id`
- Datos actualmente alineados (0 desvíos en 273 filas)
- Cambios en Admin Líneas NO se propagan a catálogo web
- **Requiere fix:** Fase 3 - W2 (reaplicar vista con l.marca_id)

**H2 - Descp desactualizada (MEDIO):**
- linea_referencia.descp_grupo_estilo: "BOTAS"
- grupo_estilo_v2.descp_grupo_estilo: "TENIS" (maestro correcto)
- v_stock_rimec hereda descripción obsoleta de lr
- **Requiere fix:** Fase 2 - R1 (sync_linea_referencia_fk)

**H3 - Pilar mal cargado:**
- NO aplicable, FK correctos en pilar

### Scripts evidencia generados

- `scripts/investigar_5835_100.py` → caso específico pilar vs consumers
- `scripts/investigar_5835_100_resultado.json` → diagnóstico JSON
- `scripts/verificar_desvio_marca_ppd_linea.py` → scan completo BD marca

---

## Desvíos identificados (resumen actualizado)

| Componente | Atributo | Lee desde | Debería leer | Impacto |
|------------|----------|-----------|--------------|---------|
| `v_stock_rimec` | Marca | `ppd.id_marca` | `linea.marca_id` | ⚠️ ALTO - afecta catálogo web y filtros |
| `fetchControl.ts` | Marca | `ppd.id_marca` | `linea.marca_id` | ⚠️ ALTO - control stock incorrecto |
| Línea×Ref UI | Estilo descp | Solo FK, no sync | `grupo_estilo_v2.descp` | ⚠️ MEDIO - descp obsoleta |
| Admin Líneas | Marca | No editable | Debe permitir editar `marca_id` | ⚠️ BAJO - workaround manual |

---

## Próximos pasos (Fase 2 y 3)

### Fase 2 - Nexus
- [ ] R1: Extraer `sync_linea_referencia_fk()` para refrescar descp desde maestras
- [ ] R2: Buscador Línea×Ref por código (5835 / 100)
- [ ] R3: Admin Líneas permitir editar marca_id
- [ ] R4: Script `verificar_pilar_propagacion.py`

### Fase 3 - Web
- [ ] W1: `fetchControl.ts` marca desde `linea.marca_id`
- [ ] W2: `v_stock_rimec` marca desde `l.marca_id` (reaplicar vista)
- [ ] W3: Catálogo/filtros alineados con vista corregida
- [ ] W4: Verificación end-to-end: cambio pilar → estadísticas sin tocar ppd

---

**Archivo:** `docs/AUDIT_PILAR_FK_CONSUMERS.md`  
**Estado:** Matriz creada, pendiente ejecución SQL I2 para completar resultados
