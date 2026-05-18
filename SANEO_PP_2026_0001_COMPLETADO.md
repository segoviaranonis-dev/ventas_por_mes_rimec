# Saneo PP-2026-0001 — Completado

**Fecha**: 2026-05-17  
**Operación**: Consolidación de moléculas duplicadas (Módulo 500 standard)  
**Script**: `scripts/sanear_ppd_duplicados_pp.py`

---

## Resumen ejecutivo

**Antes:**
- 391 filas en `pedido_proveedor_detalle`
- 91 moléculas duplicadas (209 filas involucradas)
- 118 filas con rn>1 (duplicados a eliminar)

**Después:**
- **273 filas únicas** (1 molécula = 1 fila)
- **0 duplicados** verificado con `listar_pps_con_duplicados.py`
- **748 cajas totales** (cantidades consolidadas)
- **7,164 pares totales** (coincide con parse_proforma original)

---

## Operación ejecutada

### Comando
```bash
python scripts/sanear_ppd_duplicados_pp.py --pp-id 1 --yes
```

### Proceso
1. **PREVIEW** (rn calculation):
   - 391 filas totales
   - 273 filas únicas (rn=1)
   - 118 filas duplicadas (rn>1)

2. **UPDATE** (consolidación):
   - 91 moléculas con duplicados
   - UPDATE de fila rn=1 con suma de `cantidad_cajas` y `cantidad_pares`
   - Ejemplo: id=308 (7320/239 AVELA) → 4 cajas (antes 1)

3. **DELETE** (limpieza):
   - 118 filas eliminadas (todas las rn>1)
   - Verificación: COUNT = 273 (esperado: 273) ✅

---

## Verificación final

### Base de datos
```sql
SELECT COUNT(*) as total,
       SUM(cantidad_cajas) as cajas,
       SUM(cantidad_pares) as pares
FROM pedido_proveedor_detalle
WHERE pedido_proveedor_id = 1;

-- Resultado:
-- total: 273
-- cajas: 748
-- pares: 7,164
```

### Vista v_stock_rimec
```sql
SELECT COUNT(*) FROM v_stock_rimec WHERE pp_id = 1;
-- Resultado: 273 filas
```

### Script de verificación
```bash
python scripts/listar_pps_con_duplicados.py
# Resultado: Total PP afectados: 0
# [OK] No hay PP con duplicados
```

---

## Impacto en catálogo web (rimec-web)

**Antes del saneo:**
- Ejemplo 7320/239: mostraba "8 col." (8 chips)
- Otros modelos: similar duplicación visual

**Después del saneo:**
- 7320/239: debe mostrar "2 col." (AVELA + NEGRO)
- 1214/1073: ajustado de 5 filas → 2 moléculas únicas
- 1214/1075: ajustado de 6 filas → 2 moléculas únicas
- etc. (91 modelos afectados)

**Verificación pendiente:**
1. Reiniciar `rimec-web` dev server
2. Hard refresh (Ctrl+F5) en http://localhost:3001
3. Verificar modelos clave:
   - 7320/239: badge "2 col."
   - 1214/1073: verificar chips correctos
   - 5287/210: verificar consolidación

---

## Arquitectura aplicada

**Módulo 500 standard:**  
1 molécula = `linea + referencia + material_code + color_code + grades_json` → 1 fila ppd

**Normalización automática en import:**  
- Implementada en `modules/pedido_proveedor/logic.py`
- Función `_mol_key_import()` + deduplicación en `populate_pp_from_proforma()`
- Futuros imports: automáticamente consolidados

**Datos históricos:**  
- PP-2026-0001: saneado ✅
- PP en estado COMPRADO/CERRADO: no modificados (datos históricos intactos)

---

## Próximos pasos

1. **Catálogo web**: Verificar visualmente que chips/badge reflejan moléculas reales
2. **Monitoreo**: En próximos imports de proforma, verificar logs de Nexus:
   - Si aparece warning "N moléculas consolidadas" → Excel trae duplicados
   - Coordinar con proveedor para evitar duplicación en origen
3. **Auditoría global**: Si se importan más PP, ejecutar:
   ```bash
   python scripts/listar_pps_con_duplicados.py
   ```
   Para detectar nuevos duplicados temprano

---

## Archivos generados

1. `scripts/sanear_ppd_duplicados_pp.py` — script parametrizado consolidación + DELETE
2. `scripts/listar_pps_con_duplicados.py` — detector de PP con moléculas duplicadas
3. `SANEO_PP_2026_0001_COMPLETADO.md` — este informe
4. `OT-PROFORMA-7447-INFORME-COMPLETADO.md` — informe original diagnóstico 7320/239

---

**Estado**: ✅ COMPLETADO  
**Siguiente acción**: Verificar catálogo web en http://localhost:3001  
**Commit sugerido**: `fix(pp): consolidate all duplicate molecules in PP-2026-0001 (273 unique molecules)`
