# Control de integridad — Holding RIMEC (rol Auto / Maestro)

> **Ninguna OT se considera cerrada sin veredicto Auto** cuando el director pide control de integridad.  
> Claude Code **ejecuta**; Auto **audita** contra políticas del holding.

---

## Principios no negociables

| # | Regla | Violación típica de Claude (rechazar) |
|---|--------|--------------------------------------|
| P1 | **Una sola verdad** — precio/caso desde evento + `precio_lista`, venta web desde `fn_precio_venta_web` + `caso_precio_web_regla` | Diccionario Python paralelo, `%` hardcodeado en UI |
| P2 | **Caso comercial en evento**, no en `linea.caso_id` para lógica nueva | Resucitar `linea.caso_id` o `linea_caso` |
| P3 | **Pilares blindados** — nunca `TRUNCATE CASCADE` sobre `caso_precio_biblioteca` ni tablas referenciadas por `linea` | Reset que borra `linea` (error 039) |
| P4 | **Sales Report blindado** — `registro_ventas_general_v2` intocable | Cualquier DELETE/TRUNCATE en ventas históricas |
| P5 | **Sin parches de import** — si falta módulo, **crear el módulo** documentado | `try/except ImportError: pass`, stubs vacíos en UI |
| P6 | **Sin atajos de stock** — depósito = `movimiento_detalle`; web = vista/`precio_web` acordada | Inventar stock en memoria o tabla auxiliar no acordada |
| P7 | **Ley FI** — Compra Web / cards usan `get_fi_detalles_canonico` / `render_fi_card` | Tabla plana 198 filas o join inventado a `precio_lista` |
| P8 | **Evidencia máquina** — JSON pre/post counts; no “funciona en mi máquina” | Cerrar OT sin `*-EVIDENCIA.json` |

---

## Flujo obligatorio

```
Director pide OT → Auto redacta OT (criterios + anti-patrones)
       → Claude Code ejecuta → entrega evidencia + diff
       → Auto audita (checklist) → PASS / FAIL / CONDICIONAL
       → Solo si PASS → OT CERRADA en OT_REGISTRO_ESTADO.md
```

**Claude Code no marca OT como cerrada** sin línea en evidencia: `"auditoria_auto": "PASS"`.

---

## Checklist rápido por tipo de OT

### Reset / SQL
- [ ] Pilares COUNT pre = post
- [ ] `caso_precio_biblioteca` no truncado con CASCADE
- [ ] `registro_ventas_general_v2` sin cambio
- [ ] `caso_precio_web_regla` intacto

### Precio / Web
- [ ] Sin markup en TS/Python fuera de `caso_precio_web_regla` / `fn_precio_venta_web`
- [ ] Paridad depósito ↔ `v_stock_rimec.precio_web` si aplica OT-510

### Deploy / Git
- [ ] Sin `.env` / `service_role` en commit
- [ ] `npm run build` verde (Next) antes de push

### Bugfix Streamlit / imports
- [ ] Causa raíz = archivo faltante o path, no silenciar error
- [ ] Módulo alineado con `.cursor/rules/*` existentes

---

## OT-513 (`scripts.lib`) — veredicto Auto

| Pregunta | Respuesta |
|----------|-----------|
| ¿Es parche/diccionario intermedio? | **No** — restaura `scripts/lib/import_heartbeat.py` ya exigido por `import-heartbeat.mdc` |
| ¿Alternativa prohibida? | Inline `def start_import_heartbeat: pass` en `ui.py` → **rechazado** |
| ¿Toca pilares/precios? | **No** |
| Condición para PASS en prod | `git ls-files scripts/lib/import_heartbeat.py` en `main` + Streamlit Admin líneas sin traceback |
| Veredicto 2026-05-18 | **PASS condicional** — commit `ccfc675`; causa raíz `.gitignore` `lib/`; post-fix `!scripts/lib/` en repo |

## OT-514 (rimec-web auth) — veredicto Auto 2026-05-18

| Check | Resultado |
|-------|-----------|
| Login server-side `usuario_v2` | ✅ `validateUsuario.ts` + `/api/auth/login` |
| Solo VENDEDOR/ADMIN (+ DIRECTOR→ADMIN) | ✅ `roles.ts` + 403 |
| Sin usuarios hardcodeados | ✅ |
| Middleware rutas | ✅ `/`, carrito, pedidos, estadísticas, APIs |
| **SESSION_SECRET en Vercel** | ⚠️ **Obligatorio** — hay default en código si falta env |
| **SUPABASE_SERVICE_ROLE_KEY** | ⚠️ Recomendado — fallback a anon puede fallar o ser inseguro si RLS abre `usuario_v2` |
| C3 pruebas CESAR/HECTOR/IVO | Pendiente confirmación director |

**Veredicto:** **PASS condicional** — commit `dfedd16`; cerrar C3 manual + configurar `SESSION_SECRET` en Vercel Production. |

---

## Qué enviar a Auto tras cada Claude Code

1. `OT-*-EVIDENCIA.json`
2. Lista de archivos tocados (o `git diff --stat`)
3. Captura o log del check funcional
4. Pregunta explícita si dudás: *“¿Violamos P1–P8?”*

Auto responde: **PASS** / **FAIL** + acciones correctivas (nueva OT mínima, sin rehacer todo).
