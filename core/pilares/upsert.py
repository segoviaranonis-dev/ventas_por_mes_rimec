"""
Upsert idempotente de pilares (§8 regla .mdc).

API mínima mandatoria:
  - upsert_linea()
  - upsert_referencia()
  - upsert_material()
  - upsert_color()

Comportamiento garantizado:
  - Idempotencia: mismo input → mismo id, no duplica
  - Transaccional: un fallo en una fila no aborta el lote
  - Devuelve id del pilar para usar como FK aguas abajo
  - Honra regla no inversa (enriquecimiento.py)
  - Aplica herencia jerárquica para línea (herencia.py)

TODO: Implementación completa en fase 2 de OT.
      Por ahora, placeholders que mantienen firma API.
"""
from __future__ import annotations

from typing import Literal
from sqlalchemy.engine import Connection

from .enriquecimiento import aplicar_enriquecimiento_no_inverso


def upsert_material(
    conn: Connection,
    codigo_proveedor: str,
    proveedor_id: int,
    *,
    descripcion: str | None = None,
    fuente: Literal["listado", "proforma", "retail"],
) -> int:
    """
    Upsert material por codigo_proveedor.

    Args:
        conn: Conexión SQLAlchemy
        codigo_proveedor: Código numérico del proveedor
        proveedor_id: FK a proveedor_importacion
        descripcion: Descripción opcional (aplica regla no inversa)
        fuente: Fuente de datos ("listado", "proforma", "retail")

    Returns:
        material.id (int)

    Lógica:
      1. SELECT por (codigo_proveedor, proveedor_id)
      2. Si existe: aplicar enriquecimiento no inverso si descripcion != None
      3. Si no existe: INSERT con descripcion (puede ser NULL)
      4. Devolver id
    """
    # TODO: Implementar lógica completa
    # Placeholder: devuelve -1 hasta fase 2
    raise NotImplementedError("upsert_material en fase 2 de OT")


def upsert_color(
    conn: Connection,
    codigo_proveedor: str,
    proveedor_id: int,
    *,
    nombre: str | None = None,
    hex_web: str | None = None,
    fuente: Literal["listado", "proforma", "retail"],
) -> int:
    """
    Upsert color por codigo_proveedor.

    Args:
        conn: Conexión SQLAlchemy
        codigo_proveedor: Código numérico del proveedor
        proveedor_id: FK a proveedor_importacion
        nombre: Nombre/descripción opcional (aplica regla no inversa)
        hex_web: Hex color web opcional
        fuente: Fuente de datos

    Returns:
        color.id (int)
    """
    raise NotImplementedError("upsert_color en fase 2 de OT")


def upsert_linea(
    conn: Connection,
    codigo_proveedor: str,
    proveedor_id: int,
    *,
    descripcion: str | None = None,
    marca_id: int | None = None,
    genero_id: int | None = None,
    grupo_estilo_id: int | None = None,
    caso_id: int | None = None,
    fuente: Literal["listado", "proforma", "retail"],
) -> int:
    """
    Upsert línea por codigo_proveedor.

    Si es nueva y no trae dimensiones (marca/genero/estilo), aplica
    herencia jerárquica (§3.1 regla) vía herencia.py::aplicar_herencia_linea.

    Returns:
        linea.id (int)
    """
    raise NotImplementedError("upsert_linea en fase 2 de OT")


def upsert_referencia(
    conn: Connection,
    codigo_proveedor: str,
    linea_id: int,
    proveedor_id: int,
    *,
    descripcion: str | None = None,
    fuente: Literal["listado", "proforma", "retail"],
) -> int:
    """
    Upsert referencia por (linea_id, codigo_proveedor).

    Returns:
        referencia.id (int)
    """
    raise NotImplementedError("upsert_referencia en fase 2 de OT")
