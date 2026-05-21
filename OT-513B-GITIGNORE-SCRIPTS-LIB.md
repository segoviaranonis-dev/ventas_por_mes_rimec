# OT-513B — Cerrar OT-513: `.gitignore` + verificación Streamlit (sin acción del director)

**Estado:** PENDIENTE (Claude Code)  
**Padre:** OT-STREAMLIT-SCRIPTS-LIB-513-001 (commit `ccfc675` ya en GitHub)  
**Repo:** https://github.com/segoviaranonis-dev/ventas_por_mes_rimec.git

## Objetivo

El director **no ejecuta comandos**. Claude Code completa lo pendiente de auditoría Auto.

---

## Tarea 1 — Evitar recurrencia `.gitignore`

En `.gitignore`, tras la línea `lib/`, debe existir:

```gitignore
lib/
!scripts/lib/
```

Si falta, añadirla. Commit y push a `main`.

```powershell
cd C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main
git add .gitignore
git commit -m "chore(gitignore): track scripts/lib despite lib/ pattern"
git push origin main
```

---

## Tarea 2 — Verificar C3 Streamlit Cloud

1. Esperar redeploy tras push (1–3 min).
2. Abrir la app Streamlit del proyecto `ventas_por_mes_rimec` (URL del dashboard Streamlit Cloud).
3. **Motor de Precios → Admin líneas** — debe cargar **sin** `ModuleNotFoundError: scripts.lib`.
4. Abrir expander **Importar pilares desde Excel** — no debe crashear al expandir.
5. Si la app sigue con código viejo: **Manage app → Reboot** en Streamlit dashboard y repetir paso 3.

Registrar URL real de la app en evidencia.

---

## Tarea 3 — Actualizar evidencia y cerrar

1. Actualizar `OT-STREAMLIT-SCRIPTS-LIB-513-001-EVIDENCIA.json`:
   - `auditoria_auto`: `"PASS"` (no condicional) si C3 OK
   - `checks[C3].pass`: `true`
   - `verificacion_streamlit.url_app`: URL real
2. Actualizar `docs/OT_REGISTRO_ESTADO.md` si hace falta.
3. **No tocar** lógica de pilares, precios, ni `ui.py` salvo que C3 siga fallando por otra causa (reportar, no parchear con `except ImportError`).

---

## Prohibido

- `except ImportError` en `modules/rimec_engine/ui.py`
- Diccionarios/markup paralelos
- Pedir al director que ejecute git o Streamlit

---

## Entrega

- Commit SHA del `.gitignore`
- Evidencia JSON actualizada
- Una línea: `C3 Streamlit: OK` o `C3 FAIL: <motivo>`

**No pedir confirmación al director.**
