# CABLE DE ACERO REFORZADO — Completar Puente End-to-End

## Estado Actual (2026-05-26)

### ✅ SEGMENTOS COMPLETADOS:

1. **Catálogo Quincena** (MIG-096)
   - Tabla `quincena_arribo` con 24 quincenas
   - Fuente única de verdad para ETAs

2. **FKs Instalados** (MIG-097)
   - `intencion_compra.quincena_arribo_id`
   - `pedido_proveedor.quincena_arribo_id`
   - `factura_interna.quincena_arribo_id`

3. **v_stock_rimec Actualizada** (MIG-098)
   - Columnas: `quincena_arribo_id`, `quincena_desc`
   - JOIN: `LEFT JOIN quincena_arribo qa ON qa.id = pp.quincena_arribo_id`
   - Vista lista para RIMEC Web

4. **Intención Compra → PP**
   - UI: Slider de quincenas (0-24)
   - Logic: Dual-field (fecha_llegada + quincena_arribo_id)
   - Propagación automática IC → PP

5. **PP UI**
   - Control inline "📦 Quincena" en listado (AFUERA)
   - Permite asignar quincena manualmente a PPs antiguos
   - Función: `update_quincena_pp(pp_id, quincena_id)`

6. **PDF Individual**
   - `pdf_factura_individual.py` YA lee quincena
   - Query líneas 88-120: JOIN con quincena_arribo
   - Campo: `qa.descripcion as quincena_llegada`

### ❌ SEGMENTOS FALTANTES:

## 1. RIMEC WEB (Crítico)

**Problema:** Tarjetas se agrupan por `eta` (fecha variable) en lugar de quincena (dato duro)

**Archivos a actualizar:**

### rimec-web/app/page.tsx
```typescript
// AGREGAR a StockRow interface (línea 11):
export interface StockRow {
  det_id: number
  pp_id: number
  pp_nro: string
  proforma: string
  eta: string | null                    // VIEJO - mantener para compatibilidad
  quincena_arribo_id: number | null     // NUEVO - dato duro
  quincena_desc: string | null          // NUEVO - descripción legible
  marca_id: number
  // ... resto de campos
}
```

### rimec-web/lib/catalogoOrigen.ts

**Cambiar función `deriveOrigenFromStockRow` (líneas 130-170):**

```typescript
export function deriveOrigenFromStockRow(row: StockOrigenRow): OrigenMetadatos {
  const tipoRaw = String(row.origen_tipo ?? '').trim().toUpperCase()

  if (tipoRaw === 'STOCK_LOCAL' || tipoRaw === 'STOCK') {
    const depId = String(row.deposito_id ?? 'RIMEC_PY').trim()
    return {
      tipo: 'STOCK_LOCAL',
      referenciaId: depId,
      label: `Stock · ${depId}`,
      shell: SHELL_STOCK_LOCAL,
    }
  }

  if (tipoRaw === 'DEPOSITO_X' || tipoRaw.startsWith('DEPOSITO')) {
    const depId = String(row.deposito_id ?? 'DEP').trim()
    return {
      tipo: 'DEPOSITO_X',
      referenciaId: depId,
      label: `Depósito ${depId}`,
      shell: SHELL_DEPOSITO_X,
    }
  }

  // CABLE DE ACERO: Priorizar quincena_desc sobre eta
  const quincenaId = row.quincena_arribo_id
  const quincenaDesc = row.quincena_desc
  const etaIso = row.eta?.slice(0, 10) ?? ''
  const ppId = row.pp_id != null ? Number(row.pp_id) : 0

  // Si hay quincena definida, usarla como referencia
  if (quincenaId && quincenaDesc) {
    // Agrupar por quincena_arribo_id (dato duro)
    return {
      tipo: 'TRÁNSITO_PP',
      referenciaId: `q:${quincenaId}`,
      label: `📦 ${quincenaDesc}`,
      shell: paletaQuincena(`${quincenaId}`), // usar ID para consistencia de color
    }
  }

  // Fallback: usar ETA si no hay quincena (PPs antiguos sin migrar)
  const referenciaId = etaIso || (ppId > 0 ? `pp:${ppId}` : 'sin-eta')
  const label = etaIso
    ? `🚢 ${etaLabelDdMm(etaIso)}`
    : row.pp_nro
      ? `PP ${row.pp_nro}`
      : ppId > 0
        ? `PP #${ppId}`
        : 'Tránsito'

  return {
    tipo: 'TRÁNSITO_PP',
    referenciaId,
    label,
    shell: etaIso ? paletaQuincena(etaIso) : PALETAS_QUINCENA[0]!,
  }
}
```

**Agregar a interface StockOrigenRow:**
```typescript
type StockOrigenRow = {
  pp_id?: number | null
  pp_nro?: string | null
  eta?: string | null
  quincena_arribo_id?: number | null     // NUEVO
  quincena_desc?: string | null          // NUEVO
  origen_tipo?: string | null
  deposito_id?: string | number | null
}
```

## 2. APROBACIÓN → FACTURA INTERNA

**Problema:** Cuando se crea FI desde célula, no copia quincena_arribo_id del PP

**Archivo:** control_central/modules/aprobacion_pedidos/logic.py

### Cambio 1: Leer quincena del PP (función `crear_preventa_desde_celula`)

**Línea 657 - Agregar quincena al query:**
```python
df = get_dataframe("""
    SELECT 
        cliente_id, vendedor_id, plazo_id, lista_precio_id,
        descuento_1, descuento_2, descuento_3, descuento_4, nro_pedido
    FROM pedido_venta_rimec WHERE id = :pid
""", {"pid": pedido_id})
```

**CAMBIAR A:**
```python
df = get_dataframe("""
    SELECT 
        pvr.cliente_id, pvr.vendedor_id, pvr.plazo_id, pvr.lista_precio_id,
        pvr.descuento_1, pvr.descuento_2, pvr.descuento_3, pvr.descuento_4, 
        pvr.nro_pedido
    FROM pedido_venta_rimec pvr WHERE pvr.id = :pid
""", {"pid": pedido_id})
```

**Línea 667 - Obtener quincena del PP ANTES de crear FI:**
```python
pp_id = _si(celula["pp_id"])
total_pares = sum(i.get("pares", 0) for i in items)
total_monto = sum(i.get("subtotal", 0) for i in items)
nro_pv = _get_next_nro_pv(pp_id)
```

**AGREGAR DESPUÉS:**
```python
# Cable de acero: leer quincena del PP para propagarla a FI
quincena_id = None
if pp_id:
    df_pp = get_dataframe("""
        SELECT quincena_arribo_id 
        FROM pedido_proveedor 
        WHERE id = :pp_id
    """, {"pp_id": pp_id})
    if df_pp is not None and not df_pp.empty:
        quincena_id = _si(df_pp.iloc[0]["quincena_arribo_id"])
```

### Cambio 2: Insertar quincena en FI

**Línea 675 - SQL INSERT:**
```python
res = conn.execute(sqlt("""
    INSERT INTO factura_interna
        (nro_factura, pp_id, marca, caso,
         cliente_id, vendedor_id, plazo_id, lista_precio_id,
         descuento_1, descuento_2, descuento_3, descuento_4,
         total_pares, total_monto, estado)
    VALUES
        (:nro, :pp_id, :marca, :caso,
         :cli, :vend, :plazo, :lista,
         :d1, :d2, :d3, :d4,
         :tp, :tn, 'RESERVADA')
    RETURNING id
"""), {
    "nro": nro_pv,
    "pp_id": pp_id,
    "marca": celula.get("marca", ""),
    "caso": celula.get("caso", "SIN_CASO"),
    ...
})
```

**CAMBIAR A:**
```python
res = conn.execute(sqlt("""
    INSERT INTO factura_interna
        (nro_factura, pp_id, marca, caso,
         cliente_id, vendedor_id, plazo_id, lista_precio_id,
         descuento_1, descuento_2, descuento_3, descuento_4,
         total_pares, total_monto, estado, quincena_arribo_id)
    VALUES
        (:nro, :pp_id, :marca, :caso,
         :cli, :vend, :plazo, :lista,
         :d1, :d2, :d3, :d4,
         :tp, :tn, 'RESERVADA', :qid)
    RETURNING id
"""), {
    "nro": nro_pv,
    "pp_id": pp_id,
    "marca": celula.get("marca", ""),
    "caso": celula.get("caso", "SIN_CASO"),
    "cli": _si(p["cliente_id"]),
    "vend": _si(p.get("vendedor_id")),
    "plazo": _si(p.get("plazo_id")),
    "lista": _si(p["lista_precio_id"]),
    "d1": float(p.get("descuento_1") or 0),
    "d2": float(p.get("descuento_2") or 0),
    "d3": float(p.get("descuento_3") or 0),
    "d4": float(p.get("descuento_4") or 0),
    "tp": total_pares, 
    "tn": total_monto,
    "qid": quincena_id,  # CABLE DE ACERO
})
```

### Cambio 3: Función `autorizar_pedido` (línea 396)

**Mismo patrón - agregar antes del try (línea 478):**
```python
# Pre-generar números PV
nros_pv_map = _generar_nros_pv_por_pp(grupos)
preventas_generadas: list[str] = []
```

**AGREGAR:**
```python
# Cable de acero: pre-cargar quincenas de cada PP
quincenas_por_pp: dict[int, int | None] = {}
for pp_id in {g["pp_id"] for g in grupos.values()}:
    df_pp = get_dataframe("""
        SELECT quincena_arribo_id 
        FROM pedido_proveedor 
        WHERE id = :pp_id
    """, {"pp_id": pp_id})
    if df_pp is not None and not df_pp.empty:
        quincenas_por_pp[pp_id] = _si(df_pp.iloc[0]["quincena_arribo_id"])
    else:
        quincenas_por_pp[pp_id] = None
```

**Línea 486 - Actualizar INSERT:**
```python
res = conn.execute(sqlt("""
    INSERT INTO factura_interna
        (nro_factura, pp_id, marca, caso,
         cliente_id, vendedor_id, plazo_id, lista_precio_id,
         descuento_1, descuento_2, descuento_3, descuento_4,
         total_pares, total_monto, estado, quincena_arribo_id)
    VALUES
        (:nro, :pp_id, :marca, :caso,
         :cli, :vend, :plazo, :lista,
         :d1, :d2, :d3, :d4,
         :tp, :tn, 'RESERVADA', :qid)
    RETURNING id
"""), {
    "nro": nro_pv,
    "pp_id": grupo["pp_id"],
    "marca": grupo["marca"],
    "caso": grupo["caso"],
    "cli": _si(pedido["cliente_id"]),
    "vend": _si(pedido.get("vendedor_id")),
    "plazo": _si(pedido.get("plazo_id")),
    "lista": _si(pedido["lista_precio_id"]),
    "d1": float(pedido.get("descuento_1") or 0),
    "d2": float(pedido.get("descuento_2") or 0),
    "d3": float(pedido.get("descuento_3") or 0),
    "d4": float(pedido.get("descuento_4") or 0),
    "tp": total_pares,
    "tn": total_neto,
    "qid": quincenas_por_pp.get(grupo["pp_id"]),  # CABLE DE ACERO
})
```

## 3. PDF FACTURA INTERNA (Multi-factura)

**Archivo:** control_central/core/pdf_factura_interna.py

**Línea 139 - Agregar a query `_obtener_facturas_del_pedido`:**

```python
query = """
    SELECT
        fi.id as fi_id,
        fi.nro_factura,
        fi.pp_id,
        pp.numero_registro as pp_nro,
        qa.descripcion as quincena_llegada,  -- AGREGAR ESTA LÍNEA
        fi.marca_id,
        fi.marca as marca_nombre,
        ...
    FROM public.factura_interna fi
    LEFT JOIN public.pedido_proveedor pp ON pp.id = fi.pp_id
    LEFT JOIN public.quincena_arribo qa ON qa.id = pp.quincena_arribo_id  -- AGREGAR JOIN
    LEFT JOIN public.factura_interna_detalle fid ON fid.factura_id = fi.id
    ...
```

**Línea 213 - Agregar quincena al dict de factura:**
```python
if fi_id not in facturas_dict:
    facturas_dict[fi_id] = {
        "fi_id": fi_id,
        "nro_factura": row["nro_factura"],
        "pp_id": int(row["pp_id"]) if row["pp_id"] else None,
        "pp_nro": row["pp_nro"] or "SIN PP",
        "quincena": row.get("quincena_llegada") or "Sin definir",  # AGREGAR
        "marca": row["marca_nombre"] or "SIN MARCA",
        "caso": row["caso_nombre"] or "SIN CASO",
        ...
    }
```

## VERIFICACIÓN POST-IMPLEMENTACIÓN

### Test 1: RIMEC Web agrupa por quincena
```bash
# En rimec-web, verificar que tarjetas con mismo quincena_arribo_id
# se agrupen bajo una misma shell visual
cd rimec-web
npm run dev
# Navegar a catálogo y verificar que PPs con misma quincena compartan color
```

### Test 2: FI hereda quincena
```python
# En control_central
python -c "
from core.database import get_dataframe
df = get_dataframe('''
    SELECT fi.id, fi.nro_factura, fi.pp_id, fi.quincena_arribo_id,
           pp.quincena_arribo_id as pp_quincena,
           qa.descripcion
    FROM factura_interna fi
    JOIN pedido_proveedor pp ON pp.id = fi.pp_id
    LEFT JOIN quincena_arribo qa ON qa.id = fi.quincena_arribo_id
    WHERE fi.created_at > NOW() - INTERVAL '1 day'
    ORDER BY fi.created_at DESC
    LIMIT 10
''')
print(df.to_string())
# Verificar que fi.quincena_arribo_id = pp.quincena_arribo_id
"
```

### Test 3: PDF muestra quincena
```python
# Generar PDF individual y verificar que aparezca quincena
from core.pdf_factura_individual import generar_pdf_fi_individual
pdf_bytes = generar_pdf_fi_individual(fi_id=123)
with open('test_quincena.pdf', 'wb') as f:
    f.write(pdf_bytes)
# Abrir PDF y verificar que muestre "📦 2da Quincena de Mayo" o similar
```

## ORDEN DE IMPLEMENTACIÓN RECOMENDADO

1. **Aprobación → FI** (crítico para nuevos datos)
   - Actualizar `crear_preventa_desde_celula`
   - Actualizar `autorizar_pedido`
   - Verificar que quincena se copie correctamente

2. **PDF Multi-factura** (para visualización interna)
   - Agregar quincena a query
   - Actualizar template para mostrar quincena

3. **RIMEC Web** (requiere deploy a Vercel)
   - Actualizar StockRow interface
   - Modificar catalogoOrigen.ts
   - Probar localmente con `npm run dev`
   - Deploy cuando esté validado

## NOTAS IMPORTANTES

- **Dual-field strategy**: Mantener `eta` junto a `quincena` hasta validación completa
- **PPs antiguos**: Sin quincena asignada → fallback a `eta` en RIMEC Web
- **Verificar Supabase**: Confirmar que vista v_stock_rimec en Supabase refleje cambios
- **NO PUSH hasta validar**: Implementar local, probar exhaustivamente, LUEGO git push

## FECHA OBJETIVO

- **Completar Aprobación + PDF**: 2026-05-26 (HOY)
- **RIMEC Web**: 2026-05-27 (después de validar FI)
- **Push a producción**: 2026-05-28 (después de pruebas integrales)
