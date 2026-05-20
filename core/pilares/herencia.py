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
    # 1. Si ya tiene todas las dimensiones, no heredar
    if marca_id is not None and genero_id is not None and grupo_estilo_id is not None:
        return {
            "marca_id": marca_id,
            "genero_id": genero_id,
            "grupo_estilo_id": grupo_estilo_id,
        }

    # 2. Buscar línea plantilla para herencia
    plantilla = _buscar_linea_plantilla(conn, nuevo_codigo_proveedor, proveedor_id)

    if plantilla:
        # 3. Heredar dimensiones faltantes de plantilla
        return {
            "marca_id": marca_id if marca_id is not None else plantilla["marca_id"],
            "genero_id": genero_id if genero_id is not None else plantilla["genero_id"],
            "grupo_estilo_id": grupo_estilo_id if grupo_estilo_id is not None else plantilla["grupo_estilo_id"],
        }

    # 4. Sin plantilla: usar sentinelas OTROS
    sentinelas = _obtener_sentinelas_otros(conn)
    return {
        "marca_id": marca_id if marca_id is not None else sentinelas["marca_id"],
        "genero_id": genero_id if genero_id is not None else sentinelas["genero_id"],
        "grupo_estilo_id": grupo_estilo_id if grupo_estilo_id is not None else sentinelas["grupo_estilo_id"],
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
    codigo_nuevo_int = int(codigo_proveedor_nuevo)

    r = conn.execute(
        text("""
            SELECT marca_id, genero_id, grupo_estilo_id
            FROM linea
            WHERE proveedor_id = :prov
              AND codigo_proveedor < :codigo
              AND activo = TRUE
            ORDER BY codigo_proveedor DESC
            LIMIT 1
        """),
        {"prov": proveedor_id, "codigo": codigo_nuevo_int},
    ).fetchone()

    if r:
        return {
            "marca_id": r[0],
            "genero_id": r[1],
            "grupo_estilo_id": r[2],
        }

    return None


def _obtener_sentinelas_otros(conn: Connection) -> dict[str, int | None]:
    """
    Devuelve FKs del catálogo por defecto "OTROS".

    Returns:
        {"marca_id": -999001, "genero_id": None, "grupo_estilo_id": None}
    """
    # Buscar marca RETAIL_OTROS (sentinela -999001)
    r = conn.execute(
        text("""
            SELECT id
            FROM marca_v2
            WHERE nombre_v2 = 'RETAIL_OTROS'
               OR id = -999001
            LIMIT 1
        """),
    ).fetchone()

    marca_id = r[0] if r else -999001  # Fallback a sentinela conocida

    # Genero y grupo_estilo: NULL por defecto (sin sentinelas)
    return {
        "marca_id": marca_id,
        "genero_id": None,
        "grupo_estilo_id": None,
    }
