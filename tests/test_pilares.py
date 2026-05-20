"""
Tests para motor compartido de pilares (OT-PILARES-LEYES-IMPORTACION-001).

Cobertura objetivo: ≥80%

Test suites:
  - upsert_material: idempotencia + regla no inversa
  - upsert_color: idempotencia + regla no inversa
  - upsert_linea: idempotencia + herencia jerárquica
  - upsert_referencia: idempotencia
  - herencia: plantilla + sentinelas OTROS
  - grada: validación canónica + warnings
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pilares import (
    upsert_material,
    upsert_color,
    upsert_linea,
    upsert_referencia,
    aplicar_herencia_linea,
    validar_grada_canonica,
    es_grada_simple,
    MATRIZ_GRADA_12,
)


@pytest.fixture
def db_engine():
    """Motor SQLite en memoria para tests aislados."""
    engine = create_engine("sqlite:///:memory:")

    # Crear schema de prueba
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE material (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_proveedor INTEGER NOT NULL,
                proveedor_id INTEGER NOT NULL,
                descripcion TEXT,
                activo INTEGER DEFAULT 1,
                UNIQUE(codigo_proveedor, proveedor_id)
            )
        """))

        conn.execute(text("""
            CREATE TABLE color (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_proveedor INTEGER NOT NULL,
                proveedor_id INTEGER NOT NULL,
                nombre TEXT,
                hex_web TEXT,
                activo INTEGER DEFAULT 1,
                UNIQUE(codigo_proveedor, proveedor_id)
            )
        """))

        conn.execute(text("""
            CREATE TABLE linea (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_proveedor INTEGER NOT NULL,
                proveedor_id INTEGER NOT NULL,
                descripcion TEXT,
                marca_id INTEGER,
                genero_id INTEGER,
                grupo_estilo_id INTEGER,
                caso_id INTEGER,
                activo INTEGER DEFAULT 1,
                UNIQUE(codigo_proveedor, proveedor_id)
            )
        """))

        conn.execute(text("""
            CREATE TABLE referencia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                linea_id INTEGER NOT NULL,
                codigo_proveedor INTEGER NOT NULL,
                proveedor_id INTEGER NOT NULL,
                descripcion TEXT,
                activo INTEGER DEFAULT 1,
                UNIQUE(linea_id, codigo_proveedor, proveedor_id)
            )
        """))

        conn.execute(text("""
            CREATE TABLE marca_v2 (
                id INTEGER PRIMARY KEY,
                nombre_v2 TEXT
            )
        """))

        # Insertar marca sentinela RETAIL_OTROS
        conn.execute(text("""
            INSERT INTO marca_v2 (id, nombre_v2)
            VALUES (-999001, 'RETAIL_OTROS')
        """))

    yield engine
    engine.dispose()


@pytest.fixture
def conn(db_engine):
    """Conexión transaccional que hace rollback al final del test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


# ============================================================================
# TESTS: upsert_material
# ============================================================================

def test_upsert_material_insert_nuevo(conn: Connection):
    """INSERT material nuevo con descripción."""
    mat_id = upsert_material(
        conn, "1001", 654,
        descripcion="Cuero sintético",
        fuente="listado",
    )

    assert mat_id > 0

    r = conn.execute(
        text("SELECT codigo_proveedor, descripcion FROM material WHERE id = :id"),
        {"id": mat_id},
    ).fetchone()

    assert r[0] == 1001
    assert r[1] == "Cuero sintético"


def test_upsert_material_idempotencia(conn: Connection):
    """Mismo input → mismo id (idempotencia)."""
    mat_id1 = upsert_material(conn, "1002", 654, descripcion="Tela", fuente="listado")
    mat_id2 = upsert_material(conn, "1002", 654, descripcion="Tela", fuente="listado")

    assert mat_id1 == mat_id2


def test_upsert_material_enriquecimiento_no_inverso_actualiza(conn: Connection):
    """Si existe y nueva descripción no-vacía → UPDATE."""
    mat_id = upsert_material(conn, "1003", 654, descripcion="Desc1", fuente="listado")

    mat_id2 = upsert_material(conn, "1003", 654, descripcion="Desc2", fuente="proforma")

    assert mat_id == mat_id2

    r = conn.execute(
        text("SELECT descripcion FROM material WHERE id = :id"),
        {"id": mat_id},
    ).fetchone()

    assert r[0] == "Desc2"


def test_upsert_material_enriquecimiento_no_inverso_no_vacia(conn: Connection):
    """Si existe con descripción y nueva es vacía → NO TOCAR."""
    mat_id = upsert_material(conn, "1004", 654, descripcion="Original", fuente="listado")

    mat_id2 = upsert_material(conn, "1004", 654, descripcion="", fuente="retail")

    assert mat_id == mat_id2

    r = conn.execute(
        text("SELECT descripcion FROM material WHERE id = :id"),
        {"id": mat_id},
    ).fetchone()

    assert r[0] == "Original"  # NO debe vaciar


def test_upsert_material_enriquecimiento_no_inverso_none(conn: Connection):
    """Si existe y nueva es None → NO TOCAR."""
    mat_id = upsert_material(conn, "1005", 654, descripcion="Original", fuente="listado")

    mat_id2 = upsert_material(conn, "1005", 654, descripcion=None, fuente="retail")

    r = conn.execute(
        text("SELECT descripcion FROM material WHERE id = :id"),
        {"id": mat_id},
    ).fetchone()

    assert r[0] == "Original"


def test_upsert_material_insert_sin_descripcion(conn: Connection):
    """INSERT nuevo sin descripción → NULL permitido."""
    mat_id = upsert_material(conn, "1006", 654, descripcion=None, fuente="retail")

    r = conn.execute(
        text("SELECT descripcion FROM material WHERE id = :id"),
        {"id": mat_id},
    ).fetchone()

    assert r[0] is None


# ============================================================================
# TESTS: upsert_color
# ============================================================================

def test_upsert_color_insert_nuevo(conn: Connection):
    """INSERT color nuevo con nombre."""
    color_id = upsert_color(
        conn, "2001", 654,
        nombre="Rojo",
        hex_web="#FF0000",
        fuente="listado",
    )

    assert color_id > 0

    r = conn.execute(
        text("SELECT codigo_proveedor, nombre, hex_web FROM color WHERE id = :id"),
        {"id": color_id},
    ).fetchone()

    assert r[0] == 2001
    assert r[1] == "Rojo"
    assert r[2] == "#FF0000"


def test_upsert_color_idempotencia(conn: Connection):
    """Mismo input → mismo id."""
    c1 = upsert_color(conn, "2002", 654, nombre="Azul", fuente="listado")
    c2 = upsert_color(conn, "2002", 654, nombre="Azul", fuente="listado")

    assert c1 == c2


def test_upsert_color_enriquecimiento_no_inverso(conn: Connection):
    """Si existe y nuevo nombre no-vacío → UPDATE."""
    c_id = upsert_color(conn, "2003", 654, nombre="Verde", fuente="listado")

    upsert_color(conn, "2003", 654, nombre="Verde Oscuro", fuente="proforma")

    r = conn.execute(
        text("SELECT nombre FROM color WHERE id = :id"),
        {"id": c_id},
    ).fetchone()

    assert r[0] == "Verde Oscuro"


def test_upsert_color_no_vacia_con_vacio(conn: Connection):
    """Si existe con nombre y nuevo es vacío → NO TOCAR."""
    c_id = upsert_color(conn, "2004", 654, nombre="Amarillo", fuente="listado")

    upsert_color(conn, "2004", 654, nombre="", fuente="retail")

    r = conn.execute(
        text("SELECT nombre FROM color WHERE id = :id"),
        {"id": c_id},
    ).fetchone()

    assert r[0] == "Amarillo"


# ============================================================================
# TESTS: upsert_linea
# ============================================================================

def test_upsert_linea_insert_con_dimensiones(conn: Connection):
    """INSERT línea nueva con dimensiones explícitas → NO hereda."""
    linea_id = upsert_linea(
        conn, "8001", 654,
        descripcion="Zapato Casual",
        marca_id=100,
        genero_id=1,
        grupo_estilo_id=5,
        fuente="listado",
    )

    assert linea_id > 0

    r = conn.execute(
        text("SELECT marca_id, genero_id, grupo_estilo_id FROM linea WHERE id = :id"),
        {"id": linea_id},
    ).fetchone()

    assert r[0] == 100
    assert r[1] == 1
    assert r[2] == 5


def test_upsert_linea_idempotencia(conn: Connection):
    """Mismo input → mismo id."""
    l1 = upsert_linea(conn, "8002", 654, descripcion="Sandalia", fuente="listado")
    l2 = upsert_linea(conn, "8002", 654, descripcion="Sandalia", fuente="listado")

    assert l1 == l2


def test_upsert_linea_herencia_de_plantilla(conn: Connection):
    """Línea nueva sin dimensiones hereda de plantilla anterior."""
    # 1. Crear línea plantilla 8100 con dimensiones
    conn.execute(text("""
        INSERT INTO linea (codigo_proveedor, proveedor_id, marca_id, genero_id, grupo_estilo_id, activo)
        VALUES (8100, 654, 200, 2, 10, 1)
    """))

    # 2. Crear línea 8200 sin dimensiones → debe heredar de 8100
    linea_id = upsert_linea(
        conn, "8200", 654,
        descripcion="Bota",
        fuente="listado",
    )

    r = conn.execute(
        text("SELECT marca_id, genero_id, grupo_estilo_id FROM linea WHERE id = :id"),
        {"id": linea_id},
    ).fetchone()

    # Debe heredar marca=200, genero=2, estilo=10 de plantilla 8100
    assert r[0] == 200
    assert r[1] == 2
    assert r[2] == 10


def test_upsert_linea_sin_plantilla_usa_sentinelas(conn: Connection):
    """Línea nueva sin plantilla → usa sentinelas OTROS."""
    # No hay líneas previas, debe usar sentinelas
    linea_id = upsert_linea(
        conn, "8001", 654,
        descripcion="Primera línea",
        fuente="retail",
    )

    r = conn.execute(
        text("SELECT marca_id, genero_id, grupo_estilo_id FROM linea WHERE id = :id"),
        {"id": linea_id},
    ).fetchone()

    # Debe usar sentinelas: marca=-999001, genero=None, estilo=None
    assert r[0] == -999001
    assert r[1] is None
    assert r[2] is None


def test_upsert_linea_herencia_parcial(conn: Connection):
    """Hereda solo las dimensiones que faltan."""
    # Plantilla con dimensiones completas
    conn.execute(text("""
        INSERT INTO linea (codigo_proveedor, proveedor_id, marca_id, genero_id, grupo_estilo_id, activo)
        VALUES (8100, 654, 300, 3, 15, 1)
    """))

    # Nueva línea con marca pero sin genero/estilo → hereda solo genero/estilo
    linea_id = upsert_linea(
        conn, "8150", 654,
        descripcion="Mocasín",
        marca_id=999,  # Explícita, NO hereda
        fuente="listado",
    )

    r = conn.execute(
        text("SELECT marca_id, genero_id, grupo_estilo_id FROM linea WHERE id = :id"),
        {"id": linea_id},
    ).fetchone()

    assert r[0] == 999  # Explícita
    assert r[1] == 3    # Heredada
    assert r[2] == 15   # Heredada


# ============================================================================
# TESTS: upsert_referencia
# ============================================================================

def test_upsert_referencia_insert_nueva(conn: Connection):
    """INSERT referencia nueva."""
    # Primero crear línea
    linea_id = upsert_linea(conn, "8001", 654, fuente="listado")

    ref_id = upsert_referencia(
        conn, "1001", linea_id, 654,
        descripcion="Referencia A",
        fuente="listado",
    )

    assert ref_id > 0

    r = conn.execute(
        text("SELECT linea_id, codigo_proveedor, descripcion FROM referencia WHERE id = :id"),
        {"id": ref_id},
    ).fetchone()

    assert r[0] == linea_id
    assert r[1] == 1001
    assert r[2] == "Referencia A"


def test_upsert_referencia_idempotencia(conn: Connection):
    """Mismo input → mismo id."""
    linea_id = upsert_linea(conn, "8002", 654, fuente="listado")

    r1 = upsert_referencia(conn, "1002", linea_id, 654, descripcion="Ref B", fuente="listado")
    r2 = upsert_referencia(conn, "1002", linea_id, 654, descripcion="Ref B", fuente="listado")

    assert r1 == r2


def test_upsert_referencia_enriquecimiento_no_inverso(conn: Connection):
    """Si existe y nueva descripción no-vacía → UPDATE."""
    linea_id = upsert_linea(conn, "8003", 654, fuente="listado")

    ref_id = upsert_referencia(conn, "1003", linea_id, 654, descripcion="Original", fuente="listado")

    upsert_referencia(conn, "1003", linea_id, 654, descripcion="Actualizada", fuente="proforma")

    r = conn.execute(
        text("SELECT descripcion FROM referencia WHERE id = :id"),
        {"id": ref_id},
    ).fetchone()

    assert r[0] == "Actualizada"


# ============================================================================
# TESTS: grada
# ============================================================================

def test_es_grada_simple_talla_simple():
    """Talla simple (34, 38) → True."""
    assert es_grada_simple("34") is True
    assert es_grada_simple("38") is True
    assert es_grada_simple("  39  ") is True


def test_es_grada_simple_curva():
    """Curva con paréntesis → False."""
    assert es_grada_simple("34(1 2 3 3 2 1)39") is False
    assert es_grada_simple("20(1 1 1 1 1 1)25") is False


def test_validar_grada_canonica_exacta():
    """Curva canónica 34(1 2 3 3 2 1)39 → válida sin warning."""
    valida, warning = validar_grada_canonica("34(1 2 3 3 2 1)39")

    assert valida is True
    assert warning is None


def test_validar_grada_canonica_espaciado():
    """Curva canónica con espacios variables → válida."""
    valida, warning = validar_grada_canonica("  34 ( 1  2  3  3  2  1 ) 39  ")

    assert valida is True
    assert warning is None


def test_validar_grada_simple_sin_warning():
    """Talla simple → válida sin warning."""
    valida, warning = validar_grada_canonica("36")

    assert valida is True
    assert warning is None


def test_validar_grada_no_canonica_acepta_con_warning():
    """Curva no canónica → válida CON warning (Estrategia B)."""
    valida, warning = validar_grada_canonica("20(1 1 1 1 1 1)25")

    assert valida is True  # NO rechaza
    assert warning is not None
    assert "no es canónica" in warning


def test_validar_grada_vacia():
    """Grada vacía → válida sin warning."""
    valida, warning = validar_grada_canonica("")

    assert valida is True
    assert warning is None


def test_matriz_grada_12_suma():
    """MATRIZ_GRADA_12 suma exactamente 12 pares."""
    total = sum(MATRIZ_GRADA_12.values())
    assert total == 12


def test_matriz_grada_12_tallas():
    """MATRIZ_GRADA_12 tiene tallas 34-39."""
    assert MATRIZ_GRADA_12 == {
        34: 1,
        35: 2,
        36: 3,
        37: 3,
        38: 2,
        39: 1,
    }


# ============================================================================
# TESTS: herencia directa (funciones internas expuestas vía importación)
# ============================================================================

def test_aplicar_herencia_linea_todas_dimensiones_dadas(conn: Connection):
    """Si vienen todas las dimensiones, retorna sin cambios."""
    resultado = aplicar_herencia_linea(
        conn, "9000", 654,
        marca_id=100,
        genero_id=1,
        grupo_estilo_id=5,
    )

    assert resultado["marca_id"] == 100
    assert resultado["genero_id"] == 1
    assert resultado["grupo_estilo_id"] == 5


def test_aplicar_herencia_linea_sin_plantilla_usa_sentinelas(conn: Connection):
    """Sin plantilla → usa sentinelas OTROS."""
    resultado = aplicar_herencia_linea(conn, "9000", 654)

    assert resultado["marca_id"] == -999001
    assert resultado["genero_id"] is None
    assert resultado["grupo_estilo_id"] is None


def test_aplicar_herencia_linea_con_plantilla(conn: Connection):
    """Con plantilla → hereda dimensiones faltantes."""
    # Crear plantilla
    conn.execute(text("""
        INSERT INTO linea (codigo_proveedor, proveedor_id, marca_id, genero_id, grupo_estilo_id, activo)
        VALUES (8500, 654, 400, 4, 20, 1)
    """))

    # Pedir herencia para código 8600 (> 8500)
    resultado = aplicar_herencia_linea(
        conn, "8600", 654,
        marca_id=500,  # Explícita
        # genero y estilo faltan → deben heredarse
    )

    assert resultado["marca_id"] == 500  # Explícita
    assert resultado["genero_id"] == 4   # Heredada
    assert resultado["grupo_estilo_id"] == 20  # Heredada
