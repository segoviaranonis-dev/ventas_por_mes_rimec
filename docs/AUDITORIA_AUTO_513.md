# Auditoría Auto — OT-STREAMLIT-SCRIPTS-LIB-513-001

## Causa raíz aceptada

- Módulo **documentado** en `.cursor/rules/import-heartbeat.mdc` pero **ausente en Git**.
- Solución válida: **añadir** `scripts/lib/import_heartbeat.py` (+ `__init__.py`), no silenciar el error.

## Diff permitido (solo esto)

- `scripts/__init__.py` (nuevo)
- `scripts/lib/__init__.py` (nuevo)
- `scripts/lib/import_heartbeat.py` (nuevo)

## Diff prohibido (FAIL automático)

- `except ImportError` en `modules/rimec_engine/ui.py` para saltar import pilares
- Funciones vacías `start_import_heartbeat = lambda: (None, None)` en UI
- Markup/precio/caso tocados
- `linea.caso_id` escrito en imports

## Verificación

```powershell
python -c "from scripts.lib.import_heartbeat import start_import_heartbeat, stop_import_heartbeat; print('OK')"
git ls-files scripts/lib/import_heartbeat.py
```

Streamlit Cloud: Motor → Admin líneas → expander import pilares **abre sin traceback**.

## Veredicto

| | |
|-|-|
| PASS | Solo archivos permitidos + C1–C3 + GitHub main actualizado |
| FAIL | Cualquier parche prohibido — revertir commit |
