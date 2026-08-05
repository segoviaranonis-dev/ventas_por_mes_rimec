# Moises — Sistema de respaldo DB (canónico) · actualización de datos

**Código:** etapa `MOISES-20260804` · evidencia rueda de auxilio  
**Fecha:** 2026-08-04 · orden Director  
**Shibboleth:** Andrés, el que viene. Protocolo Moises Activado.

---

## Qué dice la documentación (verdad holding)

El sistema de respaldo de la base (Supabase / PostgreSQL) **ya está diseñado** en Control Central:

| Pieza | Ruta |
|-------|------|
| Script | `control_central/scripts/seguridad/backup_db_automatico.py` |
| Automatización | `control_central/.github/workflows/backup-diario.yml` |
| Lección incendio | error **4.90.01.001** (billing) — backup diario debe estar **activo y descargable** |

### Cómo funciona

1. Lee credenciales de `.streamlit/secrets.toml` → sección `[postgres]` (local) **o** secrets GitHub (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) en Actions.  
2. Ejecuta **`pg_dump`** (dump completo, plain SQL, `--no-owner` / `--no-privileges`).  
3. Comprime a **`backup_YYYYMMDD_HHMMSS.sql.gz`**.  
4. Guarda en `control_central/backups/db/` (local) y/o **GitHub Artifacts** (retención **30 días**).  
5. Cron Actions: **03:00 UTC** diario + `workflow_dispatch` (manual).

### Qué **no** es el respaldo

- No es “volver a importar Excel”.  
- No es clonar el repo git (el código ≠ los datos).  
- Supabase PITR del plan (si está activo en el proyecto) es **capa cloud adicional**; el holding canónico documentado para mudanza Moises es el **dump `pg_dump` + artifact**.

---

## Actualizar datos (orilla nueva / PC aislada / TEST)

**Esto es lo que hay que hacer con los datos:**

```
OPS (hoy)                         Orilla nueva / TEST / restore
─────────                         ────────────────────────────
pg_dump → .sql.gz    ──copia──►   gunzip + psql restore
(o Artifact GH)                   hacia proyecto Supabase destino
```

| Paso | Acción |
|------|--------|
| 1 | Generar backup fresco (`python scripts/seguridad/backup_db_automatico.py` o Actions → Run workflow) |
| 2 | Descargar `.sql.gz` (local `backups/db/` o Artifact) — **cofre Director**, nunca commit del dump |
| 3 | En destino: crear proyecto Supabase / DB vacía (o TEST) |
| 4 | `gunzip` + `psql -h … -U … -d … -f backup_….sql` |
| 5 | Smoke: login apps + conteo tablas críticas (`v_stock_rimec`, FI, etc.) |
| 6 | Apuntar `.env` / Vercel env de la orilla nueva a esa DB |

**Regla Moises:** sin dump recuperable **antes** del cutover = **no** cutover (Carta · rueda de auxilio).

---

## Deploy del sistema de respaldo (parte Moises)

| # | Entregable | Estado |
|---|------------|--------|
| A | Script + workflow en git `segoviaranonis-dev/ventas_por_mes_rimec` (`main`) | ✅ (sync Moises) |
| B | Secrets GH Actions `DB_*` configurados en el repo | ⏳ verificar Director / Claude |
| C | Workflow diario activo + corrida manual | ⏳ |
| D | Dump fresco local o Artifact para rueda PC aislada | ⏳ ejecutar en este turno si hay `pg_dump` |
| E | Prohibido: subir `.sql.gz` a git público | ✅ ley |

---

## Restaurar (comando canónico)

```bash
gunzip backup_YYYYMMDD_HHMMSS.sql.gz
psql -h HOST -U USER -d DATABASE -f backup_YYYYMMDD_HHMMSS.sql
```

(Host/user/db desde cofre — no documentar valores aquí.)

---

## Referencias

- `4.90.01.001_supabase-proyecto-bloqueado-facturacion.md`  
- [ETAPA_MOISES_20260804.md](./ETAPA_MOISES_20260804.md) · Fase 0.3  
- [ETAPA_MOISES_CARTA_CONSTITUCION_20260804.md](./ETAPA_MOISES_CARTA_CONSTITUCION_20260804.md)

**Documentado en Moises — el camino de datos = dump/restore, no “solo git”.**
