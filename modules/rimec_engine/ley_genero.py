"""
LEY DE GÉNERO — Motor de Precios RIMEC

Se valida antes de cada importación de precios.
Al provisionar pilares, el género de la línea se asigna por marca (nombre de hoja Excel).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from core.database import engine, get_dataframe

# (patrón en nombre de hoja/marca, código en maestro public.genero)
# Orden: patrones más largos primero (evita que MOLECA matchee MOLEKINHA).
LEY_GENERO_REGLAS: tuple[tuple[str, str], ...] = (
    ("MOLEKINHA", "NIÑAS"),
    ("MOLEKINHO", "NIÑOS"),
    ("ACTVITTA", "DAMAS"),
    ("VIZZANO", "DAMAS"),
    ("BEIRA RIO", "DAMAS"),
    ("MODARE", "DAMAS"),
    ("MOLECA", "DAMAS"),
    ("BR SPORT", "CABALLEROS"),
)

GENEROS_LEY = ("DAMAS", "NIÑAS", "NIÑOS", "CABALLEROS")

# Códigos alternativos en maestro public.genero (DAMA vs DAMAS, etc.)
CODIGOS_GENERO_BD: dict[str, tuple[str, ...]] = {
    "DAMAS": ("DAMAS", "DAMA"),
    "NIÑAS": ("NIÑAS", "NINAS", "NINA", "NIÑA"),
    "NIÑOS": ("NIÑOS", "NINOS", "NINO", "NIÑO"),
    "CABALLEROS": ("CABALLEROS", "CABALLERO"),
}


def normalizar_marca(nombre: str) -> str:
    return " ".join(str(nombre or "").upper().split())


def genero_codigo_por_marca(nombre_marca: str) -> str | None:
    """Resuelve código de género (DAMAS, NIÑAS, …) según la Ley de Género."""
    m = normalizar_marca(nombre_marca)
    if not m:
        return None
    for patron, genero in LEY_GENERO_REGLAS:
        if patron in m:
            return genero
    return None


def validar_ley_genero_importacion(marcas: list[str] | set[str]) -> dict:
    """
    Validación obligatoria antes de importar precios.
    Retorna dict con ok, asignaciones {marca: genero}, marcas_rechazadas, generos_faltantes_bd.
    """
    asignaciones: dict[str, str] = {}
    rechazadas: list[str] = []
    visto: set[str] = set()

    for raw in marcas:
        marca = str(raw).strip()
        if not marca:
            continue
        key = normalizar_marca(marca)
        if key in visto:
            continue
        visto.add(key)
        genero = genero_codigo_por_marca(marca)
        if genero:
            asignaciones[marca] = genero
        else:
            rechazadas.append(marca)

    en_bd = _codigos_genero_en_bd()

    faltantes_bd = [g for g in GENEROS_LEY if not _ley_genero_existe_en_bd(g, en_bd)]
    usados = set(asignaciones.values())
    faltantes_uso = [g for g in usados if not _ley_genero_existe_en_bd(g, en_bd)]

    ok = not rechazadas and not faltantes_bd and not faltantes_uso
    return {
        "ok": ok,
        "asignaciones": asignaciones,
        "marcas_rechazadas": rechazadas,
        "generos_faltantes_bd": sorted(set(faltantes_bd + faltantes_uso)),
    }


def _codigos_genero_en_bd() -> set[str]:
    df_gen = get_dataframe(
        """SELECT upper(trim(codigo)) AS codigo,
                  upper(trim(COALESCE(descripcion, ''))) AS descripcion
           FROM genero
           WHERE COALESCE(activo, true)"""
    )
    en_bd: set[str] = set()
    if df_gen is not None and not df_gen.empty:
        for _, r in df_gen.iterrows():
            if r["codigo"]:
                en_bd.add(str(r["codigo"]))
            if r["descripcion"]:
                en_bd.add(str(r["descripcion"]))
    return en_bd


def _ley_genero_existe_en_bd(codigo_ley: str, en_bd: set[str]) -> bool:
    variantes = CODIGOS_GENERO_BD.get(codigo_ley, (codigo_ley,))
    return any(v.upper() in en_bd for v in variantes)


def lookup_genero_id(conn, codigo_genero: str) -> int | None:
    variantes = CODIGOS_GENERO_BD.get(codigo_genero, (codigo_genero,))
    for cod in variantes:
        row = conn.execute(
            text(
                """
                SELECT id FROM public.genero
                WHERE upper(trim(codigo)) = upper(trim(:c))
                  AND COALESCE(activo, true)
                LIMIT 1
                """
            ),
            {"c": cod},
        ).fetchone()
        if row:
            return int(row[0])
        row = conn.execute(
            text(
                """
                SELECT id FROM public.genero
                WHERE upper(trim(COALESCE(descripcion, ''))) = upper(trim(:c))
                  AND COALESCE(activo, true)
                LIMIT 1
                """
            ),
            {"c": cod},
        ).fetchone()
        if row:
            return int(row[0])
    return None


def aplicar_ley_genero_fk_lineas(
    conn,
    lineas_marca: dict[int, str],
) -> tuple[int, list[str]]:
    """
    Escribe linea.genero_id según Ley de Género (marca → maestro genero).
    lineas_marca: {linea.id: nombre_hoja_excel}
  Retorna (líneas actualizadas, marcas sin FK de género).
    """
    actualizadas = 0
    sin_fk: list[str] = []
    for linea_id, marca_nombre in sorted(lineas_marca.items(), key=lambda t: int(t[0])):
        genero_id = resolver_genero_id_por_marca(conn, marca_nombre)
        if not genero_id:
            if marca_nombre not in sin_fk:
                sin_fk.append(marca_nombre)
            continue
        conn.execute(
            text(
                """
                UPDATE public.linea
                SET genero_id = CAST(:gid AS bigint)
                WHERE id = CAST(:lid AS bigint)
                """
            ),
            {"gid": genero_id, "lid": int(linea_id)},
        )
        actualizadas += 1
    return actualizadas, sin_fk


def aplicar_ley_genero_desde_evento(evento_id: int) -> dict:
    """Aplica FK genero_id en linea para todas las líneas del listado."""
    df = get_dataframe(
        """
        SELECT DISTINCT pl.linea_id, TRIM(pl.marca) AS marca
        FROM precio_lista pl
        WHERE pl.evento_id = :eid
          AND pl.linea_id IS NOT NULL
          AND TRIM(COALESCE(pl.marca, '')) <> ''
        """,
        {"eid": evento_id},
    )
    if df is None or df.empty:
        return {"lineas": 0, "sin_fk": []}

    mapa: dict[int, str] = {}
    for _, row in df.iterrows():
        lid = int(row["linea_id"])
        marca = str(row["marca"]).strip()
        if lid in mapa and mapa[lid].upper() != marca.upper():
            continue
        mapa[lid] = marca

    row_pe = get_dataframe(
        "SELECT proveedor_id FROM precio_evento WHERE id = :eid",
        {"eid": evento_id},
    )
    if row_pe is None or row_pe.empty:
        return {"lineas": 0, "sin_fk": [], "total": len(mapa)}
    proveedor_id = int(row_pe.iloc[0]["proveedor_id"])

    from modules.rimec_engine.pillar_fk import run_with_pilar_lock

    def _aplicar(conn) -> tuple[int, list[str]]:
        return aplicar_ley_genero_fk_lineas(conn, mapa)

    try:
        n, sin_fk = run_with_pilar_lock(proveedor_id, _aplicar)
    except OperationalError:
        return {"lineas": 0, "sin_fk": ["deadlock"], "total": len(mapa), "error": "deadlock"}

    return {"lineas": n, "sin_fk": sin_fk, "total": len(mapa)}


def resolver_genero_id_por_marca(conn, nombre_marca: str) -> int | None:
    codigo = genero_codigo_por_marca(nombre_marca)
    if not codigo:
        return None
    return lookup_genero_id(conn, codigo)


def texto_ley_genero_resumen() -> str:
    lineas = ["**Ley de género** (validación obligatoria al importar):"]
    grupos: dict[str, list[str]] = {g: [] for g in GENEROS_LEY}
    for patron, genero in LEY_GENERO_REGLAS:
        if patron not in grupos[genero]:
            grupos[genero].append(patron)
    for genero in GENEROS_LEY:
        marcas = ", ".join(grupos[genero]) if grupos[genero] else "—"
        lineas.append(f"- **{genero}:** {marcas}")
    return "\n".join(lineas)
