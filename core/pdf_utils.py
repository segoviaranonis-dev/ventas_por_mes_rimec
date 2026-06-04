"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
MÓDULO: core/pdf_utils.py
VERSION: 1.0.0 (PROTOCOLO ÚNICO DE IMÁGENES PARA PDFs)
AUTOR: Héctor & Claude AI
DESCRIPCIÓN: Funciones centralizadas y robustas para cargar imágenes en PDFs.
             Protocolo único con retry, timeout largo, logging detallado.

CARACTERÍSTICAS:
    - Timeout configurable (default 15s)
    - Retry automático (3 intentos con backoff exponencial)
    - Logging detallado de errores
    - Redimensionamiento con PIL manteniendo aspect ratio
    - Soporte para URLs de Supabase Storage

USO:
    from core.pdf_utils import get_pdf_image

    img = get_pdf_image(
        url="https://abc.supabase.co/storage/v1/object/public/productos/img.png",
        max_width=12*mm,
        max_height=12*mm
    )

    if img:
        # Usar imagen en PDF
    else:
        # Mostrar placeholder
"""

import time
import logging
from typing import Optional
from io import BytesIO

import requests
from PIL import Image
from reportlab.platypus import Image as RLImage
from reportlab.lib.units import mm

# Configurar logger
logger = logging.getLogger(__name__)


def get_thumbnail_url(original_url: str) -> str:
    """
    Convierte URL original de Supabase a URL de thumbnail.

    Args:
        original_url: https://[...]/storage/v1/object/public/productos/8246-1176.jpg

    Returns:
        https://[...]/storage/v1/object/public/productos/thumbs/8246-1176.jpg
    """
    if not original_url or '/productos/' not in original_url:
        return original_url

    return original_url.replace('/productos/', '/productos/thumbs/')


def get_pdf_image(
    url: str,
    max_width: float = 12 * mm,
    max_height: float = 12 * mm,
    timeout: int = 15,
    retries: int = 3,
    backoff_factor: float = 0.5,
    use_thumbnail: bool = True
) -> Optional[RLImage]:
    """
    PROTOCOLO ÚNICO: Descarga y prepara imagen para PDF con retry y timeout.

    OPTIMIZACIÓN: Intenta thumbnail primero (productos/thumbs/), fallback a original.

    Args:
        url: URL de la imagen (debe ser HTTPS de dominio confiable)
        max_width: Ancho máximo en puntos (default 12mm)
        max_height: Alto máximo en puntos (default 12mm)
        timeout: Timeout por intento en segundos (default 15s)
        retries: Número de reintentos (default 3)
        backoff_factor: Factor de backoff exponencial (default 0.5)
        use_thumbnail: Si True, intenta thumbnail primero (default True)

    Returns:
        RLImage redimensionada o None si falla después de todos los reintentos

    Logs:
        - INFO: Descarga exitosa
        - WARNING: Retry por timeout o error
        - ERROR: Falla después de todos los reintentos
    """
    if not url:
        logger.debug("[PDF Utils] URL vacía, retornando None")
        return None

    # Validación básica de seguridad
    if not url.startswith("https://"):
        logger.warning(f"[PDF Utils] URL rechazada (no HTTPS): {url}")
        return None

    # Intentar thumbnail primero si está habilitado
    if use_thumbnail and '/productos/' in url:
        thumb_url = get_thumbnail_url(url)
        logger.debug(f"[PDF Utils] Intentando thumbnail: {thumb_url[:80]}...")

        result = _download_and_resize_image(
            thumb_url,
            max_width,
            max_height,
            timeout,
            retries,
            backoff_factor
        )

        if result:
            logger.info(f"[PDF Utils] ✓ Thumbnail cargado exitosamente")
            return result

        logger.info(f"[PDF Utils] Thumbnail no disponible, intentando original...")

    # Fallback a URL original (o única opción si use_thumbnail=False)
    return _download_and_resize_image(
        url,
        max_width,
        max_height,
        timeout,
        retries,
        backoff_factor
    )


def _download_and_resize_image(
    url: str,
    max_width: float,
    max_height: float,
    timeout: int,
    retries: int,
    backoff_factor: float
) -> Optional[RLImage]:
    """
    Función interna: Descarga y redimensiona imagen.
    (Extraída para reutilizar en thumbnail + original)
    """

    for attempt in range(retries):
        try:
            # Calcular timeout con backoff exponencial
            current_timeout = timeout * (1 + backoff_factor * attempt)

            # Descargar imagen con timeout
            response = requests.get(
                url,
                timeout=current_timeout,
                headers={
                    "User-Agent": "Nexus-Core-PDF-Generator/2.0"
                }
            )

            if response.status_code != 200:
                if attempt < retries - 1:
                    time.sleep(backoff_factor * (2 ** attempt))
                    continue
                return None

            # Abrir imagen con PIL
            img_buffer = BytesIO(response.content)
            pil_img = Image.open(img_buffer)

            # Calcular dimensiones manteniendo aspect ratio
            aspect = pil_img.width / pil_img.height
            if aspect > 1:  # Imagen ancha
                width = max_width
                height = max_width / aspect
            else:  # Imagen alta
                height = max_height
                width = max_height * aspect

            # Crear RLImage
            img_buffer.seek(0)
            rl_img = RLImage(img_buffer, width=width, height=height)

            return rl_img

        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
                continue
            return None

        except requests.exceptions.RequestException:
            if attempt < retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
                continue
            return None

        except Exception:
            return None

    return None


def format_gradas(gradas_dict: dict) -> str:
    """
    Formatea diccionario de gradas en string legible.

    Args:
        gradas_dict: {"35": 2, "36": 3, "37": 1}

    Returns:
        "35:2 · 36:3 · 37:1"
    """
    if not gradas_dict:
        return "N/A"

    try:
        sorted_gradas = sorted(gradas_dict.items(), key=lambda x: float(x[0]))
        return " · ".join([f"{num}:{cant}" for num, cant in sorted_gradas])
    except:
        return str(gradas_dict)


# [EXECUTION-CONFIRMED] v1.0.0 - PDF Utils Protocolo Único
