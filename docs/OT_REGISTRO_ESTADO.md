# Registro de órdenes de trabajo (OT) — RIMEC Nexus + Web

> **Fuente de verdad del estado operativo.** Actualizado: **2026-05-18** (post OT-511 reset).  
> Evidencia máquina: `OT-*-EVIDENCIA.json` en raíz del repo.

---

## En curso (nueva etapa — carga final)

| OT | Título | Estado | Nota |
|----|--------|--------|------|
| [OT-DEPLOY-GIT-VERCEL-512-001](../OT-DEPLOY-GIT-VERCEL-512-001.md) | Git 4 repos + Vercel ×3 + Streamlit Nexus | **PARCIAL** | Fase 0+1 OK → docs `DEPLOY_*_512.md` para usuario |
| [OT-DEPOSITO-WEB-510-001](../OT-DEPOSITO-WEB-510-001.md) | Depósito Web: LPN + Precio venta = Bazar | **EN PAUSA** | Tras nueva carga con stock |

## Recomendado (prevención)

| OT | Título | Estado | Nota |
|----|--------|--------|------|
| [OT-FI-CASO-508-001](../OT-FI-CASO-508-001.md) Fase 2 | Persistir `caso` + `lista_precio_id` al crear/recalcular FI | **RECOMENDADO** | Evita “Sin caso” en nuevas FIs |

**Hilo mayo 2026 (504→509):** ✅ **CERRADO** — traspaso 44/44, depósito, Ley FI, precio web Bazar.  
**Simulación PP-2026-0001:** archivada por reset OT-511 (2026-05-18); BD operativa en **0**.

---

## Cerradas (reset + etapa carga final)

| OT | Título | Resultado | Evidencia |
|----|--------|-----------|-----------|
| [OT-RESET-TRANSACCIONAL-511-001](../OT-RESET-TRANSACCIONAL-511-001.md) | Vaciar operativa; pilares + biblioteca + diccionario intactos | **CERRADA** | `OT-RESET-TRANSACCIONAL-511-001-EVIDENCIA.json` |

Post-reset: `linea=1452`, biblioteca `5807` líneas-caso, `caso_precio_web_regla=6`, Sales Report `107570` sin cambio.

---

## Cerradas (mayo 2026 — simulación archivada PP-2026-0001)

| OT | Título | Resultado | Evidencia |
|----|--------|-----------|-----------|
| OT-TRASPASO-504-001 | UniqueViolation `traspaso_detalle` — merge por `combinacion_id` | CERRADA | `OT-TRASPASO-504-001-EVIDENCIA.json` |
| OT-COMBINACION-505-001 | Backfill `combinacion` + rehidratar traspaso | CERRADA (base) | `OT-COMBINACION-505-001-EVIDENCIA.json` |
| OT-COMBINACION-505-002 | Snapshot ref 565 material vacío → 44 pares traspaso | CERRADA | `OT-COMBINACION-505-002-EVIDENCIA.json` |
| OT-DEPOSITO-WEB-506-001 | Depósito Web 36→44 (`movimiento_detalle`) | CERRADA | `OT-DEPOSITO-WEB-506-001-EVIDENCIA.json` |
| OT-COMPRA-WEB-507-001 | Compra Web = Ley FI (`render_fi_card`) | CERRADA (código) | `OT-COMPRA-WEB-507-001-EVIDENCIA.json` |
| OT-FI-CASO-508-001 | Fase 1: backfill `fi.caso` + `lista_precio_id=8` | CERRADA F1 | `OT-FI-CASO-508-001-EVIDENCIA.json` |
| OT-WEB-PRECIO-509-001 | Diccionario casos → `precio_web` Bazar (migr. 048, módulo Nexus) | **CERRADA** | `OT-WEB-PRECIO-509-001-EVIDENCIA.json` |

### Referencia operativa PP-2026-0001

| Artefacto | Valor |
|-----------|--------|
| PP | PP-2026-0001 (`pp_id=1`) |
| Listado precio | Evento **#8** (CP 7447-4085x) |
| FI | **1-PV001** — 44 pares, caso **BR-VZ-MD-ML-MKA-O** (post backfill) |
| Compra Legal | CL-2026-0001 — DISTRIBUIDA |
| Traspaso | T-2026-0001 (`traspaso_id=2`) — 44 pares detalle |
| Depósito Web | 44 pares tras sync movimiento (506) |

---

## Cerradas (etapas anteriores)

| OT / etapa | Título | Evidencia |
|------------|--------|-----------|
| Módulo 500 | Saneo PP duplicados 391→273 | `SANEO_PP_2026_0001_COMPLETADO.md` |
| OT-PILAR-502 | Pilares FK género/marca/estilo | `OT-PILAR-502-*-EVIDENCIA.json` |
| OT-FI-COMPRA-503-002 | Ley FI card + métricas compra unificadas | `OT-FI-COMPRA-503-002-EVIDENCIA.json` |
| OT-COMPRA-501-002 | Trazabilidad PP ↔ listado `precio_evento_id` | `OT-COMPRA-501-002-EVIDENCIA.json` |

---

## Scripts clave por flujo

| Flujo | Scripts |
|-------|---------|
| Combinación / traspaso | `backfill_combinacion_desde_ppd.py`, `rehidratar_traspaso_standalone.py`, `corregir_snapshot_ref565.py` |
| Stock web | `sincronizar_movimiento_desde_traspaso.py`, `auditar_stock_traspaso_vs_movimiento.py` |
| Validación | `validar_traspaso_detalle.py`, `diagnosticar_brecha_traspaso.py` |
| Caso FI | `reparar_fi_caso_desde_listado.py` |
| Precio web | `auditar_precio_web_casos.py`, módulo **Diccionario Web** (`web_precio_caso`) |

---

## Reglas Cursor relacionadas

| Regla | Archivo |
|-------|---------|
| Ley FI (card canónico) | `.cursor/rules/rimec-ley-fi-card.mdc` |
| Compra Web = misma FI | `docs/COMPRA_WEB_LEY_FI.md` |
| Arquitectura única verdad | `.cursor/rules/rimec-arquitectura-unica-verdad.mdc` |

---

## Histórico de fixes documentados

| Doc | Tema |
|-----|------|
| `OT-COMBINACION-505-001-FIX-ON-CONFLICT.md` | ON CONFLICT talla + color sintético |
| `OT-COMBINACION-505-001-ORDEN-CLAUDE.md` | Orden backfill (superseded por 505-002) |
| `docs/AUDIT_COMBINACION_VACIA.md` | Diagnóstico combinación vacía |
| `docs/AUDIT_TRASPASO_DUPLICADOS.md` | Diagnóstico duplicados traspaso |
