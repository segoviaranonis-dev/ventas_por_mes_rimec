"""
convertir_miniaturas_retail.py

Convierte imágenes de productos a miniaturas optimizadas para web.

Flujo:
1. Lee imágenes de carpeta origen (fotos full-size)
2. Genera miniaturas en múltiples tamaños
3. Optimiza para web (compresión JPEG, calidad 85)
4. Guarda en carpeta destino

Tamaños generados:
- thumb_200  → 200x200px (grid, listados)
- thumb_400  → 400x400px (tarjetas, preview)
- thumb_800  → 800x800px (modal, zoom)

Requisitos:
- Python 3.11+
- Pillow (PIL)

Uso:
  python tools/convertir_miniaturas_retail.py

Con rutas personalizadas:
  python tools/convertir_miniaturas_retail.py --origen D:\Fotos --destino D:\Thumbs
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Falta instalar Pillow. Ejecuta: python -m pip install Pillow"
    ) from exc


DEFAULT_ORIGEN = r"C:\Users\hecto\Documents\Prg_locales\proyectos\imagenes"
DEFAULT_DESTINO = r"C:\Users\hecto\Documents\Prg_locales\proyectos\miniaturas"

TAMANIOS = {
    "thumb_200": 200,
    "thumb_400": 400,
    "thumb_800": 800,
}

CALIDAD_JPEG = 85
EXTENSIONES_PERMITIDAS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class ConversionResult:
    origen: Path
    nombre: str
    tamanio_origen: int  # bytes
    tamanio_200: int
    tamanio_400: int
    tamanio_800: int
    duracion_ms: int
    error: str | None


def es_imagen(path: Path) -> bool:
    """Verifica si un archivo es una imagen válida."""
    return path.suffix.lower() in EXTENSIONES_PERMITIDAS


def crear_miniatura(
    imagen_origen: Image.Image,
    tamanio: int,
    destino: Path,
    calidad: int = CALIDAD_JPEG
) -> int:
    """
    Crea miniatura cuadrada con crop centrado.

    Args:
        imagen_origen: Imagen PIL abierta
        tamanio: Tamaño del lado (cuadrado)
        destino: Path donde guardar
        calidad: Calidad JPEG (0-100)

    Returns:
        Tamaño en bytes del archivo generado
    """
    # Crop centrado cuadrado
    width, height = imagen_origen.size
    size = min(width, height)

    left = (width - size) // 2
    top = (height - size) // 2
    right = left + size
    bottom = top + size

    img_cuadrada = imagen_origen.crop((left, top, right, bottom))

    # Resize con antialias de alta calidad
    img_thumb = img_cuadrada.resize((tamanio, tamanio), Image.Resampling.LANCZOS)

    # Convertir a RGB si es RGBA (para JPEG)
    if img_thumb.mode == "RGBA":
        rgb_img = Image.new("RGB", img_thumb.size, (255, 255, 255))
        rgb_img.paste(img_thumb, mask=img_thumb.split()[3])  # Alpha como mask
        img_thumb = rgb_img

    # Guardar como JPEG optimizado
    destino.parent.mkdir(parents=True, exist_ok=True)
    img_thumb.save(
        destino,
        format="JPEG",
        quality=calidad,
        optimize=True,
        progressive=True
    )

    return destino.stat().st_size


def convertir_imagen(
    path_origen: Path,
    dir_destino: Path,
    tamanios: dict[str, int],
    calidad: int
) -> ConversionResult:
    """
    Convierte una imagen a múltiples tamaños de miniatura.

    Args:
        path_origen: Archivo imagen origen
        dir_destino: Directorio base destino
        tamanios: Dict {nombre: tamanio} ej: {"thumb_200": 200}
        calidad: Calidad JPEG

    Returns:
        ConversionResult con detalles del proceso
    """
    t0 = time.time()
    nombre_base = path_origen.stem
    tamanio_origen = path_origen.stat().st_size

    try:
        # Abrir imagen origen
        with Image.open(path_origen) as img:
            # Generar miniaturas
            tamanios_generados = {}

            for nombre_tamanio, px in tamanios.items():
                # Nombre: original.jpg → thumb_200/original.jpg
                destino = dir_destino / nombre_tamanio / f"{nombre_base}.jpg"
                bytes_generados = crear_miniatura(img, px, destino, calidad)
                tamanios_generados[nombre_tamanio] = bytes_generados

        duracion_ms = int((time.time() - t0) * 1000)

        return ConversionResult(
            origen=path_origen,
            nombre=path_origen.name,
            tamanio_origen=tamanio_origen,
            tamanio_200=tamanios_generados.get("thumb_200", 0),
            tamanio_400=tamanios_generados.get("thumb_400", 0),
            tamanio_800=tamanios_generados.get("thumb_800", 0),
            duracion_ms=duracion_ms,
            error=None
        )

    except Exception as e:
        duracion_ms = int((time.time() - t0) * 1000)
        return ConversionResult(
            origen=path_origen,
            nombre=path_origen.name,
            tamanio_origen=tamanio_origen,
            tamanio_200=0,
            tamanio_400=0,
            tamanio_800=0,
            duracion_ms=duracion_ms,
            error=str(e)
        )


def procesar_carpeta(
    dir_origen: Path,
    dir_destino: Path,
    tamanios: dict[str, int],
    calidad: int
) -> list[ConversionResult]:
    """
    Procesa todas las imágenes de una carpeta.

    Args:
        dir_origen: Carpeta con imágenes originales
        dir_destino: Carpeta base donde crear miniaturas
        tamanios: Tamaños a generar
        calidad: Calidad JPEG

    Returns:
        Lista de resultados de conversión
    """
    # Buscar imágenes (solo en nivel raíz, no recursivo)
    imagenes = [f for f in dir_origen.iterdir() if f.is_file() and es_imagen(f)]

    if not imagenes:
        print(f"⚠️  No se encontraron imágenes en {dir_origen}")
        return []

    print(f"\n📷 Procesando {len(imagenes)} imágenes...")
    print(f"   Origen: {dir_origen}")
    print(f"   Destino: {dir_destino}")
    print(f"   Tamaños: {', '.join(f'{t}px' for t in tamanios.values())}")
    print(f"   Calidad: {calidad}%\n")

    resultados: list[ConversionResult] = []

    for i, img_path in enumerate(imagenes, 1):
        print(f"[{i}/{len(imagenes)}] {img_path.name}...", end=" ", flush=True)

        resultado = convertir_imagen(img_path, dir_destino, tamanios, calidad)
        resultados.append(resultado)

        if resultado.error:
            print(f"❌ Error: {resultado.error}")
        else:
            # Mostrar reducción de tamaño
            reduccion = (1 - resultado.tamanio_200 / resultado.tamanio_origen) * 100
            print(f"✅ {resultado.duracion_ms}ms (reducción: {reduccion:.0f}%)")

    return resultados


def generar_reporte(
    resultados: list[ConversionResult],
    output_dir: Path
) -> None:
    """
    Genera CSV con estadísticas de conversión.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "conversion_miniaturas.csv"

    print(f"\n📊 Generando reporte: {csv_path}")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "imagen",
            "tamanio_origen_bytes",
            "tamanio_200_bytes",
            "tamanio_400_bytes",
            "tamanio_800_bytes",
            "reduccion_200_pct",
            "duracion_ms",
            "error"
        ])

        for r in resultados:
            reduccion = 0
            if r.tamanio_origen > 0:
                reduccion = (1 - r.tamanio_200 / r.tamanio_origen) * 100

            writer.writerow([
                r.nombre,
                r.tamanio_origen,
                r.tamanio_200,
                r.tamanio_400,
                r.tamanio_800,
                f"{reduccion:.1f}",
                r.duracion_ms,
                r.error or ""
            ])

    print("  ✅ Reporte generado")


def mostrar_resumen(resultados: list[ConversionResult]) -> None:
    """
    Muestra resumen de estadísticas.
    """
    if not resultados:
        return

    exitosos = [r for r in resultados if not r.error]
    fallidos = [r for r in resultados if r.error]

    print("\n" + "="*70)
    print("📊 RESUMEN DE CONVERSIÓN")
    print("="*70)

    print(f"\n✅ Exitosas: {len(exitosos)}/{len(resultados)}")
    if fallidos:
        print(f"❌ Fallidas:  {len(fallidos)}/{len(resultados)}")

    if exitosos:
        # Estadísticas
        total_origen = sum(r.tamanio_origen for r in exitosos)
        total_200 = sum(r.tamanio_200 for r in exitosos)
        total_400 = sum(r.tamanio_400 for r in exitosos)
        total_800 = sum(r.tamanio_800 for r in exitosos)

        duracion_promedio = sum(r.duracion_ms for r in exitosos) / len(exitosos)
        reduccion_promedio = (1 - total_200 / total_origen) * 100 if total_origen > 0 else 0

        print(f"\n📏 Tamaño total:")
        print(f"   Origen:     {total_origen / 1024 / 1024:.1f} MB")
        print(f"   Thumb 200:  {total_200 / 1024 / 1024:.1f} MB (reducción: {reduccion_promedio:.0f}%)")
        print(f"   Thumb 400:  {total_400 / 1024 / 1024:.1f} MB")
        print(f"   Thumb 800:  {total_800 / 1024 / 1024:.1f} MB")

        print(f"\n⏱️  Velocidad:")
        print(f"   Promedio: {duracion_promedio:.0f}ms por imagen")
        print(f"   Total: {sum(r.duracion_ms for r in exitosos) / 1000:.1f}s")

    if fallidos:
        print(f"\n❌ Imágenes con error:")
        for r in fallidos[:10]:  # Mostrar max 10
            print(f"   - {r.nombre}: {r.error}")
        if len(fallidos) > 10:
            print(f"   ... y {len(fallidos) - 10} más")

    print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Convertir imágenes a miniaturas")
    parser.add_argument(
        "--origen",
        type=str,
        default=DEFAULT_ORIGEN,
        help=f"Carpeta origen con imágenes (default: {DEFAULT_ORIGEN})"
    )
    parser.add_argument(
        "--destino",
        type=str,
        default=DEFAULT_DESTINO,
        help=f"Carpeta destino para miniaturas (default: {DEFAULT_DESTINO})"
    )
    parser.add_argument(
        "--calidad",
        type=int,
        default=CALIDAD_JPEG,
        help=f"Calidad JPEG 0-100 (default: {CALIDAD_JPEG})"
    )
    parser.add_argument(
        "--tamanios",
        type=str,
        default="200,400,800",
        help="Tamaños separados por coma (default: 200,400,800)"
    )
    args = parser.parse_args()

    print("\n" + "="*70)
    print("CONVERSOR DE MINIATURAS - RETAIL")
    print("="*70)

    # Validar origen
    dir_origen = Path(args.origen)
    if not dir_origen.exists():
        print(f"\n❌ ERROR: Carpeta origen no existe: {dir_origen}")
        return 1

    if not dir_origen.is_dir():
        print(f"\n❌ ERROR: Origen no es un directorio: {dir_origen}")
        return 1

    # Preparar destino
    dir_destino = Path(args.destino)

    # Parsear tamaños
    try:
        tamanios_lista = [int(t.strip()) for t in args.tamanios.split(",")]
        tamanios_dict = {f"thumb_{t}": t for t in tamanios_lista}
    except ValueError:
        print(f"\n❌ ERROR: Tamaños inválidos: {args.tamanios}")
        print("   Usa números separados por coma, ej: 200,400,800")
        return 1

    # Procesar
    resultados = procesar_carpeta(
        dir_origen,
        dir_destino,
        tamanios_dict,
        args.calidad
    )

    if not resultados:
        return 0

    # Generar reporte
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reporte_dir = Path.cwd() / "reportes_miniaturas" / timestamp
    generar_reporte(resultados, reporte_dir)

    # Mostrar resumen
    mostrar_resumen(resultados)

    print(f"✅ Proceso completado")
    print(f"📁 Miniaturas en: {dir_destino}")
    print(f"📁 Reporte en: {reporte_dir}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
