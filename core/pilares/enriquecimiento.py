"""
Regla de enriquecimiento no inverso (§6 regla .mdc).

**Regla maestra:**
  SI pilar.descripcion EXISTE Y NO está vacía:
      SI flujo_entrante.descripcion EXISTE Y NO está vacía:
          UPDATE descripcion
      SI NO:
          NO TOCAR (NUNCA borrar/vaciar)
  SI pilar.descripcion NO EXISTE o está vacía:
      SI flujo_entrante.descripcion EXISTE Y NO está vacía:
          UPDATE descripcion (enriquecimiento)
      SI NO:
          NO TOCAR (mantener vacío)

Nunca usar COALESCE(:nueva, descripcion) con :nueva = '' porque pisa.
Validar siempre que el aporte sea no-vacío antes de actualizar.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


def aplicar_enriquecimiento_no_inverso(
    conn: Connection,
    tabla: str,
    pk_col: str,
    pk_val: int | str,
    descripcion_col: str,
    nueva_descripcion: str | None,
) -> bool:
    """
    Aplica regla no inversa: actualiza descripción solo si el aporte es no-vacío.

    Args:
        conn: Conexión SQLAlchemy
        tabla: Nombre tabla (ej. "material", "color")
        pk_col: Nombre columna PK (ej. "id", "codigo_proveedor")
        pk_val: Valor PK
        descripcion_col: Nombre columna descripción (ej. "descripcion", "nombre")
        nueva_descripcion: Valor entrante (puede ser None o vacío)

    Returns:
        True si actualizó, False si no tocó

    Implementación SQL canónica (§6 regla):
        UPDATE material
        SET descripcion = :nueva_descripcion
        WHERE codigo_proveedor = :codigo
          AND :nueva_descripcion IS NOT NULL
          AND TRIM(:nueva_descripcion) <> '';
    """
    # Validar aporte no-vacío
    if nueva_descripcion is None:
        return False

    nueva_trimmed = str(nueva_descripcion).strip()
    if not nueva_trimmed:
        return False

    # UPDATE solo si aporte es válido
    sql = text(f"""
        UPDATE public.{tabla}
        SET {descripcion_col} = :nueva_desc
        WHERE {pk_col} = :pk_val
          AND :nueva_desc IS NOT NULL
          AND TRIM(:nueva_desc) <> ''
    """)

    result = conn.execute(
        sql,
        {"nueva_desc": nueva_trimmed, "pk_val": pk_val},
    )

    return (result.rowcount or 0) > 0


def debe_actualizar_descripcion(
    descripcion_actual: str | None,
    descripcion_entrante: str | None,
) -> bool:
    """
    Helper: decide si debe actualizar según regla no inversa.

    Returns:
        True si debe actualizar, False si debe saltar

    Casos:
      - actual=None, entrante="Rojo" → True (enriquecimiento)
      - actual="", entrante="Rojo" → True (enriquecimiento)
      - actual="Azul", entrante="Rojo" → True (actualización)
      - actual="Azul", entrante="" → False (NO vaciar)
      - actual="Azul", entrante=None → False (NO vaciar)
    """
    actual_vacia = not (descripcion_actual or "").strip()
    entrante_valida = bool((descripcion_entrante or "").strip())

    if not entrante_valida:
        return False  # nunca vaciar

    # Si entrante es válida y (actual vacía o diferente) → actualizar
    return True
