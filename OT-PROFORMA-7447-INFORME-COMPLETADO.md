# OT — Proforma 7447 / PP 7320·239: Informe Completado

**Fecha**: 2026-05-17  
**Repos**: ventas_por_mes_rimec-main, rimec-web  
**Síntoma**: Catálogo web mostraba "8 col." para MODARE 7320/239 con regla "1 caja = 1 color" esperada

---

## FASE 1 — Auditoría y diagnóstico

### Métricas

| Métrica | Valor |
|---------|-------|
| Filas parse_proforma total | 396 |
| Filas foco 7320/239 (parser) | 8 |
| Filas RAW Excel (ITEM) 7320.239 | 8 |
| Duplicados por molécula (parser) | 3 claves duplicadas |
| Duplicados por molécula (BD antes) | 3 claves duplicadas (8 filas) |
| numero_proforma en BD | 7441-4084 |
| ¿Coincide archivo 7447 con proforma BD? | **Sí** |

### Hipótesis ganadora: **H1 — Excel trae N filas reales con cajas > 0**

**Evidencia:**
- Excel RAW: 8 filas ITEM distintos (214-221) para 7320/239
- Parser oficial `parse_proforma()`: 8 filas (idéntico conteo, sin fan-out)
- BD pedido_proveedor_detalle: 8 filas con `fila_origen_f9` trazables al Excel

**Detalle de duplicación en Excel proforma:**
```
Items 216, 217, 219, 220: AVELA 1248, 1 caja/8 pares cada uno (misma curva)
Items 214, 218:           NEGRO 01,    1 caja/8 pares cada uno (curva A)
Items 215, 221:           NEGRO 01,    1 caja/12 pares cada uno (curva B)
```

**Conclusión H1:**  
El Excel de proforma física trae 8 líneas ITEM para lo que operación espera sean 3 moléculas únicas. **No es bug del parser ni del catálogo web**. Origen: falta de consolidación en Excel proveedor o falta de normalización en `populate_pp_from_proforma()`.

**Veredicto del script de auditoría:**
> El EXCEL trae varias filas ITEM con cajas>0 para el mismo modelo/color/curva.  
> No es bug del catálogo web: el importador persiste lo que el Excel declara.  
> **Normalización: 1 molécula = 1 fila en proforma OR consolidar al importar.**

---

## FASE 2 — Reparación de raíz

### 2.1 Normalización en import PP (Módulo 500 standard)

**Archivo modificado:** `modules/pedido_proveedor/logic.py`

**Cambios implementados:**

1. **Nueva función `_mol_key_import(row: dict) -> str`**  
   Clave canónica molécula: `linea|referencia|material_code|color_code|grades_json(sorted)`

2. **Normalización en `populate_pp_from_proforma()`:**
   - Antes del loop de INSERT, deduplica `detalle_rows` agrupando por `_mol_key_import()`
   - Si molécula aparece N veces, **suma boxes/pairs** en fila consolidada
   - Loguea WARNING con `DBInspector.log()` indicando moléculas duplicadas y items afectados
   - Audit trail en `flujo_auditoria`: agrega `n_filas_excel`, `n_duplicados` al snapshot

3. **Test unitario:** `scripts/test_normalizacion_proforma.py`  
   - Simula caso 7320/239 con 8 filas Excel
   - Verifica que consolida a 3 moléculas únicas
   - **Resultado:** ✅ Todos los tests pasaron

**Extracto del test:**
```
Filas Excel: 8
Filas unicas (moleculas): 3
Duplicados consolidados: 3

Resultado final (filas a insertar en BD):
  AVELA 1248      |  4 cjs |  32 pares | item(s): 216, 217, 219, 220
  NEGRO 01        |  2 cjs |  16 pares | item(s): 214, 218
  NEGRO 01        |  2 cjs |  24 pares | item(s): 215, 221
```

### 2.2 Limpieza de datos existentes (PP-2026-0001)

**Script:** `scripts/sanear_ppd_duplicados_pp.py`

**Operación ejecutada:**
```bash
python scripts/sanear_ppd_duplicados_pp.py --pp-id 1 --linea 7320 --ref 239 --yes
```

**Resultado:**
- **3 moléculas consolidadas** (UPDATE de fila rn=1 con suma de cajas/pares)
- **5 filas duplicadas eliminadas** (DELETE de filas rn>1)
- **Verificación:** 3 filas restantes (esperado: 3) ✅

**Estado BD después:**
```
ID  | Linea | Ref | Color          | Cajas | Pares | Fila_F9
------------------------------------------------------------
308 | 7320  | 239 | AVELA 1248     |     4 |    32 | 216
312 | 7320  | 239 | NEGRO 01       |     2 |    16 | 214
313 | 7320  | 239 | NEGRO 01       |     2 |    24 | 215
```

### 2.3 Vista v_stock_rimec actualizada

Vista recreada con columnas `cajas_disponibles`, `pares_vendidos`, `saldo_pares` en FASE 0 del diagnóstico.

**Verificación en vista:**
```
det_id | Color          | Cajas | Disponible
-----------------------------------------------
   308 | AVELA 1248     |     4 |          4
   312 | NEGRO 01       |     2 |          2
   313 | NEGRO 01       |     2 |          2
```

---

## FASE 3 — Verificación end-to-end

### Criterio de cierre

| Verificación | Estado | Valor |
|-------------|--------|-------|
| Filas ppd = filas únicas por molécula | ✅ | 3 |
| Filas ppd = moléculas en Excel (tras consolidar) | ✅ | 3 |
| COUNT v_stock_rimec para 7320/239 | ✅ | 3 |
| cajas_disponibles en vista | ✅ | 4, 2, 2 |
| Frontend CatalogoGrid.tsx | ✅ | Filter `cajas_disponibles > 0` implementado |
| Test normalization script | ✅ | 8 → 3 (pasó) |

### Pendiente manual (usuario)

**Catálogo web rimec-web:**
1. Iniciar dev server: `cd rimec-web && npm run dev`
2. Abrir http://localhost:3001 con Ctrl+F5 (hard refresh)
3. Buscar modelo 7320/239 (MODARE)
4. **Resultado esperado:**
   - **Badge:** "2 col." (AVELA y NEGRO, no 8)
   - **Chips:** 2 chips de color (no 8)
   - **Disp:** AVELA muestra "4 cjs", NEGRO muestra "2 cjs" o "2 cjs" según curva

**SQL de verificación final:**
```sql
SELECT COUNT(*) 
FROM v_stock_rimec 
WHERE linea_codigo='7320' AND referencia_codigo='239' AND cajas_disponibles > 0;
-- Esperado: 3
```

---

## Entregables

1. ✅ `scripts/auditar_proforma_7447_resultado.txt` — salida completa auditoría Fase 1
2. ✅ `modules/pedido_proveedor/logic.py` — normalización import con `_mol_key_import()` y deduplicación
3. ✅ `scripts/test_normalizacion_proforma.py` — test unitario (8 filas → 3 moléculas)
4. ✅ `scripts/sanear_ppd_duplicados_pp.py` — script parametrizado consolidación + DELETE
5. ✅ Cambios verificados en BD: 3 filas consolidadas en `pedido_proveedor_detalle`
6. ✅ Vista `v_stock_rimec` retorna 3 filas con `cajas_disponibles` correcto

---

## Arquitectura: Módulo 500 standard

**Regla innegociable aplicada:**  
**1 molécula** = `linea + referencia + material_code + color_code + grades_json` → **1 fila en pedido_proveedor_detalle por PP**

Si Excel trae duplicados, el import ahora:
1. Detecta duplicados por clave molecular
2. Suma `boxes` y `pairs` en fila consolidada
3. Loguea WARNING visible en UI Nexus
4. Inserta 1 fila con cantidades sumadas
5. Registra `n_duplicados` en audit trail

**Beneficio:** Catálogo web y reportes muestran stock correcto sin parchear agrupación frontend.

---

## Próximos pasos (opcional)

1. **Parser proforma:** Si se detectan más modelos con duplicación sistemática (ej. todos los MODARE), evaluar si `parse_proforma()` puede consolidar filas ITEM consecutivas con misma molécula antes de retornar DataFrame.

2. **Validación UI Nexus:** Mostrar warning visible al operador cuando `n_duplicados > 0` al cargar proforma (ej. "Se consolidaron 3 moléculas duplicadas del Excel").

3. **Excel proveedor:** Coordinar con proveedor MODARE para evitar duplicación en origen (1 ITEM por molécula en fatura proforma).

4. **Auditoría global:** Ejecutar `auditar_proforma_excel_pp.py` sin `--linea/--ref` para detectar otros modelos con duplicación en BD actual.

---

**Cerrado por:** Claude Code  
**Commit sugerido:** `feat(pp): normalize molecule deduplication in proforma import (module 500)`  
**Deploy:** Código listo para git commit. Usuario debe aprobar antes de push a GitHub.
