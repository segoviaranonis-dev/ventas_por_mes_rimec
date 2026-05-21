# OT-RIMEC-WEB-AUTH-514-001 — Login Vercel (RIMEC Web): solo VENDEDOR y ADMIN

**Estado:** ✅ CERRADA (2026-05-18) — `dfedd16` · Auto PASS condicional  
**Fecha:** 2026-05-18  
**Repo:** https://github.com/segoviaranonis-dev/rimec-web.git  
**Carpeta local:** `C:\Users\hecto\Documents\Prg_locales\rimec-web`  
**Deploy:** Vercel (producción mayorista)

## Problema

Hoy **rimec-web** está **abierto**: catálogo, carrito, estadísticas sin login. Cualquiera con la URL de Vercel entra.

## Regla de negocio (director)

| `usuario_v2.categoria` | Acceso RIMEC Web (Vercel) |
|------------------------|---------------------------|
| **VENDEDOR** | ✅ Permitido |
| **ADMIN** | ✅ Permitido |
| **SU**, **USER**, otros | ❌ Bloqueado — mensaje claro, sin datos |
| Credenciales inválidas | ❌ Rechazo |

Misma **fuente de verdad** que Nexus: tabla `usuario_v2` (`descp_usuario` + `password` + `categoria`).

**Referencia Nexus:** `ventas_por_mes_rimec-main/core/auth.py` (login + `role_map` DIRECTOR/GERENTE → ADMIN).

> Nota: en Nexus el módulo Facturación FI es solo ADMIN/ROOT en sidebar; aquí el director pide acceso web para **vendedores** que operan el catálogo mayorista. No copiar `allowed_roles` de `facturacion/__init__.py` — copiar **mecanismo de login** de `AuthManager.login`.

---

## Arquitectura objetivo

```
/login (público)
    → POST /api/auth/login (server) valida usuario_v2
    → si VENDEDOR|ADMIN → cookie sesión firmada (httpOnly)
    → redirect /

middleware.ts
    → sin cookie válida → redirect /login
    → rutas /api/* (excepto auth) → 401 sin sesión

Cualquier otra categoría → /acceso-denegado (o login con error)
```

**Obligatorio server-side:** la validación de password **no** puede depender solo del anon key en el browser si RLS bloquea `usuario_v2`.

Usar **una** de:

- `DATABASE_URL` + `pg` en route handler (como `report`), o  
- `SUPABASE_SERVICE_ROLE_KEY` solo en servidor (nunca `NEXT_PUBLIC_`).

---

## Fase 1 — Sesión y utilidades

| ID | Archivo | Tarea |
|----|---------|--------|
| A1 | `lib/auth/session.ts` | Crear/leer cookie sesión: `id_usuario`, `name`, `role` (`VENDEDOR` \| `ADMIN`) |
| A2 | `lib/auth/roles.ts` | `CATEGORIAS_PERMITIDAS = ['VENDEDOR','ADMIN']` + mismo `role_map` que Nexus para normalizar (DIRECTOR→ADMIN, etc.) |
| A3 | `lib/auth/validateUsuario.ts` | Query parametrizada a `usuario_v2` |

```sql
SELECT id_usuario, descp_usuario, categoria
FROM usuario_v2
WHERE descp_usuario = $1 AND password = $2
LIMIT 1
```

| A4 | Secret | `SESSION_SECRET` o reutilizar convención del repo — documentar en `.env.example` |

---

## Fase 2 — API y páginas

| ID | Tarea |
|----|--------|
| B1 | `app/api/auth/login/route.ts` — POST JSON `{ usuario, password }` → 200 + Set-Cookie o 401/403 |
| B2 | `app/api/auth/logout/route.ts` — borrar cookie |
| B3 | `app/api/auth/me/route.ts` — opcional, devuelve sesión actual |
| B4 | `app/login/page.tsx` — formulario estilo RIMEC (usuario + contraseña), logo mayorista |
| B5 | `app/acceso-denegado/page.tsx` — “Tu categoría no tiene acceso al catálogo mayorista” |
| B6 | `middleware.ts` — proteger `/`, `/carrito`, `/pedidos`, `/estadisticas`, `/api/estadisticas`, `/api/consulta-pilar` |

**403** si login OK pero categoría no permitida (ej. SU / IVO).

---

## Fase 3 — UI existente

| ID | Tarea |
|----|--------|
| C1 | `Header.tsx` — mostrar nombre usuario + botón **Cerrar sesión** |
| C2 | Catálogo/carrito: solo tras login (middleware ya lo exige) |
| C3 | `DialogoActivacion` — opcional vincular `vendedor_v2` por `id_usuario` de sesión (si existe columna FK); si no hay FK, mantener flujo actual pero sesión ya identifica al analista |

---

## Fase 4 — Variables Vercel

En proyecto Vercel `rimec-web`, añadir (Production + Preview):

| Variable | Uso |
|----------|-----|
| `NEXT_PUBLIC_SUPABASE_URL` | ya existe |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ya existe |
| `DATABASE_URL` **o** `SUPABASE_SERVICE_ROLE_KEY` | solo login server |
| `SESSION_SECRET` | firmar cookie (string largo aleatorio) |

No commitear valores reales.

---

## Fase 5 — Pruebas

| Caso | Esperado |
|------|----------|
| CESAR / VENDEDOR / 123456 | Entra al catálogo |
| HECTOR / ADMIN / 123456 | Entra |
| IVO / SU / mandarinas | Bloqueado (403 o pantalla denegado) |
| password incorrecta | 401 |
| Sin cookie → `/carrito` | Redirect `/login` |
| `npm run build` | ✅ sin errores TypeScript |

---

## Fase 6 — Git y Vercel

```powershell
cd C:\Users\hecto\Documents\Prg_locales\rimec-web
npm run build
git add -A
git status   # sin .env.local
git commit -m "feat(auth): login usuario_v2 solo VENDEDOR y ADMIN para Vercel"
git push origin main
```

Vercel redeploy automático. Probar URL producción tras 1–2 min.

Entregar `OT-RIMEC-WEB-AUTH-514-001-EVIDENCIA.json` con checks + URL Vercel.

---

## Prohibido (integridad Auto — FAIL si aparece)

- Lista hardcodeada de usuarios en TypeScript
- `if (true)` o bypass temporal “para probar”
- Validar password solo en `use client` con anon key expuesto
- `except` silenciosos que dejen pasar sin sesión
- Mezclar auth de Bazzar Web (`bazzar-web`) en este repo

---

## Fuera de alcance

- Cambiar `usuario_v2` en Supabase
- Auth en `bazzar-web` o `report`
- Nexus Streamlit (ya tiene `core/auth.py`)
- Migrar passwords a hash (futuro; hoy plain como Nexus)

---

## Auditoría Auto

Cierre solo con veredicto Auto: `docs/AUDITORIA_AUTO_514.md` (crear checklist breve).

**Director no ejecuta comandos** — Claude Code hace build, push y prueba Vercel.

---

## Orden Claude Code

**No pedir confirmación.** Implementar → build → push → evidencia JSON.
