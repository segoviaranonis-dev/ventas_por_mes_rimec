#!/usr/bin/env python3
"""
Sube imagenes masivamente a Supabase Storage usando API REST directa
Sin dependencias pesadas - solo requests
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import requests

# Cargar .env
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
BUCKET = 'productos'

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env")
    sys.exit(1)


class Latido:
    def __init__(self):
        self.inicio = time.time()
        self.ultimo = self.inicio
        self.tick = 0

    def pulso(self, msg=""):
        ahora = time.time()
        if ahora - self.ultimo >= 60:
            self.tick += 1
            mins, secs = divmod(int(ahora - self.inicio), 60)
            print(f"\n💓 LATIDO {self.tick} — {mins}m {secs}s {msg}")
            self.ultimo = ahora


def subir_imagen(archivo_path, latido):
    """Sube una imagen usando Supabase Storage REST API"""
    try:
        latido.pulso(f"— {archivo_path.name}")

        nombre = archivo_path.name
        url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{nombre}"

        headers = {
            'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
            'Content-Type': 'image/jpeg'
        }

        with open(archivo_path, 'rb') as f:
            contenido = f.read()

        # POST para crear nuevo archivo
        resp = requests.post(url, headers=headers, data=contenido)

        # Si ya existe (409), intentar actualizar con PUT
        if resp.status_code == 409:
            resp = requests.put(url, headers=headers, data=contenido)

        if resp.status_code in [200, 201]:
            return True, ""
        else:
            return False, f"HTTP {resp.status_code}: {resp.text[:100]}"

    except Exception as e:
        return False, str(e)[:100]


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else None
    if not carpeta:
        print("Uso: python subir_imagenes_supabase.py <carpeta>")
        sys.exit(1)

    carpeta_path = Path(carpeta)
    if not carpeta_path.exists():
        print(f"ERROR: Carpeta no existe: {carpeta}")
        sys.exit(1)

    print("╔════════════════════════════════════════════════════════════════╗")
    print("║        IMPORTADOR IMÁGENES SUPABASE STORAGE (API REST)        ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"\n📁 Origen:  {carpeta}")
    print(f"☁️  Destino: {BUCKET}")
    print(f"🔗 URL:     {SUPABASE_URL}\n")

    # En Windows, glob es case-insensitive, usar solo *.jpg
    imagenes = sorted(list(carpeta_path.glob("*.jpg")))
    total = len(imagenes)

    if total == 0:
        print("ERROR: No hay imágenes .jpg en la carpeta")
        sys.exit(1)

    print(f"✅ Encontradas: {total:,} imágenes\n")
    print("─" * 60)

    resp = input(f"\n¿Subir {total:,} imágenes? (s/n): ").strip().lower()
    if resp != 's':
        print("Cancelado")
        sys.exit(0)

    print("\n🚀 Iniciando...\n")

    latido = Latido()
    exitosas = 0
    fallidas = 0
    errores = []

    for idx, img in enumerate(imagenes, 1):
        if idx % 10 == 0 or idx == total:
            pct = (idx / total) * 100
            print(f"📤 [{idx:>5}/{total}] {pct:>5.1f}% — {img.name[:50]}")

        ok, error = subir_imagen(img, latido)

        if ok:
            exitosas += 1
        else:
            fallidas += 1
            errores.append({'archivo': img.name, 'error': error})
            print(f"    ❌ {error}")

    print("\n")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                     IMPORTACIÓN COMPLETADA                     ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"\n📊 RESUMEN:")
    print(f"   Total:      {total:>6,}")
    print(f"   ✅ Exitosas: {exitosas:>6,}")
    print(f"   ❌ Fallidas: {fallidas:>6,}")

    mins, secs = divmod(int(time.time() - latido.inicio), 60)
    print(f"\n⏱️  Tiempo: {mins}m {secs}s")

    if exitosas > 0 and mins > 0:
        rate = exitosas / mins
        print(f"⚡ Velocidad: {rate:.1f} img/min")

    if errores:
        print(f"\n⚠️  ERRORES ({len(errores)}):")
        for e in errores[:10]:
            print(f"   • {e['archivo']}: {e['error']}")
        if len(errores) > 10:
            print(f"   ... y {len(errores) - 10} más")

    print(f"\n🔗 {SUPABASE_URL}/storage/buckets/{BUCKET}")
    print("\n✨ Listo\n")

    sys.exit(0 if fallidas == 0 else 1)


if __name__ == '__main__':
    main()
