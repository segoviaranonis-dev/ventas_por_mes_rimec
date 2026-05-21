# OT-MOTOR-PASO5-CIERRE-517-001 — Paso 5: cierre rápido + globos + volver a Carga (paso 0)

**Estado:** IMPLEMENTADO en working tree (pendiente push)  
**Fecha:** 2026-05-18

## Problema

- Paso 5 tarda **~5 min** sin feedback (re-sync pilares en Cloud).
- Usuario espera: **globos** y volver al **inicio del flujo (Carga / paso 0)**.

## Causa

`cerrar_evento_y_activar` llamaba siempre `sincronizar_marca_linea_desde_evento` → reprocesa 94+ SKUs en pilares (red lenta).

## Fix

1. `cerrar_evento_sql()` — solo 4 UPDATE (segundos).
2. Checkbox **desmarcado por defecto**: "Re-sincronizar pilares al cerrar".
3. `proceso_largo` con mensajes de avance.
4. Tras éxito: `celebrate_save` (balloons) + `re_paso = 0` + `_reset_flujo()` + `rerun`.

## Git

```powershell
git add modules/rimec_engine/logic.py modules/rimec_engine/ui.py
git commit -m "fix(motor): paso 5 cierre rapido, globos y vuelta a carga"
git push origin main
```

## Uso director

Cerrar con checkbox pilares **desmarcado** → ~5–15 s → globos → pantalla **0. Carga**.
