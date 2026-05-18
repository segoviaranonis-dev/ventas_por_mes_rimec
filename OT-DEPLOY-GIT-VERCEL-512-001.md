# OT-DEPLOY-GIT-VERCEL-512-001 — Publicar 4 repos + desplegar (Vercel ×3, Streamlit ×1)

**Estado:** PENDIENTE EJECUCIÓN (Claude Code)  
**Fecha:** 2026-05-17  
**Prerequisito recomendado:** [OT-RESET-TRANSACCIONAL-511-001](./OT-RESET-TRANSACCIONAL-511-001.md) cerrada (BD limpia para carga final) — **no bloqueante** del deploy de código.

## Objetivo

1. Subir la **versión actual** de cada proyecto a su repositorio GitHub (sin secretos).
2. Desplegar en **Vercel**: Report, RIMEC Web, Bazzar Web.
3. Desplegar en **Streamlit Cloud**: Nexus (`ventas_por_mes_rimec`).

**No borra datos de Supabase.** Solo versiona código y configura hosting.

---

## Mapa repos ↔ carpetas locales

| Producto | Carpeta local | Remote GitHub | Puerto local | Plataforma |
|----------|---------------|---------------|--------------|------------|
| **Nexus** (Streamlit) | `C:\Users\hecto\Documents\Prg_locales\ventas_por_mes_rimec-main` | https://github.com/segoviaranonis-dev/ventas_por_mes_rimec.git | 8501 | **Streamlit Cloud** |
| **RIMEC Web** (mayoristas) | `C:\Users\hecto\Documents\Prg_locales\rimec-web` | https://github.com/segoviaranonis-dev/rimec-web.git | 3001 | **Vercel** |
| **Bazzar Web** (tienda) | `C:\Users\hecto\Documents\Prg_locales\bazzar-web` | https://github.com/segoviaranonis-dev/bazzar-web.git | 3000 | **Vercel** |
| **Report** (informes) | `C:\Users\hecto\Documents\Prg_locales\report` | https://github.com/segoviaranonis-dev/report.git | 3000* | **Vercel** |

\* Report y Bazzar no comparten el mismo proyecto Vercel; cada uno es un **proyecto Vercel distinto**.

**Entrypoints:**

| Repo | Comando dev | Build producción |
|------|-------------|------------------|
| Nexus | `streamlit run main.py` | Streamlit: **Main file** = `main.py` |
| rimec-web | `npm run dev` (-p 3001) | `npm run build` |
| bazzar-web | `npm run dev` | `npm run build` |
| report | `npm run dev` | `npm run build` |

Referencia local: `ventas_por_mes_rimec-main/COMO_EJECUTAR.md`.

---

## Fase 0 — Seguridad antes de cualquier `git push`

| ID | Tarea |
|----|--------|
| S0 | Escanear cada repo: **no** commitear `.env`, `.env.local`, `secrets.toml`, `.streamlit/secrets.toml`, claves reales en `.env.example` |
| S1 | Si `bazzar-web/.env.example` contiene URL/keys reales → reemplazar por placeholders `REEMPLAZAR_*` |
| S2 | Confirmar `.gitignore` excluye `.env*` / `node_modules` / `.next` / `__pycache__` / `.vercel` |
| S3 | `git secrets` o búsqueda manual: `service_role`, `sk-`, `re_`, passwords en historial del primer commit |
| S4 | **Nunca** subir `OT-*-EVIDENCIA.json` con credenciales si existieran |

---

## Fase 1 — Git: los 4 repositorios

Para **cada** carpeta, en orden (puede paralelizarse si no hay conflicto de credenciales):

### Plantilla por repo

```powershell
cd <CARPETA_LOCAL>
git init                    # solo si no existe .git
git branch -M main
git remote remove origin 2>$null
git remote add origin <URL_GITHUB>
git add -A
git status                  # revisar que NO aparezcan .env.local
git commit -m "chore: versión actual para deploy etapa 512"
git push -u origin main
```

Si el remoto ya tiene commits (README de GitHub): `git pull origin main --rebase` antes del push, o `--allow-unrelated-histories` si aplica.

| Repo | URL |
|------|-----|
| Nexus | `https://github.com/segoviaranonis-dev/ventas_por_mes_rimec.git` |
| RIMEC Web | `https://github.com/segoviaranonis-dev/rimec-web.git` |
| Bazzar Web | `https://github.com/segoviaranonis-dev/bazzar-web.git` |
| Report | `https://github.com/segoviaranonis-dev/report.git` |

### Nexus — extras Streamlit

| ID | Tarea |
|----|--------|
| N1 | Asegurar `requirements.txt` actualizado (`pip freeze` solo si falta dependencia; preferir editar manual) |
| N2 | Crear `.streamlit/config.toml` mínimo si no existe (theme opcional, `headless = true`) |
| N3 | **No** commitear `secrets.toml` — documentar plantilla en `docs/DEPLOY_STREAMLIT_SECRETS.example.toml` (TOML con keys vacías) |
| N4 | README raíz: una línea con URL Streamlit Cloud (placeholder hasta deploy) |

### Next.js — extras comunes (3 repos)

| ID | Tarea |
|----|--------|
| X1 | Verificar `npm run build` local **sin errores** en cada repo antes del push |
| X2 | Crear o completar `.env.example` en **rimec-web** (hoy puede faltar; copiar patrón de report/bazzar) |
| X3 | Opcional: `vercel.json` solo si hace falta (redirects, regions); por defecto Vercel detecta Next |

**Criterio Fase 1:** los 4 remotes muestran `main` actualizado; `git ls-files` sin `.env.local` en ninguno.

---

## Fase 2 — Vercel (3 proyectos)

Cuenta: la del usuario (**segoviaranonis-dev**). Si CLI no está logueada, documentar pasos dashboard en `docs/DEPLOY_VERCEL_512.md`.

### Por proyecto Vercel

| Proyecto Vercel | Repo importado | Framework | Root | Build | Output |
|-----------------|----------------|-----------|------|-------|--------|
| `rimec-web` | rimec-web | Next.js | `./` | `npm run build` | default |
| `bazzar-web` | bazzar-web | Next.js 14 | `./` | `npm run build` | default |
| `rimec-report` (o `report`) | report | Next.js 15 | `./` | `npm run build` | default |

### Variables de entorno (configurar en Vercel UI → Settings → Environment Variables)

**rimec-web** (mínimo):

| Variable | Entorno |
|----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Production, Preview |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Production, Preview |

**bazzar-web** (mínimo):

| Variable | Entorno |
|----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Production, Preview |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Production, Preview |
| `SUPABASE_SERVICE_ROLE_KEY` | Production only (server) |
| `RESEND_API_KEY` | Production |
| `ADMIN_EMAIL` | Production |
| `ADMIN_WHATSAPP` | Production |

**report** (mínimo — ver `report/.env.example`):

| Variable | Entorno |
|----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Production, Preview |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Production, Preview |
| `DATABASE_URL` | Production only (server, **sin** `NEXT_PUBLIC_`) |

Valores: leer de los `.env.local` locales del director **sin** commitearlos; pegar en Vercel.

### CLI (si `vercel login` activo)

```powershell
cd C:\Users\hecto\Documents\Prg_locales\rimec-web
vercel link --yes
vercel env pull .env.vercel.local
vercel --prod

# Repetir para bazzar-web y report
```

### Criterio Fase 2

| Check | Esperado |
|-------|----------|
| Build Vercel | ✅ verde en los 3 |
| URL producción | Abre home sin 500 |
| rimec-web | Catálogo carga (puede estar vacío post-reset 511) |
| bazzar-web | Home carga |
| report | `/` o `/rimec` según rutas del app |

Registrar URLs finales en evidencia JSON.

---

## Fase 3 — Streamlit Cloud (Nexus)

1. https://share.streamlit.io → **New app**
2. Repository: `segoviaranonis-dev/ventas_por_mes_rimec`
3. Branch: `main`
4. **Main file path:** `main.py`
5. **App URL:** elegir subdominio (ej. `rimec-nexus` o el que defina el usuario)

### Secrets (Streamlit Cloud → Settings → Secrets)

Plantilla TOML (valores desde Supabase / `.env` local Nexus, **no** al repo):

```toml
SUPABASE_URL = "https://....supabase.co"
SUPABASE_KEY = "eyJ..."          # anon o service según lo que use core/db.py hoy
DATABASE_URL = "postgresql://..."  # si la app lo requiere
```

| ID | Tarea |
|----|--------|
| ST1 | Revisar `core/db.py` / `config` qué nombres de secret espera y alinear TOML |
| ST2 | Tras deploy: abrir app → login/hub carga sin error de conexión |
| ST3 | Documentar URL en `docs/DEPLOY_STREAMLIT_512.md` |

**Criterio Fase 3:** app Streamlit accesible por HTTPS; módulos cargan (aunque operativa vacía).

---

## Fase 4 — Documentación y evidencia

| Archivo | Contenido |
|---------|-----------|
| `docs/DEPLOY_VERCEL_512.md` | URLs Vercel + lista env vars por proyecto |
| `docs/DEPLOY_STREAMLIT_512.md` | URL Streamlit + nombres de secrets |
| `docs/DEPLOY_MAPA_URLS.md` | Tabla única: Nexus, RIMEC Web, Bazzar, Report |
| `OT-DEPLOY-GIT-VERCEL-512-001-EVIDENCIA.json` | Checks + URLs + commit SHAs |

Actualizar `docs/OT_REGISTRO_ESTADO.md` → OT-512 PENDIENTE/CERRADA.

---

## Checks cierre (evidencia)

```json
{
  "ot_id": "OT-DEPLOY-GIT-VERCEL-512-001",
  "commits": {
    "ventas_por_mes_rimec": "<sha>",
    "rimec-web": "<sha>",
    "bazzar-web": "<sha>",
    "report": "<sha>"
  },
  "urls": {
    "streamlit_nexus": "https://....streamlit.app",
    "vercel_rimec_web": "https://....vercel.app",
    "vercel_bazzar_web": "https://....vercel.app",
    "vercel_report": "https://....vercel.app"
  },
  "checks": [
    {"id": "C1", "pass": true, "expected": "4 repos push main OK"},
    {"id": "C2", "pass": true, "expected": "0 archivos .env en git ls-files"},
    {"id": "C3", "pass": true, "expected": "3 builds Vercel green"},
    {"id": "C4", "pass": true, "expected": "Streamlit app live"},
    {"id": "C5", "pass": true, "expected": "npm run build local OK x3"}
  ]
}
```

---

## Orden ejecución Claude Code

```powershell
# Fase 0 + 1
# (cada repo: audit secrets → build test → git push)

# Fase 2 — Vercel (requiere sesión usuario; si falla auth, completar docs manuales)
# Fase 3 — Streamlit Cloud (idem)

# Evidencia
```

**No pedir confirmación intermedia.** Si Vercel/Streamlit requieren login del usuario, dejar **instrucciones exactas** en `docs/DEPLOY_*_512.md` y marcar C3/C4 como `blocked: auth` en evidencia con pasos pendientes.

**No ejecutar** OT-511 en esta OT salvo que el usuario lo pida explícitamente.

---

## Errores a evitar (vez pasada)

| Error | Evitar |
|-------|--------|
| Subir `.env.local` con service_role | Solo variables en panel Vercel/Streamlit |
| Un solo proyecto Vercel para las 3 webs | **3 proyectos** separados |
| Confundir `rimec-web` con Bazzar | rimec-web = mayoristas :3001 · bazzar-web = tienda :3000 |
| Push sin `npm run build` | Build roto en Vercel |
| TRUNCATE Supabase | Fuera de alcance |

---

## Fuera de alcance

- Dominios custom (`www.bazzar.com.py`) — DNS del usuario después
- CI/CD GitHub Actions (opcional futuro)
- OT-DEPOSITO-WEB-510, OT-RESET-511 (salvo mención)
- Cambios de lógica de negocio en las apps
