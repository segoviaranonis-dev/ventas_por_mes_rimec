# OT-COMBINACION-505-001 — Orden Claude Code (ejecutar sin preguntar)

> **Estado:** ✅ CERRADA — ver `OT-COMBINACION-505-002` para cierre 44 pares y `docs/OT_REGISTRO_ESTADO.md`

**Decisión arquitectura (cerrada):** Opción **2** — `codigo_proveedor` sintético negativo estable por `(proveedor_id, nombre)` cuando PPD no trae `color_code` / `material_code`. **No** ALTER TABLE.

**Auto ya aplicó** el fix en `scripts/backfill_combinacion_desde_ppd.py` (zlib CRC32, base `-9e9` color / `-8e9` material + SAVEPOINT por fila PPD).

---

## Secuencia obligatoria

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main

# 1. Backfill combinacion
python scripts/backfill_combinacion_desde_ppd.py --pp-id 1 --dry-run
python scripts/backfill_combinacion_desde_ppd.py --pp-id 1 --yes

# 2. Rehidratar traspaso T-2026-0001
python scripts/rehidratar_traspaso_detalle.py --traspaso-id 2 --dry-run
python scripts/rehidratar_traspaso_detalle.py --traspaso-id 2 --yes

# 3. Validar
python scripts/auditar_combinacion_traspaso.py --traspaso-id 2 --compra-id 1
```

---

## Criterios PASS (evidencia JSON)

Crear `OT-COMBINACION-505-001-EVIDENCIA.json`:

```json
{
  "ot": "OT-COMBINACION-505-001",
  "fase": "2-cierre",
  "c1_combinacion_count": ">0",
  "c2_traspaso_detalle_pares": "~44",
  "c2_duplicados_traspaso_combinacion": 0,
  "c3_snapshot_vs_detalle": "OK",
  "backfill_combinaciones_nuevas": "<n>",
  "colores_codigo_sintetico": "<n>",
  "errores_backfill": 0
}
```

Consultas SQL de control:

```sql
SELECT COUNT(*) FROM combinacion;
SELECT COUNT(*), COALESCE(SUM(cantidad),0)
FROM traspaso_detalle WHERE traspaso_id = 2;
SELECT combinacion_id, COUNT(*)
FROM traspaso_detalle WHERE traspaso_id = 2
GROUP BY 1 HAVING COUNT(*) > 1;
```

---

## Si falla

| Error | Acción |
|-------|--------|
| `uq_color_proveedor_codigo` | Revisar colisión sintético; ajustar base en script |
| `misses` en rehidratar | Re-ejecutar backfill; verificar `descp_color` en `color.nombre` |
| pares << 44 | Auditar snapshot vs FI; no reabrir OT-504 |

---

## Fuera de alcance

- ALTER `color.codigo_proveedor` nullable
- Commits git (solo si usuario pide)
- OT-TRASPASO-504-001 (cerrado)

**Avisar al usuario** cuando los 3 pasos terminen con PASS o pegar error completo.
