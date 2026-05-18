# Despliegue Streamlit Cloud — OT-512

**Nexus (ventas_por_mes_rimec) → Streamlit Cloud**

---

## Prerequisitos

- Cuenta Streamlit Cloud (https://share.streamlit.io) — usar GitHub login con `segoviaranonis-dev`
- Repo ya está en GitHub: `ventas_por_mes_rimec`
- Main file: `main.py` (raíz del repo)

---

## 1. Crear app Streamlit

1. Ir a https://share.streamlit.io
2. Click **New app**
3. **Deploy an app:**
   - **Repository:** `segoviaranonis-dev/ventas_por_mes_rimec`
   - **Branch:** `main`
   - **Main file path:** `main.py`
   - **App URL (custom):** elegir subdominio, ej. `rimec-nexus` → URL será `https://rimec-nexus.streamlit.app`

4. Click **Deploy!** — NO continuar hasta configurar secrets (paso 2)

---

## 2. Configurar Secrets (ANTES del primer deploy)

1. En la pantalla de deploy, click **Advanced settings** (o ir a Settings → Secrets después)
2. Agregar secrets en formato TOML:

```toml
SUPABASE_URL = "https://extrlcvcgypwazxipvqm.supabase.co"
SUPABASE_KEY = "COPIAR_ANON_KEY_DESDE_LOCAL"
DATABASE_URL = "postgresql://postgres.ext...:PASSWORD@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
```

**⚠️ Valores reales:**
- `SUPABASE_KEY`: copiar `NEXT_PUBLIC_SUPABASE_ANON_KEY` de cualquier `.env.local` local
- `DATABASE_URL`: copiar de `.env.local` de report (o Supabase dashboard)
- **NO commitear** estos valores al repo — solo en Streamlit Secrets UI

### Verificar nombres de secrets en código

El archivo `core/db.py` o `core/config.py` puede usar nombres diferentes. Verificar:

```python
# Si el código usa:
import os
SUPABASE_URL = os.getenv("SUPABASE_URL")  # ← nombre debe coincidir
DATABASE_URL = os.getenv("DATABASE_URL")
```

Si hay discrepancia, ajustar los nombres en el TOML de arriba para que coincidan.

---

## 3. Deploy

1. Click **Deploy** (si aún no lo hiciste)
2. Esperar build — verás logs en tiempo real:
   - `Installing requirements.txt`
   - `Running main.py`
   - Si hay error de secrets, revisar paso 2

3. Si build ✅ verde → app está live

---

## 4. Verificación

| Check | Esperado |
|-------|----------|
| App status | ✅ Running |
| URL accesible | https://XXXXX.streamlit.app carga |
| Login / Home | Módulos cargan (pueden estar vacíos post-reset 511) |
| No error conexión BD | Si hay error "connection refused" → revisar `DATABASE_URL` en secrets |

### Probar módulos clave

- **Home** → debe cargar sin error
- **Motor Compras** → puede mostrar tabla vacía (normal post-reset)
- **Diccionario Web** (módulo 13.5) → debe cargar y mostrar 6 reglas casos precio

---

## 5. Actualizar app (futuros deploys)

Streamlit Cloud redeploya automáticamente al hacer `git push` a `main`. Si necesitas redeployar manualmente:

1. Ir a https://share.streamlit.io/app (tu app)
2. Click **Manage app** → **Reboot**

---

## Troubleshooting

### App no inicia — error "ModuleNotFoundError"

- Verificar `requirements.txt` tiene todas las dependencias
- Si falta alguna: agregar, commit, push → auto-redeploy

### Error "connection refused" a Supabase

- Verificar `DATABASE_URL` en Secrets tiene el formato correcto:
  ```
  postgresql://postgres.XXXXX:PASSWORD@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require
  ```
- Si usas `psycopg2`, verificar que `requirements.txt` tiene `psycopg2-binary` (NO `psycopg2`)

### Error "st.secrets has no attribute"

- Verificar que los nombres en Secrets TOML coinciden con los que usa el código
- Ejemplo: si código usa `st.secrets["SUPABASE_URL"]`, el TOML debe tener `SUPABASE_URL = "..."`

### Módulos cargan vacíos

- Normal post-reset OT-511 — BD operativa en 0
- Esperar carga de datos (OT futura)

---

## URL final

*Completar después del deploy:*

```
Streamlit Nexus: https://XXXXX.streamlit.app
```

Copiar esta URL a `OT-DEPLOY-GIT-VERCEL-512-001-EVIDENCIA.json` y `docs/DEPLOY_MAPA_URLS.md`.
