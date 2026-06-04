#!/usr/bin/env python3
"""
Importador masivo de imagenes a Supabase Storage
Sube imagenes desde carpeta local a bucket productos

Uso:
    python tools/importador_imagenes_supabase.py <ruta_carpeta>

Requisitos:
    - pip install supabase python-dotenv
    - .env con SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
from dotenv import load_dotenv
from supabase import create_client, Client

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
BUCKET_NAME = 'productos'

# Validar configuración
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ ERROR: Faltan variables de entorno SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

# Cliente Supabase con service role key para permisos de escritura
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


class Latido:
    """Heartbeat cada 60 segundos"""
    def __init__(self):
        self.inicio = time.time()
        self.ultimo_latido = self.inicio
        self.tick = 0

    def pulso(self, mensaje: str = ""):
        ahora = time.time()
        if ahora - self.ultimo_latido >= 60:
            self.tick += 1
            elapsed = int(ahora - self.inicio)
            mins = elapsed // 60
            secs = elapsed % 60
            print(f"\n💓 LATIDO {self.tick} — {mins}m {secs}s transcurridos {mensaje}")
            self.ultimo_latido = ahora


def listar_imagenes(carpeta: str) -> List[Path]:
    """Lista todos los archivos .jpg en la carpeta"""
    carpeta_path = Path(carpeta)
    if not carpeta_path.exists():
        print(f"❌ ERROR: Carpeta no existe: {carpeta}")
        sys.exit(1)

    imagenes = list(carpeta_path.glob("*.jpg")) + list(carpeta_path.glob("*.JPG"))
    return sorted(imagenes)


def subir_imagen(imagen_path: Path, latido: Latido) -> Tuple[bool, str]:
    """
    Sube una imagen a Supabase Storage bucket productos
    Retorna (éxito, mensaje_error)
    """
    try:
        latido.pulso(f"— subiendo {imagen_path.name}")

        # Leer archivo
        with open(imagen_path, 'rb') as f:
            contenido = f.read()

        # Nombre del archivo en el bucket (mismo nombre)
        nombre_destino = imagen_path.name

        # Subir a Supabase Storage
        # Nota: upload() sobrescribe si ya existe
        result = supabase.storage.from_(BUCKET_NAME).upload(
            path=nombre_destino,
            file=contenido,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )

        # Verificar resultado
        if hasattr(result, 'path') or isinstance(result, dict):
            return True, ""
        else:
            return False, f"Respuesta inesperada: {result}"

    except Exception as e:
        error_msg = str(e)
        # Si el error es "duplicate key", considerarlo éxito (ya existe)
        if "duplicate" in error_msg.lower() or "already exists" in error_msg.lower():
            return True, "ya_existe"
        return False, error_msg


def main():
    if len(sys.argv) < 2:
        print("Uso: python importador_imagenes_supabase.py <ruta_carpeta_imagenes>")
        sys.exit(1)

    carpeta_origen = sys.argv[1]

    print("╔════════════════════════════════════════════════════════════════╗")
    print("║   IMPORTADOR MASIVO DE IMÁGENES A SUPABASE STORAGE            ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"\n📁 Carpeta origen: {carpeta_origen}")
    print(f"☁️  Bucket destino: {BUCKET_NAME}")
    print(f"🔗 Supabase: {SUPABASE_URL}\n")

    # Listar imágenes
    print("📋 Listando imágenes...")
    imagenes = listar_imagenes(carpeta_origen)
    total = len(imagenes)

    if total == 0:
        print("❌ No se encontraron imágenes .jpg en la carpeta")
        sys.exit(1)

    print(f"✅ Encontradas {total:,} imágenes\n")
    print("─" * 60)

    # Confirmar antes de continuar
    resp = input(f"\n¿Subir {total:,} imágenes a Supabase? (s/n): ").strip().lower()
    if resp != 's':
        print("❌ Importación cancelada")
        sys.exit(0)

    print("\n🚀 Iniciando importación...\n")

    # Iniciar latido
    latido = Latido()

    # Contadores
    exitosas = 0
    ya_existian = 0
    fallidas = 0
    errores = []

    # Subir cada imagen
    for idx, imagen in enumerate(imagenes, 1):
        # Mostrar progreso cada 10 imágenes
        if idx % 10 == 0 or idx == total:
            porcentaje = (idx / total) * 100
            print(f"📤 [{idx:>5}/{total}] {porcentaje:>5.1f}% — {imagen.name[:50]}")

        exito, error = subir_imagen(imagen, latido)

        if exito:
            if error == "ya_existe":
                ya_existian += 1
            else:
                exitosas += 1
        else:
            fallidas += 1
            errores.append({
                'archivo': imagen.name,
                'error': error
            })
            print(f"    ❌ ERROR: {error[:100]}")

    # Reporte final
    print("\n")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                    IMPORTACIÓN COMPLETADA                      ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"\n📊 RESUMEN:")
    print(f"   Total procesadas:  {total:>6,}")
    print(f"   ✅ Exitosas:        {exitosas:>6,}")
    print(f"   ♻️  Ya existían:     {ya_existian:>6,}")
    print(f"   ❌ Fallidas:        {fallidas:>6,}")

    tiempo_total = int(time.time() - latido.inicio)
    mins = tiempo_total // 60
    secs = tiempo_total % 60
    print(f"\n⏱️  Tiempo total: {mins}m {secs}s")

    if exitosas + ya_existian > 0:
        rate = (exitosas + ya_existian) / (tiempo_total / 60) if tiempo_total > 0 else 0
        print(f"⚡ Velocidad: {rate:.1f} imágenes/minuto")

    # Mostrar errores si hubo
    if errores:
        print(f"\n⚠️  ERRORES DETECTADOS ({len(errores)}):")
        for e in errores[:10]:  # Mostrar máximo 10
            print(f"   • {e['archivo']}: {e['error'][:80]}")
        if len(errores) > 10:
            print(f"   ... y {len(errores) - 10} errores más")

    # URL de verificación
    print(f"\n🔗 Verificar en: {SUPABASE_URL}/storage/buckets/{BUCKET_NAME}")
    print("\n✨ Importación finalizada\n")

    # Exit code según resultado
    sys.exit(0 if fallidas == 0 else 1)


if __name__ == '__main__':
    main()
