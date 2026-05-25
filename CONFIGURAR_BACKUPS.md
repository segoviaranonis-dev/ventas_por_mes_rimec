# ⚙️ Configuración de Backups Automáticos

## 🎯 Objetivo

Configurar GitHub Actions para ejecutar backups automáticos diarios de la base de datos PostgreSQL (Supabase).

---

## 📝 Pasos de Configuración

### 1. Configurar Secrets en GitHub

Ve a: https://github.com/segoviaranonis-dev/ventas_por_mes_rimec/settings/secrets/actions

Haz clic en **"New repository secret"** y agrega cada uno de estos:

| Nombre | Valor | Dónde obtenerlo |
|--------|-------|-----------------|
| `DB_HOST` | `db.PROJECT_ID.supabase.co` | Supabase Dashboard → Settings → Database → Host |
| `DB_PORT` | `5432` | (siempre es 5432) |
| `DB_NAME` | `postgres` | (siempre es postgres) |
| `DB_USER` | `postgres` | (siempre es postgres) |
| `DB_PASSWORD` | `tu-password-de-supabase` | Supabase Dashboard → Settings → Database → Database password |

**Cómo obtener DB_PASSWORD:**
1. Ve a: https://supabase.com/dashboard/project/YOUR_PROJECT_ID/settings/database
2. Busca "Database password"
3. Copia el password (o resetéalo si no lo tienes)

**⚠️ IMPORTANTE:** El password es diferente a tu password de Supabase login. Es específico de la base de datos.

---

### 2. Verificar Workflow

El archivo `.github/workflows/backup-diario.yml` ya está creado y pusheado.

**Revisa que esté en GitHub:**
https://github.com/segoviaranonis-dev/ventas_por_mes_rimec/blob/main/.github/workflows/backup-diario.yml

---

### 3. Probar Backup Manual

#### Opción A: Ejecutar desde GitHub Actions (Recomendado)

1. Ve a: https://github.com/segoviaranonis-dev/ventas_por_mes_rimec/actions
2. Selecciona "Backup Diario de Base de Datos" en la lista izquierda
3. Haz clic en "Run workflow" (botón derecho)
4. Selecciona branch: `main`
5. Haz clic en "Run workflow" (botón verde)

**Espera 2-3 minutos** y verás:
- ✅ Verde: Backup exitoso
- ❌ Rojo: Algo falló (revisa logs)

---

#### Opción B: Ejecutar Localmente

Si quieres probar el script localmente primero:

```bash
# 1. Instalar PostgreSQL client (si no lo tienes)
# Windows: https://www.postgresql.org/download/windows/
# Linux: sudo apt-get install postgresql-client
# Mac: brew install postgresql

# 2. Ejecutar script
cd C:/Users/hecto/Nexus_Core/control_central
python scripts/seguridad/backup_db_automatico.py

# 3. Verificar resultado
dir backups\db
# Deberías ver: backup_YYYYMMDD_HHMMSS.sql.gz
```

---

### 4. Descargar Backups de GitHub

Después de que el workflow ejecute exitosamente:

1. Ve a: https://github.com/segoviaranonis-dev/ventas_por_mes_rimec/actions
2. Haz clic en el run más reciente (verde ✅)
3. Scroll abajo hasta "Artifacts"
4. Verás: `db-backup-1234` (número varía)
5. Haz clic para descargar (archivo .zip)

**El .zip contiene:** `backup_YYYYMMDD_HHMMSS.sql.gz`

---

### 5. Restaurar desde Backup (Si necesitas)

#### Restaurar tabla específica:

```bash
# 1. Descomprimir backup
gunzip backup_20260525_030000.sql.gz

# 2. Extraer solo la tabla que necesitas
findstr /C:"CREATE TABLE nombre_tabla" backup_20260525_030000.sql > tabla.sql
findstr /C:"COPY nombre_tabla" backup_20260525_030000.sql >> tabla.sql

# 3. Conectar a Supabase
psql -h db.PROJECT_ID.supabase.co ^
     -U postgres ^
     -d postgres ^
     -f tabla.sql

# 4. Ingresar password cuando te lo pida
```

---

#### Restaurar DB completa:

**⚠️ ESTO BORRARÁ TODA LA DB ACTUAL - ÚSALO SOLO EN EMERGENCIA**

```bash
# 1. Descomprimir
gunzip backup_20260525_030000.sql.gz

# 2. Restaurar (te pedirá password)
psql -h db.PROJECT_ID.supabase.co ^
     -U postgres ^
     -d postgres ^
     -f backup_20260525_030000.sql
```

---

## 🔍 Troubleshooting

### Error: "pg_dump: command not found"

**Solución:** Instalar PostgreSQL client
- Windows: https://www.postgresql.org/download/windows/
- Verificar: `pg_dump --version`

---

### Error: "connection refused"

**Causa:** DB_HOST incorrecto o DB offline

**Solución:**
1. Verificar DB_HOST en secrets
2. Verificar que Supabase esté online: https://status.supabase.com/

---

### Error: "password authentication failed"

**Causa:** DB_PASSWORD incorrecto

**Solución:**
1. Resetear password en Supabase Dashboard → Settings → Database
2. Actualizar secret DB_PASSWORD en GitHub

---

### Workflow no ejecuta automáticamente

**Causa:** GitHub Actions deshabilitado o repo sin actividad

**Solución:**
1. Ve a: https://github.com/segoviaranonis-dev/ventas_por_mes_rimec/settings/actions
2. Verifica que "Allow all actions and reusable workflows" esté seleccionado
3. Si el repo no tiene actividad por 60 días, GitHub deshabilita workflows
   - Ejecuta un workflow manual para reactivar

---

## 📅 Cronograma de Backups

| Hora (UTC) | Hora (Paraguay) | Frecuencia |
|------------|-----------------|------------|
| 3:00 AM | 12:00 AM | Diario |

**Retención:** 30 días (backups más antiguos se eliminan automáticamente)

---

## ✅ Checklist de Verificación

Después de configurar, verifica:

- [ ] Secrets configurados en GitHub (5 secrets)
- [ ] Workflow ejecutó exitosamente (verde ✅)
- [ ] Backup descargable en Artifacts
- [ ] Archivo .sql.gz puede descomprimirse
- [ ] Backup local en `backups/db/` (si ejecutaste localmente)

---

## 📞 Soporte

**Problema con el script?**
- Ver logs en: https://github.com/segoviaranonis-dev/ventas_por_mes_rimec/actions
- Revisar: `DISASTER_RECOVERY.md` para procedimientos completos

**Problema con Supabase?**
- https://supabase.com/support

---

**🔒 MANTENER LOS SECRETS SEGUROS - NUNCA COMPARTIRLOS EN SLACK/EMAIL/CÓDIGO**
