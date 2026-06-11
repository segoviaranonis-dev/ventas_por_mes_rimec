# OT: BACKFILL PEDIDOS DESINCRONIZADOS

**Fecha:** 2026-06-10  
**Tipo:** Corrección de datos  
**Severidad:** MEDIA  
**Módulo:** Aprobación de Pedidos

---

## 🚨 PROBLEMA IDENTIFICADO

### **Desincronización entre `pedido_venta_rimec` y `factura_interna`**

**Estado actual:**
- 45 pedidos en estado `PENDIENTE`
- TODAS sus FIs están en estado `CONFIRMADA`
- Deberían estar en `CONFIRMADO`

**Impacto:**
- La pestaña "Pendientes" NO muestra estos pedidos (filtro correcto)
- Los pedidos NO aparecen en reportes de "Confirmados"
- Confusión en métricas de gestión

---

## 🔍 CAUSA RAÍZ

### **Función `_confirmar_pedido_web()` no se ejecutó**

**Ubicación:** `modules/aprobacion_pedidos/logic.py:990-996`

```python
def _confirmar_pedido_web(pedido_id: int, conn) -> None:
    """Cambia el estado del pedido_venta_rimec de PENDIENTE → CONFIRMADO."""
    conn.execute(sqlt("""
        UPDATE public.pedido_venta_rimec
        SET estado = 'CONFIRMADO'
        WHERE id = :pedido_id AND estado = 'PENDIENTE'
    """), {"pedido_id": pedido_id})
```

**Esta función se llama desde `confirmar_fi()` cuando:**
1. Se confirma una FI (RESERVADA → CONFIRMADA)
2. Se verifica que TODAS las FIs del pedido están CONFIRMADAS
3. Se debería ejecutar el UPDATE

**Hipótesis de fallo:**
1. **FIs creadas ya confirmadas:** Algunas FIs se crearon directamente en estado CONFIRMADA (bypass del flujo RESERVADA → CONFIRMADA)
2. **Fallo de transacción:** El commit falló después de confirmar FI pero antes de confirmar pedido
3. **FIs sin pedido_id:** FIs creadas antes de la migración 029 que no tenían FK formal
4. **Condición de carrera:** Múltiples FIs confirmadas en paralelo

---

## 📊 TABLAS INVOLUCRADAS

### **1. pedido_venta_rimec (Pedidos)**

**Estado actual:**
```sql
estado          | Cantidad
----------------|----------
PENDIENTE       | 46 (45 desincronizados + 1 real)
CONFIRMADO      | 16
RECHAZADO       | 1
EDITADO         | 1
Total           | 64
```

**Problema:** 45 de los 46 PENDIENTE deberían ser CONFIRMADO

### **2. factura_interna (Preventas/FIs)**

**Estado actual:**
```sql
estado          | Cantidad
----------------|----------
RESERVADA       | 1
CONFIRMADA      | 145
ANULADA         | 2
Total           | 148
```

**OK:** Estados de FI son correctos

### **3. Relación pedido ↔ FI**

```sql
-- 45 pedidos desincronizados
SELECT
    pvr.id,
    pvr.nro_pedido,
    pvr.estado AS estado_pedido,
    COUNT(fi.id) AS fis_totales,
    STRING_AGG(DISTINCT fi.estado, ', ') AS estados_fis
FROM pedido_venta_rimec pvr
JOIN factura_interna fi ON fi.pedido_id = pvr.id
WHERE pvr.estado = 'PENDIENTE'
GROUP BY pvr.id
HAVING SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) = COUNT(fi.id);
```

---

## 🛠️ SOLUCIÓN PROPUESTA

### **PASO 1: Diagnóstico**

**Script:** `scripts/diagnostico_pedidos_desincronizados.sql`

Ejecutar para:
1. Listar los 45 pedidos desincronizados
2. Verificar estados actuales
3. Identificar FIs huérfanas (si las hay)

### **PASO 2: Backfill**

**Script:** `scripts/backfill_pedidos_confirmados.sql`

```sql
-- Cambiar PENDIENTE → CONFIRMADO
-- Solo si TODAS las FIs están CONFIRMADA
UPDATE pedido_venta_rimec pvr
SET estado = 'CONFIRMADO'
FROM (
    SELECT pvr2.id
    FROM pedido_venta_rimec pvr2
    JOIN factura_interna fi ON fi.pedido_id = pvr2.id
    WHERE pvr2.estado = 'PENDIENTE'
    GROUP BY pvr2.id
    HAVING COUNT(fi.id) = SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END)
) subq
WHERE pvr.id = subq.id;
```

### **PASO 3: Prevención**

**Reforzar `confirmar_fi()` para garantizar atomicidad:**

```python
# En logic.py:confirmar_fi()
# Después de confirmar FI, SIEMPRE verificar pedido

with engine.begin() as conn:
    # 1. Confirmar FI
    conn.execute(...)
    
    # 2. Verificar pedido (CRÍTICO: dentro de la MISMA transacción)
    if pedido_id:
        todas_confirmadas = _verificar_todas_fis_confirmadas(pedido_id)
        if todas_confirmadas:
            _confirmar_pedido_web(pedido_id, conn)
            # Log explícito
            DBInspector.log(f"[PEDIDO] {pedido_id} → CONFIRMADO", "SUCCESS")
```

---

## 📋 PLAN DE EJECUCIÓN

### **Fase 1: Diagnóstico (5 min)**
```bash
# En control_central
python -c "
from core.database import get_dataframe
import pandas as pd

# Ejecutar diagnóstico
df = get_dataframe(open('scripts/diagnostico_pedidos_desincronizados.sql').read())
print(df.to_string())
"
```

### **Fase 2: Backfill (10 min)**
```bash
# Verificación primero (dry-run)
psql $DATABASE_URL -f scripts/backfill_pedidos_confirmados.sql --command="PASO 1"

# Ejecutar backfill
psql $DATABASE_URL -f scripts/backfill_pedidos_confirmados.sql --command="PASO 2"

# Verificar post-backfill
psql $DATABASE_URL -f scripts/backfill_pedidos_confirmados.sql --command="PASO 3"
```

### **Fase 3: Validación (5 min)**
```bash
# Verificar que ahora hay solo 1 PENDIENTE (el real)
psql $DATABASE_URL -c "
SELECT estado, COUNT(*) 
FROM pedido_venta_rimec 
GROUP BY estado;
"
# Debe dar:
# CONFIRMADO: 61 (16 + 45)
# PENDIENTE: 1 (el único real)
```

---

## ✅ CRITERIOS DE ÉXITO

1. ✅ Solo 1 pedido en PENDIENTE (PVR-2026-834350 con FI 8-PV024 RESERVADA)
2. ✅ 61 pedidos en CONFIRMADO (16 originales + 45 corregidos)
3. ✅ Pestaña "Confirmadas" muestra 145 FIs (sin cambio)
4. ✅ No hay pedidos huérfanos ni FIs huérfanas

---

## 🔒 SEGURIDAD

**Reversión si algo falla:**
```sql
-- Guardar backup antes de backfill
CREATE TABLE pedido_venta_rimec_backup_20260610 AS
SELECT * FROM pedido_venta_rimec
WHERE estado = 'PENDIENTE';

-- Si necesitas revertir:
UPDATE pedido_venta_rimec pvr
SET estado = 'PENDIENTE'
FROM pedido_venta_rimec_backup_20260610 bkp
WHERE pvr.id = bkp.id;
```

---

## 📈 MÉTRICAS

**Antes:**
- PENDIENTE: 46
- CONFIRMADO: 16

**Después (esperado):**
- PENDIENTE: 1
- CONFIRMADO: 61

**Diferencia:** +45 pedidos movidos a CONFIRMADO

---

## 🎯 PRÓXIMOS PASOS

1. ✅ Ejecutar diagnóstico
2. ✅ Ejecutar backfill
3. ✅ Validar resultados
4. ⏳ Reforzar `confirmar_fi()` para prevenir (opcional)
5. ⏳ Investigar logs históricos para confirmar causa raíz

---

**Estado:** ✅ COMPLETADA (2026-06-10)  
**Aprobación:** Director  
**Ejecutor:** Cursor

---

## ✅ RESULTADO DE EJECUCIÓN

**Fecha:** 2026-06-10  
**Ejecutor:** Cursor

### **Métricas finales:**

**Pedidos corregidos:** 45  
**Tokens:** ~12k  
**Estado:** OK

### **Antes:**
- PENDIENTE: 46
- CONFIRMADO: 16

### **Después:**
- PENDIENTE: 1 (solo PVR-2026-834350 con FI 8-PV024 RESERVADA)
- CONFIRMADO: 61 (16 + 45)

### **Verificación:**
- ✅ Pedidos desincronizados restantes: 0
- ✅ Integridad entre tablas restaurada
- ✅ Métricas de gestión correctas

---

**OT CERRADA:** ✅
