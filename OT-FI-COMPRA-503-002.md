# OT-FI-COMPRA-503-002 — Métricas unificadas + Ley FI Card

**Estado:** ✅ CERRADA (2026-05-17) — evidencia `OT-FI-COMPRA-503-002-EVIDENCIA.json`  
**Fecha:** 2026-05-17  
**Prerequisito:** OT-FI-COMPRA-503-001 Fase 1 OK  

## Fase 2 — Métricas

- [x] `get_metricas_facturacion_compra(id_cl)` en `modules/compra_legal/logic.py`
- [x] `get_compra_header` usa métricas unificadas
- [x] `get_pps_de_compra.total_vendido` = FI + VT sin doble conteo (H-A)
- [x] Acordeón FAC-INT usa `met["pares_facturados"]`

## Fase 3 — Ley FI

- [x] `compra_legal/ui.py` → `render_fi_card` vía `get_facturas_internas_de_compra`
- [x] `facturacion/ui.py` → `get_fi_registro_por_numero` + `render_fi_card`
- [x] `.cursor/rules/rimec-ley-fi-card.mdc`

## Verificación

```bash
python scripts/auditar_compra_facturados.py --compra-id 1
```

Esperado: header_facturados = pp_fi = fac_expander_total = 44

## JSON cierre

`OT-FI-COMPRA-503-002-EVIDENCIA.json`
