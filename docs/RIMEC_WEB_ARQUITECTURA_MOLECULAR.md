# RIMEC Web — Arquitectura Molecular: Catálogo vs Estadísticas

**Fecha**: 2026-06-01  
**Contexto**: PP-2026-0012 muestra divergencia entre Catálogo (8,340 pares) y Estadísticas (9,904 pares)  
**Ley aplicable**: Ley de Pilares (NEXUS_HOLDING_REGLAS_CANONICAS.md § 2)

---

## Problema Identificado

### Síntoma
- **Estadísticas**: 9,904 pares para PP-2026-0012 con quincena 1ra Octubre
- **Catálogo**: 8,340 pares para el mismo filtro
- **Diferencia**: 1,564 pares (15.8%)
- **Caso específico**: VIZZANO + RASTRERAS muestra 0 en catálogo, pero aparece en estadísticas

### Causa Inmediata (Resuelta)
Supabase JS client limitaba resultados a 1,000 filas por defecto.
- **Fix aplicado**: `.range(0, 4999)` en `app/page.tsx` y `lib/filtros.ts`
- **Commits**: 28048fe, ede2dc4

### Causa Arquitectónica (Pendiente)
Divergencia molecular entre Catálogo y Estadísticas.

---

## Análisis Comparativo

### Estadísticas (Correcto - Normalización Molecular)

**Archivo**: `lib/controlStock/fetchControl.ts`

**Flujo**:
```
1. Lee de tabla base: pedido_proveedor_detalle
2. Enriquece con pilares:
   - linea (desde linea tabla)
   - referencia (desde referencia tabla)
   - estilo (desde linea_referencia tabla)
   - marca (desde linea.marca_id)
3. Construye clave molecular (5 pilares):
   molKeyFila = [pp_id, linea, referencia, material_code, color_code, grada].join('|')
4. Normaliza: normalizarFilasMolecula(filas)
   - Agrupa por molécula única
   - Suma inicial + vendido + saldo
5. Retorna filas normalizadas + filtros derivados
```

**Código clave**:
```typescript
// lib/controlStock/buildTree.ts
export function molKeyFila(r: DetalleStockRow): string {
  return [
    r.pp_id,
    r.linea,
    r.referencia,
    r.material_code,
    r.color_code,
    r.grada,
  ].join('|')
}

export function normalizarFilasMolecula(filas: DetalleStockRow[]): DetalleStockRow[] {
  const map = new Map<string, DetalleStockRow>()
  for (const r of filas) {
    const k = molKeyFila(r)
    const prev = map.get(k)
    if (!prev) {
      map.set(k, { ...r })
      continue
    }
    map.set(k, {
      ...prev,
      inicial: prev.inicial + r.inicial,
      vendido: prev.vendido + r.vendido,
      saldo: prev.saldo + r.saldo,
    })
  }
  return [...map.values()]
}
```

**Ventajas**:
- ✅ Respeta identidad molecular completa (5 pilares)
- ✅ Agrupa correctamente duplicados por molécula
- ✅ Enriquece desde pilares canónicos
- ✅ Fuente de verdad: tabla base + pilares

**Desventajas**:
- ⚠️ Lee de tabla base (pedido_proveedor_detalle), no de vista optimizada
- ⚠️ Enriquecimiento puede ser lento para grandes volúmenes

---

### Catálogo (Incorrecto - Agrupación Parcial)

**Archivo**: `app/page.tsx` + `lib/agruparTarjetasCatalogo.ts`

**Flujo**:
```
1. Lee de vista materializada: v_stock_rimec
2. Filtra por cajas_disponibles > 0
3. Enriquece con pilares (lib/atributosLinea.ts)
   - cargarAtributosDesdePilar()
   - enriquecerMetaConPilar()
4. Construye SKU (solo 3 pilares):
   buildSkuId = `${lineaId}:${referenciaId}:${materialCode}`
5. Agrupa tarjetas por SKU + origen
   - Variantes: agrupan colores y gradas dentro de SKU
6. Suma cantidad_pares (no normalizado molecularmente)
```

**Código clave**:
```typescript
// lib/catalogoOrigen.ts
export function buildSkuId(lineaId: number, referenciaId: number, materialCode: string): string {
  return `${lineaId}:${referenciaId}:${String(materialCode ?? '').trim()}`
}

// lib/agruparTarjetasCatalogo.ts
export function agruparTarjetasCatalogo(
  items: StockRow[],
  bucketUrl: string,
  cajasDisponiblesDeFila: (item: StockRow) => number,
): TarjetaCatalogo[] {
  const cardMap = new Map<string, TarjetaCatalogo>()
  const detIdsPorCard = new Map<string, Set<number>>()

  for (const item of items) {
    const cajasDisp = cajasDisponiblesDeFila(item)
    if (cajasDisp <= 0) continue

    const skuId = buildSkuId(item.linea_id, item.referencia_id, item.material_code)
    const origen: OrigenMetadatos = deriveOrigenFromStockRow(item)
    const cardKey = buildCardKey(skuId, origen)

    // Agrupa variantes (colores) dentro de tarjeta
    // NO normaliza por molécula completa
  }
}
```

**Ventajas**:
- ✅ Lee de vista optimizada (v_stock_rimec)
- ✅ Renderizado UI: tarjetas con variantes de color
- ✅ Enriquecimiento con atributosLinea

**Desventajas**:
- ❌ Agrupa solo por 3 pilares (falta color y grada)
- ❌ No normaliza molecularmente antes de sumar pares
- ❌ Suma cantidad_pares directamente sin normalización
- ❌ Puede contar duplicados si la vista tiene filas repetidas por molécula

---

## Divergencia Crítica

### Tabla Comparativa

| Aspecto | Estadísticas | Catálogo | Impacto |
|---------|--------------|----------|---------|
| **Fuente** | `pedido_proveedor_detalle` | `v_stock_rimec` | Diferentes bases de datos |
| **Pilares en agrupación** | 5 (linea+ref+mat+color+grada) | 3 (linea+ref+mat) | Catálogo agrupa demasiado |
| **Normalización** | ✅ `normalizarFilasMolecula()` | ❌ Suma directa | Catálogo puede duplicar |
| **Enriquecimiento** | Desde pilares canónicos | Desde `atributosLinea` | Ambos usan pilares |
| **Cálculo pares** | `inicial + vendido + saldo` | `cantidad_pares` | Catálogo ignora vendidos |
| **Resultado PP-2026-0012** | 9,904 pares ✅ | 8,340 pares ❌ | 15.8% divergencia |

### Por qué divergen

1. **Diferente granularidad molecular**:
   - Estadísticas: molécula = pp + 5 pilares (única)
   - Catálogo: SKU = 3 pilares (agrupa múltiples moléculas)

2. **Diferentes fuentes de datos**:
   - `pedido_proveedor_detalle` puede tener múltiples filas por molécula (por origen, por movimiento)
   - `v_stock_rimec` es una vista materializada que puede consolidar o filtrar

3. **Suma sin normalización**:
   - Catálogo suma `cantidad_pares` sin verificar duplicados moleculares
   - Si una molécula aparece 2 veces en v_stock_rimec, se suma 2 veces

4. **Límite Supabase (resuelto)**:
   - Antes: solo 1,000 filas llegaban al frontend
   - Ahora: hasta 5,000 filas con `.range(0, 4999)`

---

## Propuesta de Fix Definitivo

### Opción A: Alinear Catálogo con Normalización Molecular ⭐ (Recomendada)

**Objetivo**: Catálogo use la misma normalización molecular que Estadísticas.

**Cambios**:

1. **Importar funciones moleculares en catálogo**:
   ```typescript
   // app/page.tsx
   import { normalizarFilasMolecula } from '@/lib/controlStock/buildTree'
   ```

2. **Agregar campo grada a StockRow** (si no existe):
   ```typescript
   // app/page.tsx - interface StockRow
   grada: string  // Agregar este campo
   ```

3. **Normalizar antes de agrupar tarjetas**:
   ```typescript
   // app/page.tsx (después de enriquecer con pilar)
   const allRows = enriquecerMetaConPilar(activeRawRows, pilar) as StockRow[]
   
   // NUEVO: Normalizar molecularmente
   const allRowsNorm = normalizarFilasMolecula(allRows)
   
   // Aplicar filtros sobre filas normalizadas
   let rows = [...allRowsNorm]
   ```

4. **Modificar buildSkuId para incluir color y grada**:
   ```typescript
   // lib/catalogoOrigen.ts
   export function buildSkuId(
     lineaId: number,
     referenciaId: number,
     materialCode: string,
     colorCode: string,  // NUEVO
     grada: string       // NUEVO
   ): string {
     return `${lineaId}:${referenciaId}:${materialCode}:${colorCode}:${grada}`
   }
   ```

5. **Actualizar agruparTarjetasCatalogo**:
   - Usar SKU con 5 pilares
   - O bien, crear una tarjeta por molécula (sin variantes)
   - O bien, mantener variantes de color pero normalizar suma de pares

**Ventajas**:
- ✅ Catálogo y Estadísticas usan misma lógica molecular
- ✅ Elimina duplicados moleculares
- ✅ Respeta Ley de Pilares
- ✅ Fuente única de verdad

**Desventajas**:
- ⚠️ Cambio en UI: puede afectar cómo se muestran variantes
- ⚠️ Requiere testing exhaustivo de catálogo
- ⚠️ Puede cambiar cantidad de tarjetas mostradas

**Riesgo**: MEDIO - Cambio arquitectónico pero bien definido

---

### Opción B: Vista Normalizada Única

**Objetivo**: Crear una vista `v_stock_rimec_molecular` que ya esté normalizada molecularmente.

**Cambios**:

1. **Crear nueva vista en Supabase**:
   ```sql
   CREATE VIEW v_stock_rimec_molecular AS
   SELECT
     pp_id,
     linea_id, referencia_id, material_code, color_code, grada,
     linea_codigo, referencia_codigo, descp_material, descp_color,
     marca_id, descp_marca,
     grupo_estilo_id, descp_grupo_estilo,
     tipo_1_id, descp_tipo_1,
     SUM(cantidad_pares) as cantidad_pares,
     SUM(pares_vendidos) as pares_vendidos,
     SUM(saldo_pares) as saldo_pares,
     AVG(pares_por_caja) as pares_por_caja,
     SUM(cantidad_cajas) as cantidad_cajas,
     SUM(cajas_disponibles) as cajas_disponibles,
     MAX(lpn) as lpn,
     MAX(lpc02) as lpc02,
     MAX(lpc03) as lpc03,
     MAX(lpc04) as lpc04,
     STRING_AGG(DISTINCT pp_nro, ',') as pp_nros,
     STRING_AGG(DISTINCT proforma, ',') as proformas,
     MIN(quincena_arribo_id) as quincena_arribo_id,
     MIN(quincena_desc) as quincena_desc
   FROM v_stock_rimec
   GROUP BY
     pp_id, linea_id, referencia_id, material_code, color_code, grada,
     linea_codigo, referencia_codigo, descp_material, descp_color,
     marca_id, descp_marca, grupo_estilo_id, descp_grupo_estilo,
     tipo_1_id, descp_tipo_1
   HAVING SUM(cajas_disponibles) > 0
   ```

2. **Cambiar query de catálogo**:
   ```typescript
   // app/page.tsx
   const { data, error } = await supabase
     .from('v_stock_rimec_molecular')  // CAMBIO
     .select('*')
     .range(0, 4999)
   ```

3. **Estadísticas también usa la misma vista** (opcional):
   - Unifica fuente de datos
   - Ambos leen de la misma vista normalizada

**Ventajas**:
- ✅ Normalización en BD (más eficiente)
- ✅ Vista única para catálogo y estadísticas
- ✅ Menor lógica en frontend
- ✅ Fácil auditar: toda la lógica en SQL

**Desventajas**:
- ⚠️ Requiere migraciones de BD
- ⚠️ Vista materializada puede tener lag
- ⚠️ Agrupación de campos como pp_nros, proformas puede complicar UI

**Riesgo**: MEDIO-ALTO - Requiere cambios en BD y múltiples módulos

---

### Opción C: Endpoint Compartido (RPC)

**Objetivo**: Crear una función RPC que ambos (catálogo y estadísticas) llamen.

**Cambios**:

1. **Crear función en Supabase**:
   ```sql
   CREATE FUNCTION get_stock_molecular(
     p_pp_ids int[] DEFAULT NULL,
     p_quincena_id int DEFAULT NULL,
     p_marca_id int DEFAULT NULL,
     p_estilo_id int DEFAULT NULL
   ) RETURNS TABLE (...) AS $$
   BEGIN
     -- Lógica de normalización molecular en servidor
     -- Retorna filas ya normalizadas y enriquecidas
   END;
   $$ LANGUAGE plpgsql;
   ```

2. **Catálogo y Estadísticas llaman al RPC**:
   ```typescript
   const { data } = await supabase.rpc('get_stock_molecular', {
     p_quincena_id: 19,
     ...
   })
   ```

**Ventajas**:
- ✅ Máximo rendimiento (lógica en BD)
- ✅ Fuente única de verdad
- ✅ Ambos módulos usan mismo endpoint
- ✅ Fácil agregar filtros server-side

**Desventajas**:
- ⚠️ Más complejo de implementar
- ⚠️ Requiere conocimiento de PostgreSQL/plpgsql
- ⚠️ Menos flexible que lógica en frontend

**Riesgo**: ALTO - Cambio significativo en arquitectura

---

## Recomendación

**Opción A: Alinear Catálogo con Normalización Molecular**

**Razones**:
1. Reutiliza código existente y probado (`normalizarFilasMolecula`)
2. No requiere cambios en BD
3. Mantiene flexibilidad en frontend
4. Riesgo controlado con testing exhaustivo
5. Alineamiento directo con Ley de Pilares

**Plan de implementación**:
1. Auditar campos faltantes (grada) en StockRow / v_stock_rimec
2. Importar y aplicar `normalizarFilasMolecula` en catálogo
3. Modificar `buildSkuId` para usar 5 pilares (o crear nueva función)
4. Testing: verificar PP-2026-0012 muestra 9,904 en catálogo
5. Testing: VIZZANO + RASTRERAS aparece correctamente
6. Testing regresión: verificar otros PPs no se rompen

**Archivos a tocar**:
- `rimec-web/app/page.tsx` — Aplicar normalización molecular
- `rimec-web/lib/catalogoOrigen.ts` — Actualizar buildSkuId (o crear buildMolId)
- `rimec-web/lib/agruparTarjetasCatalogo.ts` — Usar clave molecular
- `rimec-web/types` — Agregar campo grada si falta

**No tocar**:
- `lib/controlStock/*` — Ya es correcto
- BD / vistas — No requiere cambios
- Estadísticas — Ya funciona correctamente

---

## Siguiente Paso

**Antes de implementar**:
1. ✅ Ley documentada en NEXUS_HOLDING_REGLAS_CANONICAS.md
2. ✅ Divergencia arquitectónica identificada
3. ✅ Propuesta de fix definida
4. ⏸️ **Esperar aprobación del Director para Opción A**
5. ⏸️ Implementar fix con testing exhaustivo
6. ⏸️ Verificar producción: 9,904 pares + VIZZANO RASTRERAS visible

---

**Fecha**: 2026-06-01  
**Autor**: Claude Code  
**Estado**: Propuesta pendiente aprobación
