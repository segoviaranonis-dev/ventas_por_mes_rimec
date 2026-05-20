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
"""
from __future__ import annotations

from typing import Literal
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .enriquecimiento import debe_actualizar_descripcion
from .herencia import aplicar_herencia_linea


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
    codigo_int = int(codigo_proveedor)

    # 1. Buscar existente
    r = conn.execute(
        text("""
            SELECT id, descripcion
            FROM material
            WHERE codigo_proveedor = :codigo AND proveedor_id = :prov
        """),
        {"codigo": codigo_int, "prov": proveedor_id},
    ).fetchone()

    if r:
        material_id, desc_actual = r
        # 2. Enriquecimiento no inverso
        if debe_actualizar_descripcion(desc_actual, descripcion):
            conn.execute(
                text("""
                    UPDATE material
                    SET descripcion = :desc
                    WHERE id = :id
                """),
                {"desc": (descripcion or "").strip(), "id": material_id},
            )
        return material_id

    # 3. INSERT nuevo
    r = conn.execute(
        text("""
            INSERT INTO material (codigo_proveedor, proveedor_id, descripcion, activo)
            VALUES (:codigo, :prov, :desc, TRUE)
            RETURNING id
        """),
        {
            "codigo": codigo_int,
            "prov": proveedor_id,
            "desc": (descripcion or "").strip() or None,
        },
    ).fetchone()

    return r[0]


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
    codigo_int = int(codigo_proveedor)

    # 1. Buscar existente
    r = conn.execute(
        text("""
            SELECT id, nombre
            FROM color
            WHERE codigo_proveedor = :codigo AND proveedor_id = :prov
        """),
        {"codigo": codigo_int, "prov": proveedor_id},
    ).fetchone()

    if r:
        color_id, nombre_actual = r
        # 2. Enriquecimiento no inverso
        if debe_actualizar_descripcion(nombre_actual, nombre):
            conn.execute(
                text("""
                    UPDATE color
                    SET nombre = :nom
                    WHERE id = :id
                """),
                {"nom": (nombre or "").strip(), "id": color_id},
            )
        return color_id

    # 3. INSERT nuevo
    r = conn.execute(
        text("""
            INSERT INTO color (codigo_proveedor, proveedor_id, nombre, hex_web, activo)
            VALUES (:codigo, :prov, :nom, :hex, TRUE)
            RETURNING id
        """),
        {
            "codigo": codigo_int,
            "prov": proveedor_id,
            "nom": (nombre or "").strip() or None,
            "hex": hex_web,
        },
    ).fetchone()

    return r[0]


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
    codigo_int = int(codigo_proveedor)

    # 1. Buscar existente
    r = conn.execute(
        text("""
            SELECT id, descripcion, marca_id, genero_id, grupo_estilo_id
            FROM linea
            WHERE codigo_proveedor = :codigo AND proveedor_id = :prov
        """),
        {"codigo": codigo_int, "prov": proveedor_id},
    ).fetchone()

    if r:
        linea_id = r[0]
        # Enriquecimiento descripción
        if debe_actualizar_descripcion(r[1], descripcion):
            conn.execute(
                text("UPDATE linea SET descripcion = :desc WHERE id = :id"),
                {"desc": (descripcion or "").strip(), "id": linea_id},
            )
        return linea_id

    # 2. INSERT nueva - aplicar herencia si faltan dimensiones
    dimensiones = aplicar_herencia_linea(
        conn, str(codigo_int), proveedor_id,
        marca_id=marca_id,
        genero_id=genero_id,
        grupo_estilo_id=grupo_estilo_id,
    )

    r = conn.execute(
        text("""
            INSERT INTO linea (
                codigo_proveedor, proveedor_id, descripcion,
                marca_id, genero_id, grupo_estilo_id, caso_id, activo
            )
            VALUES (:codigo, :prov, :desc, :marca, :genero, :estilo, :caso, TRUE)
            RETURNING id
        """),
        {
            "codigo": codigo_int,
            "prov": proveedor_id,
            "desc": (descripcion or "").strip() or None,
            "marca": dimensiones["marca_id"],
            "genero": dimensiones["genero_id"],
            "estilo": dimensiones["grupo_estilo_id"],
            "caso": caso_id,
        },
    ).fetchone()

    return r[0]


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
    codigo_int = int(codigo_proveedor)

    # 1. Buscar existente
    r = conn.execute(
        text("""
            SELECT id, descripcion
            FROM referencia
            WHERE linea_id = :linea AND codigo_proveedor = :codigo AND proveedor_id = :prov
        """),
        {"linea": linea_id, "codigo": codigo_int, "prov": proveedor_id},
    ).fetchone()

    if r:
        ref_id, desc_actual = r
        # Enriquecimiento descripción
        if debe_actualizar_descripcion(desc_actual, descripcion):
            conn.execute(
                text("UPDATE referencia SET descripcion = :desc WHERE id = :id"),
                {"desc": (descripcion or "").strip(), "id": ref_id},
            )
        return ref_id

    # 2. INSERT nueva
    r = conn.execute(
        text("""
            INSERT INTO referencia (linea_id, codigo_proveedor, proveedor_id, descripcion, activo)
            VALUES (:linea, :codigo, :prov, :desc, TRUE)
            RETURNING id
        """),
        {
            "linea": linea_id,
            "codigo": codigo_int,
            "prov": proveedor_id,
            "desc": (descripcion or "").strip() or None,
        },
    ).fetchone()

    return r[0]
