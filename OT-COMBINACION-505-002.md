# OT-COMBINACION-505-002 — Recuperar 8 pares ref 565 (44 → 36 en traspaso)

**Estado:** ✅ CERRADA (2026-05-17) — evidencia `OT-COMBINACION-505-002-EVIDENCIA.json`  
**Fecha:** 2026-05-17  
**Depende de:** OT-COMBINACION-505-001 (backfill + rehidratación base OK)  
**No reabrir:** OT-TRASPASO-504-001 (UniqueViolation cerrado)

## Síntoma

| Fuente | Pares |
|--------|------:|
| `traspaso.snapshot_json` (FAC-INT 1-PV001) | **44** |
| `traspaso_detalle` (traspaso_id=2, T-2026-0001) | **36** |
| **Brecha** | **8** |

Usuario traspasó 44 pares; en Bazar/detalle solo llegaron 36.

---

## Causa raíz (confirmada)

| Capa | Hallazgo |
|------|----------|
| **Snapshot** | Ítem `4202-565`: `material=''` (vacío), `color='CAMEL 1528'`, tallas t36–t40 = **8 pares** |
| **Resolución** | `rehidratar_traspaso_standalone._resolve_combinacion_id` L47-48: `if not material: return None` |
| **Origen** | `pedido_proveedor_detalle` id **202** (PP-2026-0001): `descp_material=''`, pero `material_code=31855`, `id_material=49526` |
| **Maestro** | `material` id 49526 / codigo **31855** → descripción **`LOC. CENTRUM/CACHAREL`** (existe en BD) |

No es pérdida en tránsito: la rehidratación **saltó** el ítem porque el snapshot heredó material vacío del PPD.

---

## Objetivo

1. Corregir `snapshot_json` del traspaso 2 (material legible para `_resolve`).
2. Re-hidratar `traspaso_detalle` sin duplicar las 14 filas existentes (merge por `combinacion_id`).
3. Validar **44 pares**, **19 filas**, **0 duplicados**.
4. (Opcional H2) Evitar recurrencia en PPD + lógica de traspaso.

---

## Fase 1 — Corrección datos (T-2026-0001)

| ID | Tarea | Comando |
|----|--------|---------|
| R1 | Corregir snapshot ref 565 | `python scripts/corregir_snapshot_ref565.py --dry-run` → `--yes` |
| R2 | Re-hidratar detalle | `python scripts/rehidratar_traspaso_standalone.py --traspaso-id 2 --yes` |
| R3 | Validar | `python scripts/validar_traspaso_detalle.py --traspaso-id 2` |
| R4 | Diagnóstico brecha (antes/después) | `python scripts/diagnosticar_brecha_traspaso.py --traspaso-id 2` |

**Criterio R1:** en snapshot, ítem ref `565` tiene `material = "LOC. CENTRUM/CACHAREL"` (no `""`).

**Criterio R2-R3:**

| Métrica | Esperado |
|---------|----------|
| `SUM(traspaso_detalle.cantidad)` | **44** |
| `COUNT(*)` filas detalle | **19** (14 + 5 tallas 565) |
| Duplicados `(traspaso_id, combinacion_id)` | **0** |

**JSON evidencia:** `OT-COMBINACION-505-002-EVIDENCIA.json`

---

## Fase 2 — Prevención (recomendado, misma OT si hay tiempo)

| ID | Tarea | Archivo |
|----|--------|---------|
| P1 | Backfill `ppd.descp_material` desde `material.descripcion` cuando `material_code`/`id_material` poblado y descripción vacía (ppd_id=202 y similares) | script `scripts/reparar_ppd_descp_material_vacio.py` o SQL one-shot |
| P2 | En `_crear_traspasos_para_pp` / armado snapshot: si `descp_material` vacío → `COALESCE(descp_material, m.descripcion, linea_snapshot->>'material_nombre')` | `modules/compra_legal/logic.py` |
| P3 | En `_resolve_combinacion_id`: fallback por `material.codigo_proveedor` si texto vacío (solo si se pasa código; no romper FI existentes) | `modules/compra_legal/logic.py` |

**Criterio P1:** `SELECT descp_material FROM pedido_proveedor_detalle WHERE id=202` ≠ `''`.

---

## Fase 3 — Smoke usuario

| ID | Tarea |
|----|--------|
| V1 | Nexus → Compra Legal → T-2026-0001: detalle muestra **44 pares** (incluye 565 CAMEL 1528). |
| V2 | Confirmar que totales coinciden con expander FAC-INT 1-PV001. |

---

## Checks cierre (JSON obligatorio)

```json
{
  "ot_id": "OT-COMBINACION-505-002",
  "status": "OK",
  "checks": [
    {"id": "C1", "pass": true, "expected": "snapshot ref565 material no vacio", "actual": "LOC. CENTRUM/CACHAREL"},
    {"id": "C2", "pass": true, "expected": "traspaso_detalle pares", "actual": 44},
    {"id": "C3", "pass": true, "expected": "traspaso_detalle filas", "actual": 19},
    {"id": "C4", "pass": true, "expected": "duplicados traspaso_id+combinacion_id", "actual": 0},
    {"id": "C5", "pass": true, "expected": "brecha snapshot vs detalle", "actual": 0}
  ],
  "root_cause": "ppd.descp_material vacio -> snapshot material vacio -> resolve None",
  "ppd_id_afectado": 202,
  "material_code": 31855,
  "pares_recuperados": 8
}
```

---

## Orden de ejecución (copiar a Claude Code)

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main

python scripts/diagnosticar_brecha_traspaso.py --traspaso-id 2
python scripts/corregir_snapshot_ref565.py --dry-run
python scripts/corregir_snapshot_ref565.py --yes
python scripts/rehidratar_traspaso_standalone.py --traspaso-id 2 --yes
python scripts/validar_traspaso_detalle.py --traspaso-id 2
python scripts/diagnosticar_brecha_traspaso.py --traspaso-id 2
```

Generar `OT-COMBINACION-505-002-EVIDENCIA.json` y reportar PASS/FAIL.

**No pedir confirmación intermedia** salvo error de BD.

---

## Fuera de alcance

- Re-sanear PP completo (módulo 500 cerrado).
- ALTER TABLE nullable en `color`/`material`.
- Reabrir OT-504.
