"""Protocolo Imágenes Nexus — ramas proveedor 654/638 (LEY 2.01.04.021 §2)."""

from __future__ import annotations

import re

PROVEEDOR_CALZADO = 654
PROVEEDOR_CONFECCIONES_KYLY = 638
TIPO_V2_CALZADO = 1
TIPO_V2_CONFECCIONES = 2

TIER_PREFIX = re.compile(r"^(sm|md|lg|thumbs)/", re.IGNORECASE)


def strip_tier_from_path(raw: str) -> str:
    s = str(raw or "").strip()
    marker = "/storage/v1/object/public/productos/"
    if marker in s:
        from urllib.parse import unquote

        s = unquote(s.split(marker, 1)[1].split("?")[0].split("#")[0])
    s = s.replace("productos/", "").lstrip("/")
    return TIER_PREFIX.sub("", s)


def detect_protocol_from_stem(raw: str | None) -> str | None:
    s = strip_tier_from_path(raw or "")
    if not s:
        return None
    stem = re.sub(r"\.(jpe?g|png|webp)$", "", s, flags=re.IGNORECASE)
    if not stem:
        return None
    if "_" in stem and "-" not in stem:
        return "638"
    if "-" in stem:
        return "654"
    return None


def resolve_protocol(
    *,
    proveedor_importacion_id: int | None = None,
    tipo_v2_id: int | None = None,
    imagen_nombre: str | None = None,
) -> str:
    from_name = detect_protocol_from_stem(imagen_nombre)
    if from_name:
        return from_name
    if proveedor_importacion_id == PROVEEDOR_CONFECCIONES_KYLY or tipo_v2_id == TIPO_V2_CONFECCIONES:
        return "638"
    return "654"


def color_638_variants(color: str | int | None) -> list[str]:
    raw = str(color or "").strip()
    if not raw:
        return []
    no_k = re.sub(r"^[Kk]", "", raw)
    out: set[str] = set()
    out.add(no_k)
    stripped = re.sub(r"^0+", "", no_k)
    if stripped:
        out.add(stripped)
    if re.fullmatch(r"\d+", no_k):
        out.add(no_k.zfill(4))
    return [x for x in out if x]


def stems_638(linea: str | int | None, color: str | int | None) -> list[str]:
    linea_s = str(linea or "").strip()
    if linea_s.endswith(".0") and linea_s[:-2].isdigit():
        linea_s = linea_s[:-2]
    if not linea_s:
        return []
    colors = color_638_variants(color)
    return [f"{linea_s}_{c}" for c in colors]


def stem_654(
    linea: str | int | None,
    referencia: str | int | None,
    material: str | int | None,
    color: str | int | None,
) -> str | None:
    parts = [str(x or "").strip() for x in (linea, referencia, material, color)]
    parts = [p[:-2] if p.endswith(".0") and p[:-2].isdigit() else p for p in parts]
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return None
    if len(parts) >= 4:
        return "-".join(parts[:4])
    return "-".join(parts[:2])


def imagen_nombre_pe_sql() -> str:
    """Expresión SQL nombre archivo PE — dual 654/638 · excel_color Kyly (MIG-149)."""
    return """
    CASE
      WHEN pp.proveedor_importacion_id = 638
       AND NULLIF(btrim(ppd.linea), '') IS NOT NULL
       AND NULLIF(
         regexp_replace(
           COALESCE(
             (SELECT NULLIF(btrim(s.excel_color_code), '')
              FROM stock_pe_staging_migrated m
              JOIN stock_pronta_entrega_rimec s ON s.id = m.staging_id
              WHERE m.ppd_id = ppd.id
              ORDER BY s.id LIMIT 1),
             col_j.nombre,
             ''
           ),
           '^[Kk]', ''
         ),
         ''
       ) IS NOT NULL
      THEN btrim(ppd.linea) || '_'
           || regexp_replace(
             COALESCE(
               (SELECT NULLIF(btrim(s.excel_color_code), '')
                FROM stock_pe_staging_migrated m
                JOIN stock_pronta_entrega_rimec s ON s.id = m.staging_id
                WHERE m.ppd_id = ppd.id
                ORDER BY s.id LIMIT 1),
               col_j.nombre
             ),
             '^[Kk]', ''
           ) || '.jpg'
      WHEN COALESCE(ppd.linea, ''::text) <> ''
       AND COALESCE(ppd.referencia, ''::text) <> ''
       AND COALESCE(ppd.material_code, ''::text) <> ''
       AND COALESCE(ppd.color_code, ''::text) <> ''
      THEN ppd.linea || '-' || ppd.referencia || '-' || ppd.material_code || '-' || ppd.color_code || '.jpg'
      ELSE NULL::text
    END
    """
