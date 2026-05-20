"""
Herencia jerárquica para línea nueva (§3.1 regla .mdc).

Protocolo de agregación jerárquica:
  - Si línea nueva NO trae género/marca/estilo/tipo_1
  - Buscar línea plantilla: mayor codigo_proveedor < L (mismo proveedor)
  - Heredar: genero, marca, grupo_estilo, tipo_1
  - Si no hay plantilla: usar catálogo por defecto (OTROS)

Aplicable a:
  - Listado de Precios (§3.1)
  - Facturas Proformas (§4.3)
  - Retail (§5.4)
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


def aplicar_herencia_linea(
    conn: Connection,
    nuevo_codigo_proveedor: str,
    proveedor_id: int,
    *,
    marca_id: int | None = None,
    genero_id: int | None = None,
    grupo_estilo_id: int | None = None,
) -> dict[str, int | None]:
    """
    Aplica herencia jerárquica para línea nueva sin dimensiones.

    Args:
        conn: Conexión SQLAlchemy
        nuevo_codigo_proveedor: Código de la línea nueva
        proveedor_id: FK proveedor_importacion
        marca_id: Si ya tiene, no hereda
        genero_id: Si ya tiene, no hereda
        grupo_estilo_id: Si ya tiene, no hereda

    Returns:
        {
            "marca_id": int | None,
            "genero_id": int | None,
            "grupo_estilo_id": int | None,
        }

    Lógica:
      1. Si los 3 ya vienen, retornar sin cambios
      2. Buscar línea plantilla: MAX(codigo_proveedor) WHERE codigo < nuevo_codigo
      3. Heredar los que faltan
      4. Si no hay plantilla: usar sentinelas "OTROS" (marca=-999001, genero=NULL, estilo=NULL)
    """
    # TODO: Implementación completa en fase 2 de OT
    # Por ahora, devuelve los valores entrantes sin modificar
    return {
        "marca_id": marca_id,
        "genero_id": genero_id,
        "grupo_estilo_id": grupo_estilo_id,
    }


def _buscar_linea_plantilla(
    conn: Connection,
    codigo_proveedor_nuevo: str,
    proveedor_id: int,
) -> dict[str, int | None] | None:
    """
    Busca línea plantilla (mayor codigo < nuevo) para herencia.

    Returns:
        {"marca_id": ..., "genero_id": ..., "grupo_estilo_id": ...} o None
    """
    # TODO: Implementación SQL
    return None


def _obtener_sentinelas_otros(conn: Connection) -> dict[str, int | None]:
    """
    Devuelve FKs del catálogo por defecto "OTROS".

    Returns:
        {"marca_id": -999001, "genero_id": None, "grupo_estilo_id": None}
    """
    # TODO: Query real a marca_v2, genero, grupo_estilo_v2
    return {
        "marca_id": -999001,  # Sentinela RETAIL_OTROS
        "genero_id": None,
        "grupo_estilo_id": None,
    }
