# FIX: Límite 1000 filas Supabase JS — RIMEC Web

## Problema

**Síntoma**: Catálogo RIMEC Web muestra 8,340 pares en lugar de 9,904 pares para PP-2026-0012 con filtro "1ra Quincena de Octubre".

**Causa raíz**: Supabase JS client limita resultados a **1,000 filas por defecto**, sin importar cuántas filas existan en la base de datos.

## Investigación

### Pipeline de datos

| Etapa | Descripción | Filas/Pares |
|-------|-------------|-------------|
| BD | `v_stock_rimec` WHERE `cajas_disponibles > 0` | 1,124 filas / 52,624 pares |
| Supabase JS | Query sin `.range()` explícito | **1,000 filas / 46,096 pares** |
| Filtro quincena=19 | Solo PP-2026-0012 | 164 filas / 8,340 pares |
| **Esperado** | Todas las filas PP-2026-0012 | **195 filas / 9,904 pares** |

**Diferencia**: 31 filas / 1,564 pares faltantes

### Diagnóstico

```
[DIAG 1] rawRows: 1000 pares: 46096
[DIAG 2] activeRawRows: 1000 pares: 46096
[DIAG 3] allRows (enriquecido): 1000 pares: 46096
[DIAG 4] rows (post filtros URL): 164 pares: 8340 quincenas: [ 19 ]
```

Las primeras 1,000 filas incluyen solo 164 filas de PP-2026-0012. Las otras 31 filas quedan fuera del límite.

## Solución

**Archivo**: `rimec-web/app/page.tsx` (líneas 69-78)

**Antes**:
```typescript
const { data, error } = await supabase
  .from('v_stock_rimec')
  .select('*')
  .gt('cajas_disponibles', 0)
  .order('descp_marca')
  .order('linea_codigo')
  .order('referencia_codigo')
```

**Después**:
```typescript
const { data, error } = await supabase
  .from('v_stock_rimec')
  .select('*')
  .gt('cajas_disponibles', 0)
  .order('descp_marca')
  .order('linea_codigo')
  .order('referencia_codigo')
  .range(0, 4999)  // ← Obtener hasta 5,000 filas en lugar de 1,000
```

## Resultado esperado

- **Antes**: 8,340 pares (incompleto)
- **Después**: 9,904 pares (correcto)

## Caso específico VIZZANO + RASTRERAS

**Antes**: 0 modelos / 0 pares (descartado porque las filas estaban fuera del límite 1,000)
**Después**: 11 modelos / 660 pares (visible)

## Verificación

Para verificar en producción que el fix funcionó:

1. Acceder a RIMEC Web catálogo
2. Filtrar por "1ra Quincena de Octubre"
3. Verificar total de pares: debe ser **9,904 pares**
4. Filtrar por marca VIZZANO + estilo RASTRERAS
5. Verificar: debe mostrar **11 modelos / 660 pares**

## Notas técnicas

- Supabase JS `@supabase/supabase-js` limita a 1,000 filas por defecto para evitar cargas pesadas
- `.range(0, 4999)` permite obtener hasta 5,000 filas
- Si en el futuro se requieren más de 5,000 filas, aumentar el límite o implementar paginación
- Considerar agregar paginación server-side si el stock crece significativamente

## Archivos modificados

- `rimec-web/app/page.tsx` — Agregar `.range(0, 4999)`

## Scripts de diagnóstico creados

- `control_central/diagnostico_pipeline_rimec_web.py`
- `control_central/diagnostico_atributos_pp_2026_0012.py`
- `control_central/diagnostico_cajas_pp_2026_0012.py`
- `control_central/diagnostico_quincena_19_todos_pp.py`
- `control_central/simular_pipeline_frontend.py`

---

**Fecha**: 2026-06-01
**Investigación**: Claude Code
**Fix aplicado**: ✅ Código modificado, pendiente despliegue
