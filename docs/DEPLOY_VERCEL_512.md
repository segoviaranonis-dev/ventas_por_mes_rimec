# Despliegue Vercel — OT-512

**3 proyectos Next.js → 3 proyectos Vercel separados**

---

## Prerequisitos

- Cuenta Vercel (https://vercel.com) — usar GitHub login con `segoviaranonis-dev`
- Los 3 repos ya están en GitHub:
  - `rimec-web`
  - `bazzar-web`
  - `report`

---

## 1. Desplegar rimec-web

### 1.1 Crear proyecto Vercel

1. Ir a https://vercel.com/new
2. **Import Git Repository** → seleccionar `segoviaranonis-dev/rimec-web`
3. **Configure Project:**
   - **Project Name:** `rimec-web` (o el que prefieras)
   - **Framework Preset:** Next.js (auto-detectado)
   - **Root Directory:** `./` (default)
   - **Build Command:** `npm run build` (default)
   - **Output Directory:** `.next` (default)
   - **Install Command:** `npm install` (default)

### 1.2 Configurar Environment Variables

**IMPORTANTE:** No continuar con el deploy hasta configurar las variables.

En **Environment Variables** agregar:

| Variable | Value | Entorno |
|----------|-------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://extrlcvcgypwazxipvqm.supabase.co` | Production, Preview |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | (copiar de `rimec-web/.env.local` local) | Production, Preview |

*Valores: copiar de tu archivo `.env.local` local — NO están en el repo.*

### 1.3 Deploy

1. Click **Deploy**
2. Esperar build ✅ verde
3. Obtener URL: `https://rimec-web-XXXXX.vercel.app`
4. Probar: abrir URL → debe cargar home (catálogo puede estar vacío post-reset 511)

---

## 2. Desplegar bazzar-web

### 2.1 Crear proyecto Vercel

1. Ir a https://vercel.com/new
2. **Import Git Repository** → seleccionar `segoviaranonis-dev/bazzar-web`
3. **Configure Project:**
   - **Project Name:** `bazzar-web`
   - **Framework Preset:** Next.js 14
   - **Root Directory:** `./`
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`

### 2.2 Configurar Environment Variables

| Variable | Value | Entorno |
|----------|-------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://extrlcvcgypwazxipvqm.supabase.co` | Production, Preview |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | (copiar de `.env.local`) | Production, Preview |
| `SUPABASE_SERVICE_ROLE_KEY` | (copiar de `.env.local`) | **Production only** |
| `RESEND_API_KEY` | (copiar de `.env.local`) | Production |
| `ADMIN_EMAIL` | (copiar de `.env.local` o `admin@bazzar.com.py`) | Production |
| `ADMIN_WHATSAPP` | (copiar de `.env.local` o `595981000000`) | Production |

*⚠️ `SUPABASE_SERVICE_ROLE_KEY` NUNCA en Preview — solo Production (server-side).*

### 2.3 Deploy

1. Click **Deploy**
2. Esperar build ✅
3. Obtener URL: `https://bazzar-web-XXXXX.vercel.app`
4. Probar: abrir URL → home debe cargar

---

## 3. Desplegar report (rimec-report)

### 3.1 Crear proyecto Vercel

1. Ir a https://vercel.com/new
2. **Import Git Repository** → seleccionar `segoviaranonis-dev/report`
3. **Configure Project:**
   - **Project Name:** `rimec-report` (o `report`)
   - **Framework Preset:** Next.js 15
   - **Root Directory:** `./`
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`

### 3.2 Configurar Environment Variables

| Variable | Value | Entorno |
|----------|-------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://extrlcvcgypwazxipvqm.supabase.co` | Production, Preview |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | (copiar de `.env.local`) | Production, Preview |
| `DATABASE_URL` | `postgresql://postgres.ext...:[PASSWORD]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require` | **Production only** |

*⚠️ `DATABASE_URL` es para server-side (NOT `NEXT_PUBLIC_`) — copiar de `.env.local` local.*

### 3.3 Deploy

1. Click **Deploy**
2. Esperar build ✅
3. Obtener URL: `https://report-XXXXX.vercel.app` (o `rimec-report-XXXXX`)
4. Probar: abrir URL → debe cargar home con navegación `/rimec`, `/retail`, `/sales-report`

---

## Verificación final

| Check | Esperado |
|-------|----------|
| rimec-web build | ✅ verde en Vercel dashboard |
| rimec-web URL | Home carga (catálogo puede estar vacío) |
| bazzar-web build | ✅ verde |
| bazzar-web URL | Home carga |
| report build | ✅ verde |
| report URL | Home `/` y `/rimec` cargan |

---

## Troubleshooting

### Build falla con error de tipos

- Verificar que `npm run build` pasa localmente primero
- Si falla en Vercel pero pasa local: verificar versión Node.js en Vercel → debe ser ≥18

### Error 500 en runtime

- Verificar Environment Variables están correctas
- Revisar Vercel Function Logs (Dashboard → Functions → Ver logs)
- Verificar que `DATABASE_URL` en report NO tiene `NEXT_PUBLIC_` prefix

### Catálogo vacío en rimec-web

- Normal post-reset OT-511 — BD operativa en 0
- Esperar carga de datos (OT futura)

---

## URLs finales

*Completar después del deploy:*

```
rimec-web:  https://rimec-web-XXXXX.vercel.app
bazzar-web: https://bazzar-web-XXXXX.vercel.app
report:     https://report-XXXXX.vercel.app
```

Copiar estas URLs a `OT-DEPLOY-GIT-VERCEL-512-001-EVIDENCIA.json`.
