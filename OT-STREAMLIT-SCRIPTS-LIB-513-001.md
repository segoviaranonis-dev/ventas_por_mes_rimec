# OT-STREAMLIT-SCRIPTS-LIB-513-001 — Fix `ModuleNotFoundError: scripts.lib` en Streamlit Cloud

**Estado:** PENDIENTE EJECUCIÓN (Claude Code) — fix mínimo ya puede existir en working tree  
**Fecha:** 2026-05-18  
**Repo:** https://github.com/segoviaranonis-dev/ventas_por_mes_rimec.git  
**Deploy:** Streamlit Cloud (`/mount/src/ventas_por_mes_rimec`)

## Error en producción

```
ModuleNotFoundError: No module named 'scripts.lib'
  File ".../modules/rimec_engine/ui.py", line 1583, in _render_import_pilares_excel
    from scripts.import_pilares_linea_lr_excel import run_import_pilares
  File ".../scripts/import_pilares_linea_lr_excel.py", line 30
    from scripts.lib.import_heartbeat import ...
```

**Causa:** Varios scripts importan `scripts.lib.import_heartbeat`, documentado en `.cursor/rules/import-heartbeat.mdc`, pero el paquete **`scripts/lib/` nunca se commiteó** a Git. En local puede no fallar si el archivo existía solo en disco; en Streamlit Cloud falta.

**No es error de Supabase ni del reset 511.**

---

## Objetivo

1. Añadir paquete `scripts/lib/import_heartbeat.py` (+ `__init__.py`).
2. Verificar import desde Motor de Precios → Admin líneas → Importar pilares Excel.
3. **Push a `main`** en `ventas_por_mes_rimec`.
4. **Reboot** app Streamlit Cloud (redeploy automático al push).

---

## Fase 1 — Crear archivos (si no existen)

| Archivo | Contenido |
|---------|-----------|
| `scripts/__init__.py` | vacío o docstring |
| `scripts/lib/__init__.py` | vacío |
| `scripts/lib/import_heartbeat.py` | `start_import_heartbeat`, `stop_import_heartbeat` |

API requerida (usada en 6+ scripts):

```python
stop_hb, hb_thread = start_import_heartbeat(lambda: estado["msg"], interval_sec=60)
try:
    ...
finally:
    stop_import_heartbeat(stop_hb, hb_thread)
```

Implementación: hilo `threading` + `Event`, print cada 60s con `flush=True`, formato:

`[HH:MM:SS] … sigo vivo (cada 60s, tick N) — <mensaje>`

Referencia: `.cursor/rules/import-heartbeat.mdc`

---

## Fase 2 — Verificación local

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main

python -c "from scripts.lib.import_heartbeat import start_import_heartbeat, stop_import_heartbeat; print('OK')"
python -c "from scripts.import_pilares_linea_lr_excel import run_import_pilares; print('OK')"
```

Opcional smoke Streamlit:

```powershell
streamlit run main.py
# Motor de Precios → Admin líneas → expander Importar pilares (no debe crashear al abrir)
```

---

## Fase 3 — Git push

```powershell
git add scripts/__init__.py scripts/lib/__init__.py scripts/lib/import_heartbeat.py
git status   # confirmar que NO hay .env
git commit -m "fix(streamlit): add scripts.lib.import_heartbeat missing from repo"
git push origin main
```

Streamlit Cloud redeploya solo al detectar push en `main`.

---

## Fase 4 — Verificación Streamlit Cloud

| Check | Esperado |
|-------|----------|
| App arranca sin error global | OK |
| Motor de Precios → Admin líneas | Carga sin traceback |
| Expander “Importar pilares desde Excel” | Se abre; import solo falla si faltan Excel (no por `scripts.lib`) |

Registrar URL app en `OT-STREAMLIT-SCRIPTS-LIB-513-001-EVIDENCIA.json`.

---

## Checks cierre

```json
{
  "ot_id": "OT-STREAMLIT-SCRIPTS-LIB-513-001",
  "checks": [
    {"id": "C1", "pass": true, "expected": "scripts.lib import OK", "actual": "..."},
    {"id": "C2", "pass": true, "expected": "git push main", "actual": "<sha>"},
    {"id": "C3", "pass": true, "expected": "Streamlit admin lineas sin ModuleNotFoundError", "actual": "..."}
  ]
}
```

---

## Fuera de alcance

- Cambiar lógica de `import_pilares_linea_lr_excel.py`
- OT-512 deploy completo
- Inlined heartbeat en cada script (mantener módulo único)

---

## Orden Claude Code

**No pedir confirmación.** Push + evidencia JSON. Si el fix ya está en el repo, solo verificar C1–C3 y cerrar OT.
