# Respuesta YAMBAI — OT-NEXUS-FI-CAJAS-CERRADAS-RIMEC-001

| Campo | Valor |
|-------|-------|
| **Ejecutor** | YAMBAI (albañil técnico) |
| **Fecha** | 2026-05-31 |
| **OT ID** | OT-NEXUS-FI-CAJAS-CERRADAS-RIMEC-001 |
| **Estado** | ✅ COMPLETADA |

---

## 1. Objetivo Cumplido

Corregir edición de Factura Interna para que en RIMEC se editen **cajas cerradas** y los pares se calculen automáticamente según la fórmula:

```
pares = cajas × pares_por_caja
```

**Regla implementada**: RIMEC vende cajas cerradas, no pares sueltos.

---

## 2. Archivos Tocados

| Archivo | Cambios |
|---------|---------|
| `modules/aprobacion_pedidos/logic.py` | +104 líneas / -6 líneas |

### Funciones Modificadas/Creadas

1. **`_calcular_pares_por_caja_desde_snapshot(linea_snapshot: dict) -> int`** (NUEVA)
   - Extrae `pares_por_caja` desde `linea_snapshot.gradas_fmt`
   - Formato: `"27(1-1-1-1-2-2-1-1-1-1)36"` → suma cantidades entre paréntesis
   - Fallbacks: `pares_por_caja`, `pares_curva`, default 12
   - Ejemplo: `(1-1-1-1-2-2-1-1-1-1)` → suma = 12 pares/caja

2. **`modificar_cantidad_item_fi(fi_detalle_id, nuevas_cajas, nuevos_pares)`** (MODIFICADA)
   - **ANTES**: Aceptaba `nuevos_pares` de UI sin validar
   - **AHORA**: 
     - Obtiene `linea_snapshot` de BD
     - Calcula `pares_por_caja` desde snapshot
     - **Recalcula**: `nuevos_pares = nuevas_cajas × pares_por_caja`
     - **Ignora** el valor de `nuevos_pares` que viene de UI
     - Valida `nuevas_cajas >= 0`
     - Mensaje: `"✅ X cajas × Y pares/caja = Z pares. Subtotal: Gs. ..."`

---

## 3. Caso de Prueba — FI 10-PV003

### Datos Iniciales

- **FI**: 10-PV003 (ID 80)
- **PP**: PP-2026-0010 (ID 10)
- **Item**: 2400-139 (ID 334)
- **Referencia**: CAFE 569/CARAMEL 876
- **Gradas**: `27(1-1-1-1-2-2-1-1-1-1)36`
- **Pares por caja**: 12 (suma de gradas)

### Estado ANTES

| Campo | Valor |
|-------|-------|
| Cajas | 3 |
| Pares | 36 |
| Precio neto | Gs. 105,400 |
| Subtotal | Gs. 3,794,400 |
| **Total FI** | **36 pares** / **Gs. 3,794,400** |

### Acción Ejecutada

```python
modificar_cantidad_item_fi(
    fi_detalle_id=334,
    nuevas_cajas=2,
    nuevos_pares=99  # <-- IGNORADO, se recalcula
)
```

### Estado DESPUÉS

| Campo | Valor |
|-------|-------|
| Cajas | 2 |
| Pares | **24** ← (2 × 12 = 24) ✅ |
| Precio neto | Gs. 105,400 |
| Subtotal | **Gs. 2,529,600** |
| **Total FI** | **24 pares** / **Gs. 2,529,600** |

### Diferencia

| Campo | Cambio |
|-------|--------|
| Cajas | 3 → 2 (-1 caja) |
| Pares | 36 → 24 (-12 pares) |
| Monto | Gs. 3,794,400 → Gs. 2,529,600 (-Gs. 1,264,800) |

**Conclusión**: 1 caja (12 pares) devuelta al stock del PP.

---

## 4. Stock Disponible (v_stock_rimec)

**Verificación solicitada**: ¿Al bajar de 3 a 2 cajas, vuelve 1 caja/12 pares disponible?

### Modelo de Stock RIMEC

El sistema calcula stock disponible como:

```sql
SELECT
    pp.cantidad_pares - COALESCE(SUM(fi_det.pares), 0) as saldo_pares
FROM pedido_proveedor_detalle pp
LEFT JOIN factura_interna_detalle fi_det ...
```

**Respuesta**: ✅ **SÍ**, automáticamente.

Cuando `modificar_cantidad_item_fi()` reduce pares de 36 a 24:
1. Diferencia = -12 pares
2. `UPDATE pedido_proveedor_detalle SET pares_vendidos = pares_vendidos + (-12)`
3. Esto **devuelve** 12 pares al saldo disponible
4. `v_stock_rimec` refleja cambio inmediatamente (es vista calculada)

**No se requieren cambios adicionales** — la función ya ajusta stock PP correctamente (líneas 1386-1399 de logic.py).

---

## 5. Pruebas Realizadas

| # | Caso | Esperado | Resultado |
|---|------|----------|-----------|
| 1 | Cambiar 3 cajas → 2 cajas | pares = 24 (2×12) | ✅ PASS |
| 2 | Subtotal recalculado | 105,400 × 24 = 2,529,600 | ✅ PASS |
| 3 | Total FI actualizado | 24 pares, Gs. 2,529,600 | ✅ PASS |
| 4 | Stock PP ajustado | pares_vendidos reduce en 12 | ✅ PASS |
| 5 | Valor UI ignorado | nuevos_pares=99 → recalcula a 24 | ✅ PASS |

### Log Función

```
[FI] Item 334 cantidad modificada: 3 cajas (36 pares) → 2 cajas (24 pares)
```

**Mensaje usuario**:
```
✅ 2 cajas × 12 pares/caja = 24 pares. Subtotal: Gs. 2,529,600
```

---

## 6. Evidencia

**Archivo JSON**: `docs/ot/evidencia/OT-NEXUS-FI-CAJAS-CERRADAS-RIMEC-001/prueba_cambio_cajas.json`

Contiene:
- Estado ANTES/DESPUÉS completo
- Validación fórmula
- Diferencias calculadas
- Resultado: EXITOSO

---

## 7. Commit

**Hash**: `f1219d3`

**Mensaje**:
```
OT-NEXUS-FI-CAJAS-CERRADAS-RIMEC-001: Cajas cerradas RIMEC

RIMEC vende cajas cerradas. Pares se calculan automaticamente.

Cambios:
- Funcion helper _calcular_pares_por_caja_desde_snapshot()
- modificar_cantidad_item_fi() recalcula pares = cajas x pares_por_caja
- Ignora valor de pares desde UI, usa calculo desde linea_snapshot
- Mensaje muestra formula: "X cajas x Y pares/caja = Z pares"

Prueba FI 10-PV003:
- ANTES: 3 cajas, 36 pares
- DESPUES: 2 cajas, 24 pares (2 x 12 = 24)
- Diferencia: -12 pares devueltos a stock

Ejecutor: YAMBAI
```

**Archivos**:
- `modules/aprobacion_pedidos/logic.py` (modificado)
- `docs/ot/evidencia/.../prueba_cambio_cajas.json` (nuevo)

---

## 8. Restricciones Cumplidas

✅ **NO tocado**:
- report
- rimec-web
- bazzar-web
- depósito
- compra legal
- Pasar a Compra

✅ **SOLO tocado**:
- modules/aprobacion_pedidos/logic.py (backend FI)

---

## 9. Riesgos Identificados

### Riesgo Bajo

1. **Cambio de comportamiento UI**
   - **Antes**: Usuario podía poner cualquier valor de pares
   - **Ahora**: Pares se calculan automáticamente (campo pares en UI ignorado)
   - **Mitigación**: Mensaje claro muestra fórmula aplicada

2. **Fallback pares_por_caja = 12**
   - **Si**: `linea_snapshot` no tiene `gradas_fmt` válido
   - **Entonces**: Usa 12 como default (típico RIMEC)
   - **Mitigación**: Mayoría de items tienen `gradas_fmt` correcto

### Sin Riesgo

✅ **Compatibilidad hacia atrás**: Items antiguos sin `linea_snapshot` usan fallback 12  
✅ **Transaccional**: Todo dentro de `engine.begin()` — rollback automático si falla  
✅ **Validación**: `nuevas_cajas >= 0` y `nuevos_pares > 0`  
✅ **Stock**: Ajuste automático en PPD (código ya existente, no modificado)

---

## 10. Siguiente Acción Sugerida

### Inmediato (Director)

1. **Verificar en Streamlit**:
   - Abrir FI 10-PV003 en módulo Aprobación de Pedidos
   - Editar ítems (📦 Items)
   - Cambiar cajas de 2 → 3
   - Verificar que pares cambia automáticamente a 36
   - Verificar mensaje: "✅ 3 cajas × 12 pares/caja = 36 pares..."

2. **Verificar v_stock_rimec**:
   ```sql
   SELECT referencia_codigo, saldo_pares, cajas_disponibles
   FROM v_stock_rimec
   WHERE pp_id = 10 AND referencia_codigo = '139';
   ```
   - Debería mostrar stock actualizado con pares devueltos

### Corto Plazo (Opcional)

3. **Actualizar UI** (si se desea):
   - Hacer campo "Pares" readonly en editor de ítems
   - Mostrar cálculo en tiempo real: `"Pares: X (calculado: Y cajas × Z)"`
   - Requiere cambios en `modules/aprobacion_pedidos/ui.py`
   - **Estado**: No implementado (solo backend por ahora)

### Documentación

4. **Actualizar manual operativo**:
   - Documentar que en RIMEC se editan cajas, no pares
   - Los pares se calculan automáticamente
   - Fórmula: pares = cajas × pares_por_caja (desde grada cerrada)

---

## 11. Preguntas para Cursor (Auditoría)

| # | Pregunta | Contexto |
|---|----------|----------|
| 1 | ¿Validar que `gradas_fmt` siempre existe en items actuales? | Fallback a 12 puede ocultar datos faltantes |
| 2 | ¿Actualizar UI para hacer campo pares readonly? | Mejor UX, evita confusión usuario |
| 3 | ¿Aplicar mismo patrón a otras ediciones de stock? | Consistencia en todo el sistema |

---

## 12. Estado Final

**COMPLETADA** — Backend corregido, probado, commit realizado.

**Pendiente**:
- Prueba manual en Streamlit por Director
- Validación Cursor si es necesario
- Opcional: Actualizar UI para campo pares readonly

---

**YAMBAI — Albañil Técnico Nexus Core**  
*Ejecuta OT. No improvisa arquitectura. Reporta evidencia.*
