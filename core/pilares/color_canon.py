"""Pilar color — tono_canon · catálogo estándar · sugerencia desde nombre proveedor.

Paridad Report: colores-estandar.ts · CHUSAR_PILAR_COLOR_TONO_CANON.md
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection

TonoTipo = Literal["solido", "paleta"]

_SEPARADORES_COLOR = re.compile(r"[/,\-–|]+")

# Proforma compuesta: ORO/dorado manda sobre nude/beige en la misma descripción.
_PRIORITY_NOMBRE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"oro\s*rosad|oro\s*clar|(?<![a-z])oro(?![a-z])|dorad|amarelo|amarill|gold|golden"), "Dorado"),
    (re.compile(r"(?<![a-z])negro(?![a-z])|preto|black"), "Negro"),
    (re.compile(r"(?<![a-z])blanco(?![a-z])|branco|white|marfil|ivory"), "Blanco"),
)

OTROS_MULTICOLOR_SWATCHES = [
    "#c62828",
    "#1565c0",
    "#2e7d32",
    "#ffd54f",
    "#1a1a1a",
    "#f48fb1",
]

ETIQUETAS_LEGACY: dict[str, str] = {
    "plateado": "Gris",
    "plata": "Gris",
    "amarillo": "Dorado",
}


@dataclass(frozen=True)
class ColorEstandar:
    etiqueta: str
    hex: str
    aliases: tuple[str, ...]
    multicolor: bool = False
    swatches: tuple[str, ...] = ()


COLORES_ESTANDAR_DEFAULT: tuple[ColorEstandar, ...] = (
    ColorEstandar("Negro", "#1a1a1a", ("negro", "preto", "black")),
    ColorEstandar("Blanco", "#f5f5f0", ("blanco", "branco", "white", "marfil", "ivory", "offwhite")),
    ColorEstandar(
        "Gris",
        "#9e9e9e",
        ("gris", "cinza", "grey", "gray", "grafito", "plata", "prata", "silver", "plateado", "platino"),
    ),
    ColorEstandar(
        "Dorado",
        "#ffd54f",
        ("dorado", "dourado", "oro", "gold", "golden", "amarillo", "amarelo", "yellow", "mostaza", "mustard"),
    ),
    ColorEstandar(
        "Beige",
        "#e8d5b0",
        (
            "beige", "bege", "avela", "avellana", "areia", "arena", "nude", "natural", "crema", "cream",
            "camel", "capuchino", "caramelo", "tan", "taupe", "moka", "mocha", "couro", "cuero", "leather",
        ),
    ),
    ColorEstandar(
        "Marrón",
        "#6d4c41",
        ("marrón", "marron", "marrom", "brown", "cacao", "cocoa", "chocolate", "coffee", "café", "cafe"),
    ),
    ColorEstandar("Rojo", "#c62828", ("rojo", "vermelho", "red")),
    ColorEstandar("Vino", "#880e4f", ("vino", "wine", "bordô", "bordo", "burdeo", "guinda")),
    ColorEstandar("Fucsia", "#c026d3", ("fucsia", "fuchsia", "magenta")),
    ColorEstandar("Naranja", "#c2410c", ("naranja", "laranja", "orange", "coral")),
    ColorEstandar("Verde", "#2e7d32", ("verde", "green", "oliva", "olive")),
    ColorEstandar("Celeste", "#4fc3f7", ("celeste", "aqua")),
    ColorEstandar("Azul", "#1565c0", ("azul", "blue")),
    ColorEstandar("Marino", "#1e3a5f", ("marino", "marina", "marihq", "mariho", "marinha", "navy")),
    ColorEstandar("Rosado", "#f48fb1", ("rosado", "rosa", "pink", "rosado")),
    ColorEstandar("Bronce", "#b87333", ("bronce", "bronze")),
    ColorEstandar(
        "Otros",
        "#64748b",
        ("multicolor", "multi", "varios", "mix", "estampado", "print", "combinado"),
        multicolor=True,
        swatches=tuple(OTROS_MULTICOLOR_SWATCHES),
    ),
)


def color_predominante(nombre: str | None) -> str:
    """Primer token antes de / - , | (ej. NEGRO/BLANCO → NEGRO)."""
    raw = (nombre or "").strip()
    if not raw:
        return ""
    token = _SEPARADORES_COLOR.split(raw, maxsplit=1)[0].strip()
    if not token:
        return raw
    return (token.split()[0] or token).strip()


def normalizar_etiqueta(s: str) -> str:
    t = s.strip()
    if not t:
        return ""
    return t[0].upper() + t[1:].lower() if len(t) > 1 else t.upper()


def _normalize_token(s: str) -> str:
    t = unicodedata.normalize("NFD", s.strip().lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _build_alias_index(catalog: tuple[ColorEstandar, ...]) -> dict[str, ColorEstandar]:
    index: dict[str, ColorEstandar] = {}
    for c in catalog:
        index[_normalize_token(c.etiqueta)] = c
        for alias in c.aliases:
            index[_normalize_token(alias)] = c
    return index


def is_auto_suggestable(entry: ColorEstandar | None) -> bool:
    if entry is None:
        return False
    if entry.multicolor:
        return False
    return _normalize_token(entry.etiqueta) != "otros"


def find_color_estandar_in_catalog(etiqueta: str, catalog: tuple[ColorEstandar, ...]) -> ColorEstandar | None:
    key = _normalize_token(etiqueta)
    index = _build_alias_index(catalog)
    direct = index.get(key)
    if direct:
        return direct
    legacy = ETIQUETAS_LEGACY.get(key)
    if legacy:
        return find_color_estandar_in_catalog(legacy, catalog)
    for c in catalog:
        if _normalize_token(c.etiqueta) == key:
            return c
    return None


def sugerir_color_estandar_from_nombre(
    nombre: str | None,
    catalog: tuple[ColorEstandar, ...] | None = None,
) -> ColorEstandar | None:
    """Sugerencia canónica — ORO/dorado/amarillo → Dorado; NEGRO → Negro; etc."""
    cat = catalog or COLORES_ESTANDAR_DEFAULT
    raw = (nombre or "").strip()
    if not raw:
        return None

    direct = find_color_estandar_in_catalog(raw, cat)
    if direct and is_auto_suggestable(direct):
        return direct

    raw_norm = _normalize_token(raw)
    for pattern, etiqueta in _PRIORITY_NOMBRE_PATTERNS:
        if pattern.search(raw_norm):
            hit = find_color_estandar_in_catalog(etiqueta, cat)
            if hit and is_auto_suggestable(hit):
                return hit

    tokens = [t.strip() for t in re.split(r"[/,\-–|\s]+", raw) if t.strip()]
    for token in tokens:
        hit = find_color_estandar_in_catalog(token, cat)
        if hit and is_auto_suggestable(hit):
            return hit

    raw_norm = _normalize_token(raw)
    for c in cat:
        if not is_auto_suggestable(c):
            continue
        for alias in c.aliases:
            if alias in raw_norm or raw_norm.startswith(_normalize_token(alias)):
                return c

    pred = color_predominante(raw)
    if pred:
        hit = find_color_estandar_in_catalog(pred, cat)
        if hit and is_auto_suggestable(hit):
            return hit

    return None


def estandar_to_tono(c: ColorEstandar) -> dict[str, Any]:
    if c.multicolor:
        sw = list(c.swatches) if c.swatches else OTROS_MULTICOLOR_SWATCHES
        return tono_paleta(c.etiqueta, sw)
    return tono_solido(c.etiqueta, c.hex)


def tono_solido(etiqueta: str, hex_color: str) -> dict[str, Any]:
    h = hex_color.strip()
    if not h.startswith("#"):
        h = f"#{h}"
    return {"tipo": "solido", "etiqueta": normalizar_etiqueta(etiqueta), "hex": h.lower()}


def tono_paleta(etiqueta: str, swatches: list[str]) -> dict[str, Any]:
    norm: list[str] = []
    for s in swatches:
        h = s.strip()
        if not h:
            continue
        if not h.startswith("#"):
            h = f"#{h}"
        norm.append(h.lower())
    return {"tipo": "paleta", "etiqueta": normalizar_etiqueta(etiqueta), "swatches": norm}


def sugerir_tono_desde_nombre(nombre: str | None, hex_default: str = "#94a3b8") -> dict[str, Any]:
    """Fallback legacy — preferir sugerir_color_estandar_from_nombre + estandar_to_tono."""
    hit = sugerir_color_estandar_from_nombre(nombre)
    if hit:
        return estandar_to_tono(hit)
    pred = color_predominante(nombre)
    if not pred:
        return tono_solido("(sin tono)", hex_default)
    return tono_solido(pred, hex_default)


def parse_tono_canon(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
    else:
        return None
    if not isinstance(data.get("etiqueta"), str) or not str(data["etiqueta"]).strip():
        return None
    tipo = data.get("tipo")
    if tipo == "solido" and isinstance(data.get("hex"), str):
        return tono_solido(data["etiqueta"], data["hex"])
    if tipo == "paleta" and isinstance(data.get("swatches"), list):
        return tono_paleta(data["etiqueta"], [str(x) for x in data["swatches"]])
    return None


def etiqueta_filtro(tono: dict[str, Any] | None) -> str | None:
    if not tono:
        return None
    e = str(tono.get("etiqueta") or "").strip()
    return e or None


def _tono_sin_asignar(raw: Any) -> bool:
    if raw is None:
        return True
    parsed = parse_tono_canon(raw)
    if not parsed:
        return True
    return not bool(str(parsed.get("etiqueta") or "").strip())


def _hex_from_tono(tono: dict[str, Any]) -> str:
    if tono.get("tipo") == "solido":
        return str(tono.get("hex") or "#94a3b8")
    sw = tono.get("swatches") or []
    if sw:
        return str(sw[0])
    return "#64748b"


def catalog_from_db(conn: Connection, proveedor_id: int) -> tuple[ColorEstandar, ...]:
    """Catálogo BD si existe color_tono_estandar; si no, default holding."""
    try:
        with conn.begin_nested():
            rows = conn.execute(
                text(
                    """
                    SELECT etiqueta, hex, aliases
                    FROM public.color_tono_estandar
                    WHERE proveedor_id = CAST(:p AS bigint) AND activo = true
                    ORDER BY COALESCE(orden, 999), etiqueta
                    """
                ),
                {"p": proveedor_id},
            ).fetchall()
    except Exception:
        return COLORES_ESTANDAR_DEFAULT

    if not rows:
        return COLORES_ESTANDAR_DEFAULT

    out: list[ColorEstandar] = []
    for r in rows:
        aliases_raw = r[2] if len(r) > 2 else []
        if isinstance(aliases_raw, str):
            try:
                aliases_raw = json.loads(aliases_raw)
            except json.JSONDecodeError:
                aliases_raw = []
        if isinstance(aliases_raw, (list, tuple)):
            aliases = tuple(str(a) for a in aliases_raw)
        else:
            aliases = ()
        etiqueta = str(r[0])
        multicolor = _normalize_token(etiqueta) == "otros"
        default = find_color_estandar_in_catalog(etiqueta, COLORES_ESTANDAR_DEFAULT)
        swatches = default.swatches if default and default.multicolor else ()
        out.append(
            ColorEstandar(
                etiqueta,
                str(r[1]),
                aliases,
                multicolor=multicolor,
                swatches=swatches,
            )
        )
    return tuple(out) if out else COLORES_ESTANDAR_DEFAULT


def sync_hex_web_desde_tono_canon(conn: Connection, color_id: int) -> bool:
    """Rellena hex_web desde tono_canon JSON cuando falta (catálogo lee hex_web)."""
    row = conn.execute(
        text(
            """
            SELECT tono_canon, hex_web
            FROM public.color
            WHERE id = CAST(:id AS bigint)
            LIMIT 1
            """
        ),
        {"id": color_id},
    ).fetchone()
    if not row:
        return False
    tono_raw, hex_existing = row[0], row[1]
    if hex_existing and str(hex_existing).strip():
        return False
    parsed = parse_tono_canon(tono_raw)
    if not parsed:
        return False
    hex_web = _hex_from_tono(parsed)
    conn.execute(
        text(
            """
            UPDATE public.color
            SET hex_web = :hex
            WHERE id = CAST(:id AS bigint)
              AND (hex_web IS NULL OR btrim(hex_web) = '')
            """
        ),
        {"hex": hex_web, "id": color_id},
    )
    return True


def aplicar_tono_canon_desde_nombre(
    conn: Connection,
    color_id: int,
    nombre: str | None,
    proveedor_id: int,
    *,
    forzar: bool = False,
) -> bool:
    """Persiste tono_canon + hex_web desde descripción (proforma / tránsito)."""
    nombre_eff = (nombre or "").strip()
    if not nombre_eff:
        return False

    row = conn.execute(
        text(
            """
            SELECT tono_canon, nombre
            FROM public.color
            WHERE id = CAST(:id AS bigint)
            LIMIT 1
            """
        ),
        {"id": color_id},
    ).fetchone()
    if not row:
        return False

    tono_raw, nombre_db = row[0], row[1]
    if not forzar and not _tono_sin_asignar(tono_raw):
        return False

    nombre_src = nombre_eff or (str(nombre_db or "").strip())
    if not nombre_src:
        return False

    catalog = catalog_from_db(conn, proveedor_id)
    hit = sugerir_color_estandar_from_nombre(nombre_src, catalog)
    if not hit:
        return False

    tono = estandar_to_tono(hit)
    hex_web = _hex_from_tono(tono)
    tono_json = json.dumps(tono, ensure_ascii=False)

    if forzar:
        sql = """
            UPDATE public.color
            SET tono_canon = CAST(:tono AS jsonb),
                hex_web = :hex
            WHERE id = CAST(:id AS bigint)
        """
    else:
        sql = """
            UPDATE public.color
            SET tono_canon = CAST(:tono AS jsonb),
                hex_web = :hex
            WHERE id = CAST(:id AS bigint)
              AND (tono_canon IS NULL OR btrim(tono_canon->>'etiqueta') = '')
        """
    conn.execute(
        text(sql),
        {"tono": tono_json, "hex": hex_web, "id": color_id},
    )
    return True


def aplicar_tono_canon_si_vacio(
    conn: Connection,
    color_id: int,
    nombre: str | None,
    proveedor_id: int,
) -> bool:
    """Persiste tono_canon + hex_web solo si la fila aún no tiene tono operativo."""
    return aplicar_tono_canon_desde_nombre(
        conn, color_id, nombre, proveedor_id, forzar=False
    )
