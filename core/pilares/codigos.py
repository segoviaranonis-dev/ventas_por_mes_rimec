"""
Codificación bigint de códigos pilar por proveedor.

Kyly (638): ref sintética K → 11 · material = linea×100+11 (mismo proveedor, sin colisión 654).
Línea/color alfanuméricos: K+dígitos → int(dígitos); resto → SHA-256 estable (sin colisión suma_ords).

Vulnerabilidad 2026-07-22: sum(ord)*1000+len colisionaba K0460≡K9010 y K40009≡K40117.
"""

from __future__ import annotations

import hashlib
import re

# K = 11.ª letra — ref sintética única por línea en catálogo 638
KYLY_REF_CODIGO_PROVEEDOR = 11
KYLY_MATERIAL_SUFFIX = 11
KYLY_LINEA_ALPHA_BASE = 638_000_000_000
KYLY_COLOR_ALPHA_BASE = 638_001_000_000

# Códigos legacy generados con suma_ords (bloque 638_001_xxx) — UI/backfill
KYLY_COLOR_HASH_LEGACY_MIN = KYLY_COLOR_ALPHA_BASE
KYLY_COLOR_HASH_LEGACY_MAX = KYLY_COLOR_ALPHA_BASE + 999_999_999


def _canon(s: str) -> str:
    return str(s or "").strip()


def _kyly_alnum_to_bigint(s: str, base: int) -> int:
    """
    Kyly Excel: K0460 / k40009 → 460 / 40009 (sin colisión).
    Texto no numérico → SHA-256 truncado en bloque reservado (estable, bajo colisión).
    """
    s = _canon(s)
    m = re.fullmatch(r"[Kk]?0*(\d+)", s)
    if m:
        return int(m.group(1))
    if re.fullmatch(r"\d+", s):
        return int(s)
    digest = hashlib.sha256(s.upper().encode("utf-8")).hexdigest()
    # 8 dígitos en [10_000_000, 99_999_999] para no chocar con códigos Kyly cortos
    h = 10_000_000 + (int(digest[:12], 16) % 90_000_000)
    return base + h


def is_kyly_color_fk_hash(codigo: str | int | None) -> bool:
    """True si el color_code parece FK legacy/hash 638_001_* (no código Kyly legible)."""
    s = _canon(str(codigo) if codigo is not None else "")
    if not re.fullmatch(r"\d+", s):
        return False
    n = int(s)
    return KYLY_COLOR_HASH_LEGACY_MIN <= n <= KYLY_COLOR_HASH_LEGACY_MAX


def pilar_codigo_to_bigint(codigo: str | int | None, proveedor_id: int) -> int | None:
    """Numérico directo · Kyly alfanumérico → K+dígitos o SHA-256 en bloque línea."""
    s = _canon(codigo)
    if not s or s.lower() in ("nan", "none"):
        return None
    if re.fullmatch(r"\d+", s):
        return int(s)
    if int(proveedor_id) == 638:
        return _kyly_alnum_to_bigint(s, KYLY_LINEA_ALPHA_BASE)
    return None


def linea_codigo_to_bigint(codigo: str | int | None, proveedor_id: int) -> int | None:
    return pilar_codigo_to_bigint(codigo, proveedor_id)


def referencia_codigo_kyly(_linea_codigo: str | int | None = None) -> int:
    return KYLY_REF_CODIGO_PROVEEDOR


def referencia_codigo_from_excel(codigo: str | int | None) -> int | None:
    s = _canon(codigo)
    if not s or s.upper() == "K":
        return KYLY_REF_CODIGO_PROVEEDOR
    if re.fullmatch(r"\d+", s):
        return int(s)
    return pilar_codigo_to_bigint(s, 638)


def material_codigo_kyly(linea_codigo: str | int | None) -> int | None:
    ln = linea_codigo_to_bigint(linea_codigo, 638)
    if ln is None:
        return None
    return ln * 100 + KYLY_MATERIAL_SUFFIX


def material_codigo_from_excel(material: str | int | None, linea: str | int | None) -> int | None:
    for src in (material, linea):
        cod = pilar_codigo_to_bigint(src, 638)
        if cod is not None:
            return cod
    return None


def color_codigo_to_bigint(codigo: str | int | None, proveedor_id: int) -> int | None:
    s = _canon(codigo)
    if not s or s.lower() in ("nan", "none"):
        return None
    if re.fullmatch(r"\d+", s):
        n = int(s)
        # No re-hashear FKs legacy ya persistidos
        if int(proveedor_id) == 638 and is_kyly_color_fk_hash(n):
            return n
        return n
    if int(proveedor_id) == 638:
        return _kyly_alnum_to_bigint(s, KYLY_COLOR_ALPHA_BASE)
    return None
