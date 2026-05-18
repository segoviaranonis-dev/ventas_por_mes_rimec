# OT-DEPOSITO-WEB-506-001 — Depósito Web 36→44 + prevención material vacío

**Estado:** ✅ CERRADA (2026-05-17) — evidencia `OT-DEPOSITO-WEB-506-001-EVIDENCIA.json`  
**Fecha:** 2026-05-17  
**Depende de:** OT-COMBINACION-505-002 (traspaso_detalle = 44 pares OK)  
**Disparador:** UI Depósito Web muestra **36 pares / 3 artículos**; BD `traspaso_detalle` tiene **44 pares / 19 filas**

## Síntoma (captura usuario)

- **ACTVITTA:** 36 pares, 3 artículos (solo ref **500**).
- **Faltan:** 4202-**565** CAMEL 1528 → **8 pares** (5 tallas).
- Coincide con ingreso a depósito hecho **antes** de rehidratar los 8 pares de ref 565.

## Causa raíz

| Capa | Estado |
|------|--------|
| `traspaso_detalle` | **44** pares (post OT-505-002) |
| `movimiento` + `movimiento_detalle` | **~36** pares (ingreso `procesar_ingreso_bazar` cuando detalle tenía 14 filas) |
| `modules/deposito_web/logic.py` | Lee stock desde **`movimiento_detalle`**, no desde `traspaso_detalle` |

**Conclusión:** Desalineación traspaso vs movimiento. No es bug de vista; falta **delta de stock** en almacén web.

---

## Objetivo

1. Auditar brecha `traspaso_detalle` ↔ `movimiento_detalle` para T-2026-0001.
2. Insertar líneas faltantes en `movimiento_detalle` (8 pares, comb_id 468–472 o los que correspondan).
3. Verificar Depósito Web = **44 pares**, **4 artículos** (incluye ref 565).
4. Implementar prevención P1–P3 (material vacío en snapshot / PPD).

---

## Fase 1 — Investigación

| ID | Tarea | Entregable |
|----|--------|------------|
| I1 | Crear `scripts/auditar_stock_traspaso_vs_movimiento.py --traspaso-id 2` | JSON con pares en TD, pares en MD, delta por `combinacion_id` |
| I2 | Query manual: `traspaso.estado`, `movimiento.documento_ref = T-2026-0001`, COUNT MD | Incluir en evidencia |

**Query referencia:**

```sql
-- Pares por fuente
SELECT 'traspaso_detalle' AS src, COALESCE(SUM(cantidad),0) AS pares
FROM traspaso_detalle WHERE traspaso_id = 2
UNION ALL
SELECT 'movimiento_detalle', COALESCE(SUM(md.cantidad*md.signo),0)
FROM movimiento_detalle md
JOIN movimiento m ON m.id = md.movimiento_id
WHERE m.documento_ref = 'T-2026-0001' AND m.tipo = 'INGRESO_COMPRA';

-- Faltantes en movimiento (esperado: 5 filas / 8 pares ref 565)
SELECT td.combinacion_id, td.cantidad AS qty_td,
       COALESCE(SUM(md.cantidad*md.signo),0) AS qty_md
FROM traspaso_detalle td
LEFT JOIN movimiento_detalle md ON md.combinacion_id = td.combinacion_id
  AND md.movimiento_id IN (
    SELECT id FROM movimiento WHERE documento_ref = 'T-2026-0001'
  )
WHERE td.traspaso_id = 2
GROUP BY td.combinacion_id, td.cantidad
HAVING COALESCE(SUM(md.cantidad*md.signo),0) < td.cantidad;
```

---

## Fase 2 — Sincronizar stock (T-2026-0001)

| ID | Tarea |
|----|--------|
| R1 | Crear `scripts/sincronizar_movimiento_desde_traspaso.py` |
| R2 | Lógica: para cada fila `traspaso_detalle`, `delta = cantidad_td - sum(md)`; si `delta > 0`, INSERT `movimiento_detalle` en el movimiento INGRESO_COMPRA del traspaso (crear movimiento si no existe y traspaso CONFIRMADO) |
| R3 | **Idempotente:** no duplicar si se corre dos veces |
| R4 | Ejecutar `--traspaso-id 2 --dry-run` → `--yes` |

**CLI esperado:**

```powershell
python scripts/auditar_stock_traspaso_vs_movimiento.py --traspaso-id 2
python scripts/sincronizar_movimiento_desde_traspaso.py --traspaso-id 2 --dry-run
python scripts/sincronizar_movimiento_desde_traspaso.py --traspaso-id 2 --yes
```

**Criterio R4:**

| Métrica | Esperado |
|---------|----------|
| Σ movimiento_detalle (T-2026-0001) | **44** |
| Σ traspaso_detalle (id=2) | **44** |
| Delta | **0** |

---

## Fase 3 — Verificación UI + código

| ID | Tarea |
|----|--------|
| V1 | Recargar Nexus → **Depósito Web** → marca ACTVITTA: **44 pares**, **4 artículos** (565 visible) |
| V2 | `python scripts/validar_traspaso_detalle.py --traspaso-id 2` sigue PASS |

---

## Fase 4 — Prevención (obligatoria en esta OT)

Evitar que un traspaso CONFIRMADO quede con stock incompleto si se rehidrata después.

| ID | Tarea | Archivo |
|----|--------|---------|
| P1 | Script `scripts/reparar_ppd_descp_material_vacio.py`: UPDATE `ppd.descp_material` desde `material.descripcion` WHERE `material_code`/`id_material` NOT NULL AND `descp_material` IN ('', NULL). Incluir **ppd_id=202**. | nuevo script |
| P2 | En `_crear_traspasos_para_pp` (FI → snapshot): `material = COALESCE(NULLIF(TRIM(ppd.descp_material),''), mat.descripcion, fid.linea_snapshot->>'material_nombre')` | `modules/compra_legal/logic.py` |
| P3 | En `_resolve_combinacion_id`: si `material` vacío y hay código, resolver por `material.codigo_proveedor` + proveedor de línea | `modules/compra_legal/logic.py` |
| P4 | (Opcional) Tras `rehidratar_traspaso_*`: si traspaso ya `CONFIRMADO`, llamar sync movimiento o warning en UI | `compra_legal` / script |

**Criterio P1:** `SELECT descp_material FROM pedido_proveedor_detalle WHERE id=202` = `LOC. CENTRUM/CACHAREL`.

---

## Checks cierre (JSON obligatorio)

Archivo: `OT-DEPOSITO-WEB-506-001-EVIDENCIA.json`

```json
{
  "ot_id": "OT-DEPOSITO-WEB-506-001",
  "status": "OK",
  "traspaso_id": 2,
  "traspaso_nro": "T-2026-0001",
  "checks": [
    {"id": "C1", "pass": true, "expected": "traspaso_detalle pares", "actual": 44},
    {"id": "C2", "pass": true, "expected": "movimiento_detalle pares", "actual": 44},
    {"id": "C3", "pass": true, "expected": "delta TD vs MD", "actual": 0},
    {"id": "C4", "pass": true, "expected": "deposito_web pares ACTVITTA", "actual": 44},
    {"id": "C5", "pass": true, "expected": "deposito_web articulos ref565", "actual": 1},
    {"id": "C6", "pass": true, "expected": "ppd_id 202 descp_material", "actual": "LOC. CENTRUM/CACHAREL"}
  ]
}
```

---

## Orden ejecución Claude Code (sin preguntar)

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main

# Fase 1-2
python scripts/auditar_stock_traspaso_vs_movimiento.py --traspaso-id 2
python scripts/sincronizar_movimiento_desde_traspaso.py --traspaso-id 2 --dry-run
python scripts/sincronizar_movimiento_desde_traspaso.py --traspaso-id 2 --yes

# Fase 3
python scripts/validar_traspaso_detalle.py --traspaso-id 2

# Fase 4
python scripts/reparar_ppd_descp_material_vacio.py --pp-id 1 --dry-run
python scripts/reparar_ppd_descp_material_vacio.py --pp-id 1 --yes
# Editar logic.py P2-P3 + smoke import

# Evidencia
# Generar OT-DEPOSITO-WEB-506-001-EVIDENCIA.json
```

Reportar PASS/FAIL. Si C4 falla tras C2 OK, revisar JOIN marca en `deposito_web/logic.py` (`id_marca` en snapshot).

---

## Fuera de alcance

- Re-ejecutar OT-505-002 (snapshot ya corregido).
- Reabrir OT-504.
- Cambios en `rimec-web` catálogo (solo Nexus depósito).
