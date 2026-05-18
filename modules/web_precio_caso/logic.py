"""
OT-WEB-PRECIO-509-001 N2-N4: CRUD para caso_precio_web_regla (diccionario markup web).
"""
from typing import Any
import pandas as pd
from core.database import get_dataframe, engine
from sqlalchemy import text


def listar_reglas() -> pd.DataFrame:
    """
    N3: Listar todas las reglas (activas e inactivas).
    Retorna DataFrame con: id, caso_codigo, markup_pct, descripcion, activo, updated_at
    """
    return get_dataframe("""
        SELECT id, caso_codigo, markup_pct, descripcion, activo, updated_at
        FROM caso_precio_web_regla
        ORDER BY caso_codigo
    """)


def crear_regla(caso_codigo: str, markup_pct: float, descripcion: str = "") -> dict[str, Any]:
    """
    N3: Crear nueva regla de markup.
    Validaciones:
    - caso_codigo único (N4)
    - markup_pct entre 0-200% (N4)

    Returns:
        {"ok": bool, "error": str | None, "id": int | None}
    """
    # N4: Validaciones
    caso_codigo = caso_codigo.strip().upper()
    if not caso_codigo:
        return {"ok": False, "error": "Caso código no puede estar vacío", "id": None}

    if markup_pct < 0 or markup_pct > 200:
        return {"ok": False, "error": "Markup debe estar entre 0% y 200%", "id": None}

    # Verificar unicidad
    df = get_dataframe("""
        SELECT id FROM caso_precio_web_regla
        WHERE UPPER(TRIM(caso_codigo)) = :caso
    """, {"caso": caso_codigo})

    if df is not None and not df.empty:
        return {"ok": False, "error": f"Caso '{caso_codigo}' ya existe", "id": None}

    # Insertar
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO caso_precio_web_regla (caso_codigo, markup_pct, descripcion, activo)
                VALUES (:caso, :markup, :desc, true)
                RETURNING id
            """), {"caso": caso_codigo, "markup": markup_pct, "desc": descripcion})
            new_id = result.fetchone()[0]
        return {"ok": True, "error": None, "id": new_id}
    except Exception as e:
        return {"ok": False, "error": str(e), "id": None}


def editar_regla(regla_id: int, markup_pct: float, descripcion: str = "") -> dict[str, Any]:
    """
    N3: Editar regla existente (solo markup y descripción, no caso_codigo por unicidad).

    Returns:
        {"ok": bool, "error": str | None}
    """
    # N4: Validación markup
    if markup_pct < 0 or markup_pct > 200:
        return {"ok": False, "error": "Markup debe estar entre 0% y 200%"}

    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE caso_precio_web_regla
                SET markup_pct = :markup,
                    descripcion = :desc,
                    updated_at = now()
                WHERE id = :id
            """), {"id": regla_id, "markup": markup_pct, "desc": descripcion})
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def desactivar_regla(regla_id: int) -> dict[str, Any]:
    """
    N3: Soft delete — set activo=false.

    Returns:
        {"ok": bool, "error": str | None}
    """
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE caso_precio_web_regla
                SET activo = false, updated_at = now()
                WHERE id = :id
            """), {"id": regla_id})
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def activar_regla(regla_id: int) -> dict[str, Any]:
    """
    Reactivar regla desactivada.

    Returns:
        {"ok": bool, "error": str | None}
    """
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE caso_precio_web_regla
                SET activo = true, updated_at = now()
                WHERE id = :id
            """), {"id": regla_id})
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}
