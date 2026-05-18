# OT-COMBINACION-505-001 — Fix ON CONFLICT (talla)

> **Estado:** ✅ Aplicado en `scripts/backfill_combinacion_desde_ppd.py` — OT-505-001/002 cerradas

## Causa

`INSERT ... ON CONFLICT DO NOTHING` en PostgreSQL **exige** un target explícito (`ON CONFLICT ON CONSTRAINT …` o `ON CONFLICT (col, …)`).

En `talla`, el único UNIQUE es `uq_talla_proveedor_codigo (proveedor_id, codigo_proveedor)` — no aplica a tallas numéricas creadas solo con `talla_etiqueta`.

`_resolve_combinacion_id` resuelve talla por **`talla_etiqueta`**, no por `talla_valor` solo.

## Cambios aplicados

1. **`scripts/backfill_combinacion_desde_ppd.py`** reescrito:
   - `get_or_create_talla`: SELECT por `talla_etiqueta` → INSERT sin ON CONFLICT
   - `referencia` (no `linea_referencia`) en `combinacion.referencia_id`
   - material/color por `descp_material` / `descp_color` (+ códigos F9)
   - `combinacion` sin `proveedor_id`, `activo_web=false` (igual que `logic.py`)
   - URL desde `secrets.toml` / `.env` (sin credenciales en el script)

2. **`scripts/rehidratar_traspaso_detalle.py`** nuevo:
   - Lee `snapshot_json`, usa `_resolve_combinacion_id`, agrupa cantidades, reemplaza `traspaso_detalle`

## Fix color.codigo_proveedor NOT NULL (2026-05-16)

Sin `color_code` en PPD (ej. `BLANCO 99/VINO 785`), el INSERT fallaba y hacía **rollback total**.

**Solución:** código sintético negativo `CRC32(proveedor_id|nombre)` + `SAVEPOINT` por fila PPD. Preferir `color_code` / `material_code` del PPD cuando existan.

---

## Comandos (orden)

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main

python scripts/backfill_combinacion_desde_ppd.py --pp-id 1 --dry-run
python scripts/backfill_combinacion_desde_ppd.py --pp-id 1 --yes

python scripts/rehidratar_traspaso_detalle.py --traspaso-id 2 --dry-run
python scripts/rehidratar_traspaso_detalle.py --traspaso-id 2 --yes

python scripts/auditar_combinacion_traspaso.py --traspaso-id 2 --compra-id 1
```

## Criterios de cierre (C1–C3)

| ID | Criterio | Esperado |
|----|----------|----------|
| C1 | `combinacion` poblada para moléculas PP-2026-0001 | > 0 filas resolubles |
| C2 | `traspaso_detalle` T-2026-0001 | SUM(cantidad) ≈ 44, 0 duplicados `(traspaso_id, combinacion_id)` |
| C3 | UI Compra / traspaso | líneas con `combinacion_id` no NULL |

Luego: Facturación → ENVIAR FAC-INT → Compra Web Bazar.
