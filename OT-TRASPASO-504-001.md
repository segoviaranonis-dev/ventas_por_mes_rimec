# OT-TRASPASO-504-001 — Finalizar Compra: UniqueViolation traspaso_detalle

**Estado:** ✅ CERRADA (2026-05-17) — evidencia `OT-TRASPASO-504-001-EVIDENCIA.json`  
**Fecha:** 2026-05-17  
**Disparador:** `Finalizar y Distribuir` en Compra CL-2026-0001  

## Error reportado

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint
"traspaso_detalle_traspaso_id_combinacion_id_key"
DETAIL: Key (traspaso_id, combinacion_id)=(1, 3) already exists.
```

**SQL:** `INSERT INTO traspaso_detalle (traspaso_id, combinacion_id, cantidad) ...`

## Diagnóstico Auto (hipótesis H1 — alta probabilidad)

| Causa | Detalle |
|-------|---------|
| **H1** | `crear_traspaso_por_factura` inserta **1 fila por (ítem FI × talla)** sin agrupar. Varias líneas `factura_interna_detalle` con mismos 5 pilares + misma talla → mismo `combinacion_id` → violación UNIQUE. |
| **H2** | Tras saneo módulo 500, varias `fid` pueden compartir `grades_json` idéntico en la misma FI. |
| **H3** | Reintento manual: `traspaso` id=1 creado a medias (TX debería rollback; verificar si hubo commit parcial). |

**Archivo clave:** `modules/compra_legal/logic.py`  
- `crear_traspaso_por_factura` (~L208-229)  
- `_crear_traspasos_para_pp` bloque `factura_interna` (~L346-416)

**Constraint BD:** `UNIQUE (traspaso_id, combinacion_id)` en `traspaso_detalle` — **correcto**; el bug es no consolidar cantidades.

---

## Fase 1 — Investigación (obligatoria)

| ID | Tarea |
|----|--------|
| I1 | Crear `scripts/auditar_traspaso_duplicados.py --compra-id 1` (o `--traspaso-id 1`). Listar: traspaso(s), filas `traspaso_detalle`, duplicados potenciales por `combinacion_id`, FIs sin traspaso. |
| I2 | Para `traspaso_id=1`: query qué `fid` generaron `combinacion_id=3` duplicado (linea/ref/mat/color/talla). |
| I3 | Documentar en `docs/AUDIT_TRASPASO_DUPLICADOS.md`. |

**JSON:** `OT-TRASPASO-504-001-FASE1-EVIDENCIA.json`

---

## Fase 2 — Resolución código

| ID | Tarea |
|----|--------|
| R1 | En `crear_traspaso_por_factura`: **agregar por `combinacion_id`** antes del INSERT (`dict[comb_id] += qty`). |
| R2 | INSERT con upsert: `ON CONFLICT (traspaso_id, combinacion_id) DO UPDATE SET cantidad = traspaso_detalle.cantidad + EXCLUDED.cantidad` (o reemplazar según política documentada). |
| R3 | En `_crear_traspasos_para_pp` (FI): opcional merge previo de `items_tallas` por clave `(linea, referencia, material, color)` sumando dict `tallas`. |
| R4 | `finalizar_compra`: si falla, TX completa rollback; si existe traspaso BORRADOR sin detalle por `documento_ref`, documentar limpieza o relleno idempotente. |
| R5 | Script `scripts/reparar_traspaso_parcial.py --traspaso-id 1 --dry-run` / `--yes` para entorno dev (consolidar duplicados o borrar traspaso huérfano). |

---

## Fase 3 — Verificación

| ID | Tarea |
|----|--------|
| V1 | `python scripts/auditar_traspaso_duplicados.py --compra-id 1` → 0 duplicados en detalle. |
| V2 | Smoke: `finalizar_compra(1)` en CL PENDIENTE (o compra test) → **sin UniqueViolation**, mensaje éxito, `compra_legal.estado = DISTRIBUIDA`. |
| V3 | Σ `traspaso_detalle.cantidad` por traspaso = Σ pares FI asociados (tolerancia 0). |

---

## Checks cierre (JSON máquina obligatorio)

```json
{
  "ot_id": "OT-TRASPASO-504-001",
  "status": "OK",
  "checks": [
    {"id": "C1", "pass": true, "expected": "auditar 0 duplicate (traspaso_id, combinacion_id)", "actual": "..."},
    {"id": "C2", "pass": true, "expected": "finalizar_compra sin UniqueViolation", "actual": "..."},
    {"id": "C3", "pass": true, "expected": "pares traspaso = pares FI", "actual": "..."},
    {"id": "C4", "pass": true, "expected": "AUDIT doc + reparar script", "actual": "..."}
  ],
  "metrics": {
    "compra_id": 1,
    "cl_nro": "CL-2026-0001",
    "traspasos_creados": 0,
    "pares_fi": 44
  }
}
```

## No hacer

- No commit salvo pedido del usuario.  
- No relajar UNIQUE en BD (la constraint es deseada).  
- No tocar módulo 500 / ppd saneo.

## Contexto operativo

- Compra **CL-2026-0001**, proforma **7441-4084**, PP **PP-2026-0001**  
- **44 pares** facturados, **5 FI**  
- Usuario bloqueado en **Finalizar y Distribuir** hasta este fix.
