# OT-MOTOR-PASO4-AVANCE-516-001 — Paso 3 no avanza a Paso 4 tras cálculo largo (Streamlit Cloud)

**Estado:** PENDIENTE (Claude Code) — fix parcial en working tree  
**Fecha:** 2026-05-18  
**Repo:** https://github.com/segoviaranonis-dev/ventas_por_mes_rimec.git  
**Síntoma:** Cálculo 49 SKUs termina (~40 min) pero UI sigue en **Paso 3 Preview**; no pasa a **Paso 4 Validación**.

---

## Causa raíz

1. **`st.rerun()` dentro de `with proceso_largo()` + handler del botón** — tras ejecuciones muy largas, Streamlit Cloud pierde el WebSocket; el `re_paso = 4` no se refleja en el navegador.
2. **Estado solo en `session_state`** — si la sesión se corta, el paso queda en 3 aunque **BD ya tenga** `precio_lista` + `estado=validado`.
3. **`celebrate_step` + balloons** antes del rerun pueden interferir en runs largos (secundario).

**Fuente de verdad debe ser la BD**, no solo `st.session_state["re_paso"]`.

---

## Objetivo

1. Al entrar Paso 3: si `precio_lista` tiene filas para `re_evento_id` → banner + botón **Continuar al Paso 4**.
2. Al terminar cálculo: `st.rerun()` **fuera** de `proceso_largo`; persistir `validado` en BD antes del rerun.
3. Paso 4: si `re_casos` vacío → hidratar desde `precio_evento_caso` + counts.
4. Push a `main` → redeploy Streamlit Cloud.

---

## Fase 1 — `logic.py`

| Función | Rol |
|---------|-----|
| `resumen_paso3_evento(evento_id)` | `{estado, n_precio_lista}` |
| `hidratar_paso4_desde_bd(evento_id)` | `{casos, confirmados, total_skus}` |
| `ir_a_paso4_validacion(evento_id)` | Marca validado + devuelve pack o `None` |

(Revisar/implementar si el working tree ya las tiene.)

---

## Fase 2 — `ui.py` `_paso_3_preview`

| ID | Tarea |
|----|--------|
| U1 | Arriba del botón calcular: si `n_precio_lista > 0` → `st.success` + botón **➡ Continuar al Paso 4** |
| U2 | Al pulsar: `pack = ir_a_paso4_validacion()` → set `re_casos`, `re_skus_por_caso`, `re_paso=4`, `st.rerun()` |
| U3 | Fin del cálculo: cerrar `with proceso_largo` **antes** de `celebrate_step` y `st.rerun()` |
| U4 | Si `total_guardados == 0` pero `contar_skus_procesados > 0` → warning + enlace al botón Continuar |

---

## Fase 3 — `ui.py` `_paso_4_validacion`

| ID | Tarea |
|----|--------|
| V1 | Si `re_casos` vacío y hay `evento_id` → `hidratar_paso4_desde_bd` automático |

---

## Fase 4 — Opcional auto-avance

En `_render_flujo()`, si `re_paso == 3` y `n_precio_lista > 0` y estado `validado`:

```python
st.session_state["re_paso"] = 4
# hidratar si falta
st.rerun()
```

Solo si no rompe UX (evaluar con director).

---

## Pruebas

| Caso | Esperado |
|------|----------|
| Evento con 49 filas en `precio_lista`, UI en paso 3 | Botón Continuar → Paso 4 con tabla |
| Cálculo nuevo corto (local) | Auto avanza a paso 4 sin botón manual |
| Evento sin precio_lista | Sin botón Continuar |

```sql
SELECT pe.estado, COUNT(pl.id)
FROM precio_evento pe
LEFT JOIN precio_lista pl ON pl.evento_id = pe.id
WHERE pe.id = :tu_evento
GROUP BY pe.estado;
```

---

## Git + Streamlit

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main
git add modules/rimec_engine/logic.py modules/rimec_engine/ui.py
git commit -m "fix(motor): recuperar Paso 4 desde BD tras cálculo largo Cloud"
git push origin main
```

Entregar `OT-MOTOR-PASO4-AVANCE-516-001-EVIDENCIA.json`.

---

## Prohibido

- Forzar `re_paso=4` sin filas en `precio_lista`
- Parche que oculte Paso 3 sin validar BD
- Duplicar lógica de precios

---

## Auditoría Auto

Veredicto tras push: director en Paso 3 con datos en BD → un clic → Paso 4 con tabla completa.

**No pedir confirmación al director.**
