# OT-MOTOR-PASO3-UX-515-001 — Paso 3 Motor: progreso 1/N + ping DB (Streamlit Cloud)

**Estado:** IMPLEMENTADO en working tree (pendiente push con carga final)  
**Fecha:** 2026-05-18  
**Repo:** `ventas_por_mes_rimec` / Nexus Streamlit

## Problema

49 SKUs >30 min en Streamlit Cloud; barra solo avanzaba por **caso** (ej. 30/49 en ACT-BRSPORT sin pasos intermedios); `st.spinner` da sensación de cuelgue.

## Causa raíz

1. **Latencia** Supabase ↔ Streamlit Cloud: cada SKU puede hacer varias queries (`get_or_create_*` línea/ref/material).
2. **UX:** progreso agrupado por `caso_asignado`, no por fila.
3. **Fase previa** (`asegurar_pilares_para_listado`) sin feedback antes del 30/49.

## Fix Fase 1 (hecho en `ui.py`)

- Reemplazar `st.spinner` por `proceso_largo` (panel + barra + segundos transcurridos).
- Ping `SELECT 1` al inicio → mensaje **"DB conectada (X ms)"**.
- Progreso **SKU 1/49, 2/49…** en el loop interno.
- Mensaje explícito al bulk INSERT por caso.

## Fase 2 opcional (performance — OT futura)

- Batch `provisionar_pilares` antes del loop (ya existe parcialmente).
- Reducir round-trips: transacción única por N SKUs para material nuevo.
- Ejecutar Paso 3 pesado vía script CLI en máquina local si Cloud sigue lento.

## Deploy

Incluir en el **único push Git** al cerrar la carga final, o hotfix:

```powershell
git add modules/rimec_engine/ui.py modules/rimec_engine/logic.py
git commit -m "fix(motor): paso 3 progreso por SKU + ping DB Streamlit Cloud"
git push origin main
```

Streamlit Cloud redeploy ~1–2 min.

## Criterio éxito

- Se ve **SKU n/49** actualizándose cada fila.
- Primer mensaje **DB conectada (<5000 ms)** en región razonable.
- 49 SKUs en **<5 min** ideal (depende red); si >15 min → activar Fase 2.
