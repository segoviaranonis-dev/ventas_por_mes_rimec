"""
Resolución FK pilares Kyly (proveedor 638, tipo_v2_id=2).

Proveedor 638 aislado de 654 — códigos Excel tal cual en catálogo (bigint).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from core.pilares import (
    PROVEEDOR_ID_CONFECCIONES,
    color_codigo_to_bigint,
    linea_codigo_to_bigint,
    material_codigo_from_excel,
    referencia_codigo_from_excel,
    upsert_color,
    upsert_linea,
    upsert_material,
    upsert_referencia,
)
from modules.rimec_engine.lr_schema import linea_referencia_tiene_codigos_proveedor

KYLY_REF_TEXTO = "K"
MARCAS_NINOS = {5, 6}


def safe_int_or_none(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "<na>", "nat"):
        return None
    try:
        f = float(s.replace(",", "."))
        if pd.isna(f):
            return None
        i = int(f)
        if float(i) != f:
            return None
        return i
    except (ValueError, TypeError, OverflowError):
        return None


def _cell_str(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s


def _normalize_kyly_excel_row(row: pd.Series) -> tuple[str, str, str, str]:
    """LINEA/REF/MATERIAL/COLOR — corrige filas con LINEA=K y REF numérico."""
    lc = _cell_str(row.get("linea_codigo_proveedor"))
    rc = _cell_str(row.get("referencia_codigo_proveedor"))
    mat = _cell_str(row.get("excel_material_code"))
    col = _cell_str(row.get("excel_color_code"))

    if lc.upper() == KYLY_REF_TEXTO and rc.isdigit():
        lc, rc = rc, KYLY_REF_TEXTO
    if not lc and mat:
        lc = mat
    if not rc:
        rc = KYLY_REF_TEXTO
    if not mat:
        mat = lc
    return lc, rc, mat, col


def _ensure_linea_referencia(
    conn: Connection,
    linea_id: int,
    referencia_id: int,
    proveedor_id: int,
    ref_cod: int,
) -> None:
    if conn.execute(
        text(
            """
            SELECT 1 FROM public.linea_referencia
            WHERE linea_id = CAST(:l AS bigint) AND referencia_id = CAST(:r AS bigint)
            LIMIT 1
            """
        ),
        {"l": linea_id, "r": referencia_id},
    ).fetchone():
        return

    if linea_referencia_tiene_codigos_proveedor(conn):
        conn.execute(
            text(
                """
                INSERT INTO public.linea_referencia (
                    linea_id, referencia_id, proveedor_id,
                    codigo_proveedor, linea_codigo_proveedor, referencia_codigo_proveedor
                )
                SELECT
                    CAST(:lid AS bigint), CAST(:rid AS bigint), CAST(:p AS bigint),
                    pi.codigo::text,
                    l.codigo_proveedor,
                    CAST(:rc AS bigint)
                FROM public.linea l
                CROSS JOIN public.proveedor_importacion pi
                WHERE l.id = CAST(:lid AS bigint) AND pi.id = CAST(:p AS bigint)
                ON CONFLICT (linea_id, referencia_id) DO NOTHING
                """
            ),
            {
                "lid": linea_id,
                "rid": referencia_id,
                "p": proveedor_id,
                "rc": ref_cod,
            },
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO public.linea_referencia (linea_id, referencia_id, proveedor_id)
                VALUES (CAST(:lid AS bigint), CAST(:rid AS bigint), CAST(:p AS bigint))
                ON CONFLICT (linea_id, referencia_id) DO NOTHING
                """
            ),
            {"lid": linea_id, "rid": referencia_id, "p": proveedor_id},
        )


def _resolve_cliente_id(row: pd.Series) -> int | None:
    origen = str(row.get("origen_holding", "")).strip().lower()
    marca_id = row.get("marca_id")
    if not origen or "rimec" in origen or "import" in origen:
        return None
    es_ninos = marca_id in MARCAS_NINOS
    if "fernando" in origen:
        return 2900 if es_ninos else 2100
    if "san" in origen and "mart" in origen:
        return 2700 if es_ninos else 2400
    if "palma" in origen:
        return 3200 if es_ninos else 3100
    return None


def resolve_confecciones_fks(engine: Engine, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Provisiona pilares 638 (aislado de 654) y devuelve FK numéricas."""
    if df.empty:
        return df.copy(), []

    pid = PROVEEDOR_ID_CONFECCIONES
    warns: list[str] = []
    linea_cache: dict[int, int] = {}
    ref_cache: dict[tuple[int, int], int] = {}
    mat_cache: dict[int, int] = {}
    color_cache: dict[int, int] = {}

    linea_ids: list[int | None] = []
    referencia_ids: list[int | None] = []
    material_ids: list[int | None] = []
    color_ids: list[int | None] = []
    marca_ids: list[int | None] = []
    genero_ids: list[int | None] = []
    ge_ids: list[int | None] = []
    t1_ids: list[int | None] = []
    cliente_ids: list[int | None] = []

    with engine.begin() as conn:
        for _, row in df.iterrows():
            lc_text, rc_text, mat_text, col_text = _normalize_kyly_excel_row(row)

            lc_big = linea_codigo_to_bigint(lc_text, pid)
            ref_big = referencia_codigo_from_excel(rc_text)
            mat_big = material_codigo_from_excel(mat_text, lc_text)
            col_big = color_codigo_to_bigint(col_text, pid) if col_text else None

            if lc_big is None or ref_big is None or mat_big is None:
                warns.append(
                    f"Kyly fila incompleta L={lc_text!r} R={rc_text!r} M={mat_text!r}"
                )
                linea_ids.append(None)
                referencia_ids.append(None)
                material_ids.append(None)
                color_ids.append(None)
                marca_ids.append(None)
                genero_ids.append(None)
                ge_ids.append(None)
                t1_ids.append(None)
                cliente_ids.append(None)
                continue

            if lc_big not in linea_cache:
                desc = lc_text if not lc_text.isdigit() else None
                linea_cache[lc_big] = upsert_linea(
                    conn,
                    lc_big,
                    pid,
                    descripcion=desc,
                    marca_id=None,
                    genero_id=None,
                    grupo_estilo_id=None,
                    fuente="retail",
                )
            lid = linea_cache[lc_big]

            lr_key = (lid, ref_big)
            if lr_key not in ref_cache:
                ref_cache[lr_key] = upsert_referencia(
                    conn,
                    ref_big,
                    lid,
                    pid,
                    descripcion=None if ref_big != 11 else f"Ref {KYLY_REF_TEXTO}",
                    fuente="retail",
                )
                _ensure_linea_referencia(conn, lid, ref_cache[lr_key], pid, ref_big)
            rid = ref_cache[lr_key]

            if mat_big not in mat_cache:
                mat_cache[mat_big] = upsert_material(
                    conn,
                    mat_big,
                    pid,
                    descripcion=mat_text if mat_text and not mat_text.isdigit() else None,
                    fuente="retail",
                )
            mid = mat_cache[mat_big]

            cid: int | None = None
            if col_big is not None:
                if col_big not in color_cache:
                    color_cache[col_big] = upsert_color(
                        conn,
                        col_big,
                        pid,
                        nombre=col_text if col_text and not col_text.isdigit() else None,
                        fuente="retail",
                    )
                cid = color_cache[col_big]
            elif col_text:
                warns.append(f"Kyly color no resuelto: {col_text!r}")

            linea_ids.append(lid)
            referencia_ids.append(rid)
            material_ids.append(mid)
            color_ids.append(cid)
            marca_ids.append(None)
            genero_ids.append(None)
            ge_ids.append(None)
            t1_ids.append(None)
            cliente_ids.append(_resolve_cliente_id(row))

    out = df.copy()
    out["linea_id"] = linea_ids
    out["referencia_id"] = referencia_ids
    out["material_id"] = material_ids
    out["color_id"] = color_ids
    out["marca_id"] = marca_ids
    out["genero_id"] = genero_ids
    out["grupo_estilo_id"] = ge_ids
    out["tipo_1_id"] = t1_ids
    out["cliente_id"] = cliente_ids
    return out, warns
