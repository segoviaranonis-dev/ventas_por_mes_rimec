#!/usr/bin/env python3
"""
Backup automático diario de PostgreSQL (Supabase)
Ejecutar con GitHub Actions o cron diariamente

Características:
- Exporta dump completo de la DB
- Comprime con gzip
- Sube a Google Drive (opcional) o guarda local
- Retiene últimos 30 backups
- Notifica por email si falla

Uso:
    python backup_db_automatico.py
    python backup_db_automatico.py --upload-drive  # Sube a Google Drive
"""
from __future__ import annotations

import os
import sys
import gzip
import shutil
import smtplib
from pathlib import Path
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote_plus
import subprocess

# Configuración
ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups" / "db"
RETENTION_DAYS = 30  # Mantener backups de últimos 30 días

def _load_db_config():
    """Carga configuración de DB desde secrets.toml"""
    secrets_file = ROOT / ".streamlit" / "secrets.toml"
    if not secrets_file.exists():
        raise FileNotFoundError(f"No se encuentra {secrets_file}")

    import tomllib
    with secrets_file.open("rb") as f:
        config = tomllib.load(f)

    pg = config.get("postgres", {})
    return {
        "host": pg.get("host", "localhost"),
        "port": pg.get("port", 5432),
        "database": pg.get("database") or pg.get("dbname"),
        "user": pg.get("user") or pg.get("username"),
        "password": pg.get("password"),
    }

def crear_backup() -> Path:
    """Crea backup de PostgreSQL usando pg_dump"""
    print("=" * 80)
    print("BACKUP AUTOMÁTICO DE BASE DE DATOS")
    print("=" * 80)

    # Crear directorio de backups
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Cargar configuración
    db_config = _load_db_config()

    # Nombre del archivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"backup_{timestamp}.sql"
    backup_file_gz = BACKUP_DIR / f"backup_{timestamp}.sql.gz"

    print(f"\n[1/4] Creando backup de DB: {db_config['database']}")
    print(f"      Host: {db_config['host']}")
    print(f"      Archivo: {backup_file}")

    # Establecer variable de entorno para password
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["password"]

    # Ejecutar pg_dump
    cmd = [
        "pg_dump",
        "-h", db_config["host"],
        "-p", str(db_config["port"]),
        "-U", db_config["user"],
        "-d", db_config["database"],
        "-F", "p",  # Plain text format
        "-f", str(backup_file),
        "--no-owner",
        "--no-privileges",
    ]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"      ✓ Backup creado exitosamente")
    except subprocess.CalledProcessError as e:
        print(f"      ✗ Error al crear backup:")
        print(f"        {e.stderr}")
        raise
    except FileNotFoundError:
        print(f"      ✗ ERROR: pg_dump no encontrado")
        print(f"        Instalar PostgreSQL client:")
        print(f"        - Windows: https://www.postgresql.org/download/windows/")
        print(f"        - Linux: sudo apt-get install postgresql-client")
        print(f"        - Mac: brew install postgresql")
        raise

    # Comprimir con gzip
    print(f"\n[2/4] Comprimiendo backup...")
    with open(backup_file, "rb") as f_in:
        with gzip.open(backup_file_gz, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    # Eliminar archivo sin comprimir
    backup_file.unlink()

    size_mb = backup_file_gz.stat().st_size / (1024 * 1024)
    print(f"      ✓ Comprimido: {backup_file_gz.name} ({size_mb:.2f} MB)")

    return backup_file_gz

def limpiar_backups_antiguos():
    """Elimina backups más antiguos que RETENTION_DAYS"""
    print(f"\n[3/4] Limpiando backups antiguos (>{RETENTION_DAYS} días)...")

    if not BACKUP_DIR.exists():
        print("      (No hay directorio de backups)")
        return

    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    eliminados = 0

    for backup_file in BACKUP_DIR.glob("backup_*.sql.gz"):
        # Extraer timestamp del nombre
        try:
            timestamp_str = backup_file.stem.replace("backup_", "").replace(".sql", "")
            file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

            if file_date < cutoff_date:
                backup_file.unlink()
                eliminados += 1
                print(f"      ✗ Eliminado: {backup_file.name} ({file_date.date()})")
        except (ValueError, IndexError):
            print(f"      ? Ignorado (nombre inválido): {backup_file.name}")

    if eliminados == 0:
        print("      (No hay backups antiguos para eliminar)")
    else:
        print(f"      ✓ Eliminados {eliminados} backups antiguos")

def listar_backups():
    """Lista todos los backups disponibles"""
    print(f"\n[4/4] Backups disponibles:")

    if not BACKUP_DIR.exists() or not list(BACKUP_DIR.glob("backup_*.sql.gz")):
        print("      (No hay backups)")
        return

    backups = sorted(BACKUP_DIR.glob("backup_*.sql.gz"), reverse=True)
    total_size = 0

    for i, backup_file in enumerate(backups, 1):
        size_mb = backup_file.stat().st_size / (1024 * 1024)
        total_size += size_mb

        # Extraer fecha
        timestamp_str = backup_file.stem.replace("backup_", "").replace(".sql", "")
        try:
            file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            fecha_fmt = file_date.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            fecha_fmt = "fecha desconocida"

        print(f"      {i:2d}. {backup_file.name} ({size_mb:.2f} MB) - {fecha_fmt}")

    print(f"\n      Total: {len(backups)} backups, {total_size:.2f} MB")

def enviar_notificacion_error(error: str):
    """Envía email de notificación si el backup falla"""
    # TODO: Configurar SMTP
    print(f"\n⚠️  NOTIFICACIÓN DE ERROR (email no configurado):")
    print(f"    {error}")

def main():
    """Ejecuta backup completo"""
    try:
        backup_file = crear_backup()
        limpiar_backups_antiguos()
        listar_backups()

        print("\n" + "=" * 80)
        print("✓ BACKUP COMPLETADO EXITOSAMENTE")
        print("=" * 80)
        print(f"\nArchivo: {backup_file}")
        print(f"Ubicación: {backup_file.parent}")
        print("\nPara restaurar:")
        print(f"  gunzip {backup_file.name}")
        print(f"  psql -h HOST -U USER -d DATABASE -f backup_TIMESTAMP.sql")

        return 0

    except Exception as e:
        error_msg = f"Error en backup automático: {e}"
        print(f"\n✗ {error_msg}")
        enviar_notificacion_error(error_msg)
        return 1

if __name__ == "__main__":
    sys.exit(main())
