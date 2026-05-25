# 🚨 Plan de Recuperación ante Desastres (Disaster Recovery)

**Última actualización:** 2026-05-25  
**Responsable:** Héctor Segovia (segoviaranonis@gmail.com)

---

## 📋 Tabla de Contenidos

1. [Escenarios de Desastre](#escenarios-de-desastre)
2. [Backups Disponibles](#backups-disponibles)
3. [Procedimientos de Recuperación](#procedimientos-de-recuperación)
4. [Contactos de Emergencia](#contactos-de-emergencia)
5. [Checklist Post-Recuperación](#checklist-post-recuperación)

---

## 🔥 Escenarios de Desastre

### Nivel 1: Pérdida de Datos (Base de Datos)

**Síntomas:**
- Tabla eliminada accidentalmente
- Datos corruptos
- UPDATE/DELETE sin WHERE

**Impacto:** 🔴 CRÍTICO  
**Tiempo de recuperación objetivo (RTO):** 1 hora  
**Punto de recuperación objetivo (RPO):** 24 horas

**Procedimiento:** Ver [Recuperación de Base de Datos](#recuperación-de-base-de-datos)

---

### Nivel 2: Compromiso de Seguridad

**Síntomas:**
- Acceso no autorizado detectado
- Credenciales filtradas
- Cuenta de GitHub/Vercel/Supabase comprometida

**Impacto:** 🔴 CRÍTICO  
**Tiempo de acción:** INMEDIATO

**Procedimiento:** Ver [Respuesta a Compromiso](#respuesta-a-compromiso)

---

### Nivel 3: Caída de Servicio

**Síntomas:**
- Vercel/Streamlit down
- Supabase no responde
- Deploy fallido

**Impacto:** 🟡 ALTO  
**Tiempo de recuperación:** 30 minutos

**Procedimiento:** Ver [Recuperación de Servicio](#recuperación-de-servicio)

---

### Nivel 4: Corrupción de Código

**Síntomas:**
- Commit destructivo
- Branch main comprometido
- Código malicioso inyectado

**Impacto:** 🟡 ALTO  
**Tiempo de recuperación:** 2 horas

**Procedimiento:** Ver [Recuperación de Código](#recuperación-de-código)

---

## 💾 Backups Disponibles

### 1. Base de Datos (PostgreSQL/Supabase)

**Ubicación:**
```
control_central/backups/db/backup_YYYYMMDD_HHMMSS.sql.gz
```

**Frecuencia:** Diario (3:00 AM UTC / 00:00 Paraguay)  
**Retención:** 30 días  
**Automatización:** GitHub Actions (`.github/workflows/backup-diario.yml`)

**Backups adicionales:**
- **Supabase automático:** Últimas 7 días (si está en plan Pro)
- **GitHub Artifacts:** Últimos 30 backups en Actions

---

### 2. Código Fuente (Git)

**Repositorios principales:**
```
https://github.com/segoviaranonis-dev/ventas_por_mes_rimec.git (Nexus Core)
https://github.com/segoviaranonis-dev/rimec-web.git (Rimec Web)
https://github.com/segoviaranonis-dev/bazzar-web.git (Bazzar Web)
https://github.com/segoviaranonis-dev/report.git (Reportes)
```

**Repositorio de respaldo privado:** (Crear según recomendación)

---

### 3. Variables de Entorno

**Ubicaciones:**
- Vercel: Dashboard → Settings → Environment Variables
- Streamlit: Secrets management
- Local: `.streamlit/secrets.toml` (NO en Git)

**⚠️ IMPORTANTE:** Guardar copia offline de todas las variables de entorno.

---

## 🔧 Procedimientos de Recuperación

### Recuperación de Base de Datos

#### Escenario A: Restaurar tabla específica

```bash
# 1. Descargar último backup
cd control_central/backups/db
latest=$(ls -t backup_*.sql.gz | head -1)
gunzip -k $latest  # -k mantiene el .gz

# 2. Extraer solo la tabla necesaria
backup_file="${latest%.gz}"
grep -A 1000 "CREATE TABLE nombre_tabla" $backup_file > tabla_especifica.sql

# 3. Restaurar en Supabase
psql -h db.PROJECT_ID.supabase.co \
     -U postgres \
     -d postgres \
     -f tabla_especifica.sql

# 4. Verificar
psql -h db.PROJECT_ID.supabase.co \
     -U postgres \
     -d postgres \
     -c "SELECT COUNT(*) FROM nombre_tabla;"
```

---

#### Escenario B: Restauración completa

```bash
# 1. Descargar último backup
cd control_central/backups/db
latest=$(ls -t backup_*.sql.gz | head -1)
gunzip $latest

# 2. ADVERTENCIA: Esto BORRARÁ toda la DB actual
read -p "¿Estás seguro? Esto es DESTRUCTIVO (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Cancelado"
    exit 1
fi

# 3. Crear nueva DB temporal
createdb -h db.PROJECT_ID.supabase.co \
         -U postgres \
         nexus_restore_temp

# 4. Restaurar backup
backup_file="${latest%.gz}"
psql -h db.PROJECT_ID.supabase.co \
     -U postgres \
     -d nexus_restore_temp \
     -f $backup_file

# 5. Verificar datos
psql -h db.PROJECT_ID.supabase.co \
     -U postgres \
     -d nexus_restore_temp \
     -c "\dt"  # Listar tablas

# 6. Si todo OK, renombrar DBs
# (Requiere acceso a Supabase Dashboard)
# Dashboard → Database → Settings → Restore from backup
```

---

### Respuesta a Compromiso

#### 1. DETECCIÓN

**Señales de alerta:**
- Login desde ubicación inusual
- Cambios no autorizados en código
- Emails de "nueva sesión" que no iniciaste
- Actividad sospechosa en logs de Supabase

---

#### 2. CONTENCIÓN INMEDIATA (Primeros 5 minutos)

```bash
# A. Cambiar TODAS las contraseñas
# - GitHub
# - Vercel  
# - Supabase
# - Email (segoviaranonis@gmail.com)

# B. Revocar tokens de acceso
# GitHub: Settings → Developer settings → Personal access tokens → Revoke all
# Vercel: Settings → Tokens → Delete all
# Supabase: Dashboard → Settings → API → Regenerate keys

# C. Cerrar todas las sesiones activas
# GitHub: Settings → Sessions → Revoke all
# Vercel: Settings → Sessions → Sign out all devices
```

---

#### 3. INVESTIGACIÓN (Primeros 30 minutos)

```bash
# A. Revisar logs de Supabase
# Dashboard → Logs → Database
# Buscar: DROP, DELETE, UPDATE, INSERT sospechosos

# B. Revisar commits recientes
git log --all --since="24 hours ago" --author=".*" --oneline

# C. Revisar deploys en Vercel
# Dashboard → Deployments → Últimas 24 horas

# D. Revisar usuarios de Supabase
SELECT id_usuario, descp_usuario, created_at 
FROM usuario_v2 
WHERE created_at > NOW() - INTERVAL '24 hours';
```

---

#### 4. REMEDIACIÓN

```bash
# A. Restaurar desde backup si hay daño
# (Ver sección "Recuperación de Base de Datos")

# B. Revertir commits maliciosos
git revert <commit-hash>
git push origin main --force  # Solo si es absolutamente necesario

# C. Regenerar SERVICE_ROLE_KEY
# Supabase Dashboard → Settings → API → Service role secret → Regenerate
# Actualizar en:
# - Vercel env vars
# - Streamlit secrets
# - Local .streamlit/secrets.toml
```

---

#### 5. PREVENCIÓN FUTURA

```bash
# Activar 2FA en TODAS las cuentas
# - GitHub: Settings → Password and authentication → Enable 2FA
# - Vercel: Settings → Security → Enable 2FA
# - Supabase: Account → Security → Enable 2FA
# - Gmail: Seguridad → Verificación en 2 pasos

# Revisar accesos autorizados
# GitHub: Settings → Applications → Authorized OAuth Apps
# Revocar apps sospechosas
```

---

### Recuperación de Servicio

#### Vercel Down

```bash
# 1. Verificar status
curl -I https://rimec-web.vercel.app
# o visitar: https://www.vercel-status.com/

# 2. Si es problema de Vercel (su infraestructura)
# - Esperar (no hay nada que hacer)
# - Monitorear: https://twitter.com/vercel

# 3. Si es problema de deploy
# Vercel Dashboard → rimec-web → Deployments → Redeploy
```

---

#### Supabase Down

```bash
# 1. Verificar status
curl https://status.supabase.com/api/v2/status.json

# 2. Si DB no responde
# Supabase Dashboard → Database → Restart database

# 3. Si persiste
# Contactar soporte: https://supabase.com/support
```

---

#### Streamlit Down

```bash
# 1. Verificar logs
# Streamlit Cloud → App → Logs

# 2. Reiniciar app
# Streamlit Cloud → App → Reboot

# 3. Si falla por dependencias
# Verificar requirements.txt
# Hacer commit con fix → Auto-redeploy
```

---

### Recuperación de Código

#### Revertir commit destructivo

```bash
# 1. Identificar commit problemático
git log --oneline -20

# 2. Revertir (crea nuevo commit que deshace cambios)
git revert <commit-hash>
git push origin main

# 3. Si necesitas volver a estado anterior (DESTRUCTIVO)
git reset --hard <commit-hash-bueno>
git push origin main --force  # ⚠️ Solo en emergencia
```

---

#### Restaurar desde backup privado

```bash
# (Cuando tengamos repo privado configurado)
git clone git@github.com:BACKUP-ACCOUNT/nexus-backup-privado.git
cd nexus-backup-privado
git log  # Verificar que tiene el código bueno
cp -r * /path/to/control_central/
cd /path/to/control_central
git add .
git commit -m "Restaurado desde backup privado"
git push origin main
```

---

## 📞 Contactos de Emergencia

### Responsable Principal
**Nombre:** Héctor Segovia  
**Email:** segoviaranonis@gmail.com  
**Rol:** Administrador de Sistemas

---

### Servicios de Soporte

**Supabase Support:**
- Portal: https://supabase.com/support
- Email: support@supabase.com
- Docs: https://supabase.com/docs

**Vercel Support:**
- Portal: https://vercel.com/help
- Twitter: @vercel
- Docs: https://vercel.com/docs

**GitHub Support:**
- Portal: https://support.github.com/
- Docs: https://docs.github.com/

---

## ✅ Checklist Post-Recuperación

Después de cualquier incidente, verificar:

### Recuperación de Datos
- [ ] Todos los datos restaurados correctamente
- [ ] Consultas SQL funcionan normalmente
- [ ] No hay datos faltantes
- [ ] Backups futuros funcionan

### Recuperación de Servicio
- [ ] Todas las apps funcionan (Vercel, Streamlit)
- [ ] Usuarios pueden loguearse
- [ ] Pueden hacer pedidos
- [ ] Pueden ver catálogo

### Seguridad
- [ ] Todas las contraseñas cambiadas
- [ ] 2FA activado en todas las cuentas
- [ ] Tokens/keys regenerados
- [ ] Logs revisados (no hay actividad sospechosa)

### Comunicación
- [ ] Director informado del incidente
- [ ] Usuarios notificados (si aplicable)
- [ ] Documentación actualizada
- [ ] Post-mortem escrito (qué pasó, por qué, cómo prevenirlo)

---

## 📝 Log de Incidentes

Registrar todos los incidentes aquí:

### Incidente #001 - [Fecha]
**Tipo:** [Nivel 1/2/3/4]  
**Descripción:** [Qué pasó]  
**Causa raíz:** [Por qué pasó]  
**Solución:** [Cómo se resolvió]  
**Prevención:** [Qué hacer para que no vuelva a pasar]  
**Responsable:** [Quién lo resolvió]

---

## 🔄 Mantenimiento de este Documento

- **Revisar:** Cada 3 meses
- **Actualizar:** Después de cada cambio de infraestructura
- **Probar:** Simular recuperación cada 6 meses

**Próxima revisión:** 2026-08-25

---

**📌 MANTENER ESTE DOCUMENTO ACTUALIZADO Y ACCESIBLE EN TODO MOMENTO**
