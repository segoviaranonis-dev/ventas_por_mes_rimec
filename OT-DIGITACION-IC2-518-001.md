# OT-DIGITACION-IC2-518-001 — Fix asignar 2ª IC a PP: `precio_evento_id` = 'None'

**Estado:** PENDIENTE (Claude Code)  
**Fecha:** 2026-05-18  
**Repo:** https://github.com/segoviaranonis-dev/ventas_por_mes_rimec.git  
**Módulo:** `modules/digitacion/`

## Error en producción (Streamlit Cloud)

```
ValueError: invalid literal for int() with base 10: 'None'
  File modules/digitacion/ui.py", line 195, in _render_asignacion
    if int(ev_actual) in ids_list:
```

**Cuándo:** Al asignar la **segunda** IC a un **PP existente** (IC-2026-0002 · BR SPORT).

## Causa raíz

`ev_actual = ic.get("precio_evento_id")` puede ser:

| Valor en `dg_ic_data` | `if ev_actual:` | `int(ev_actual)` |
|----------------------|-----------------|------------------|
| `NULL` en BD → `NaN` (pandas) | True (NaN es “truthy”) | Falla |
| string `'None'` | True | **ValueError** |
| `None` Python | False | — OK |

La IC pendiente suele tener `precio_evento_id` **NULL** hasta elegir evento en el selectbox. El código asume entero válido.

## Objetivo

1. Normalizar IDs opcionales (`precio_evento_id`) sin `int()` ciego.
2. Segunda (y N-ésima) IC al mismo PP: pantalla asignación **sin crash**.
3. Pre-selección de evento solo si el ID es entero válido y está en listado cerrado.
4. Push `main` → usuario sincroniza Streamlit.

---

## Fase 1 — Helper (`modules/digitacion/logic.py`)

```python
def coerce_optional_int(val) -> int | None:
    """None, NaN, 'None', '', 'nan' → None; else int."""
```

Usar `pandas.isna` si hace falta. **No** duplicar en otros módulos en esta OT.

---

## Fase 2 — `ui.py` `_render_asignacion`

| Línea ~191-196 | Cambio |
|----------------|--------|
| `ev_actual = ic.get("precio_evento_id")` | `ev_actual = coerce_optional_int(...)` |
| `if ev_actual:` + `int(ev_actual)` | `if ev_actual is not None and ev_actual in ids_list:` |

Opcional al guardar en bandeja (línea ~77): normalizar `precio_evento_id` en dict antes de `dg_ic_data`.

---

## Fase 3 — Pruebas

| Caso | Esperado |
|------|----------|
| IC sin `precio_evento_id` (NULL) | Selectbox evento, idx=0, sin error |
| Asignar 1ª IC → PP nuevo | OK |
| Asignar 2ª IC → **mismo PP existente** | OK, sin ValueError |
| IC con evento ya en BD (entero) | Pre-selección correcta en selectbox |

---

## Fase 4 — Git

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main
git add modules/digitacion/logic.py modules/digitacion/ui.py
git commit -m "fix(digitacion): coerce precio_evento_id null/None al asignar IC a PP"
git push origin main
```

Entregar `OT-DIGITACION-IC2-518-001-EVIDENCIA.json`.

---

## Prohibido (integridad Auto)

- `except ValueError: pass` sin normalizar
- Hardcodear evento_id
- Cambiar lógica `asignar_ic` / tabla puente

---

## Fuera de alcance

- Refactor completo digitación
- OT Paso 5 / Motor

**No pedir confirmación al director.**
