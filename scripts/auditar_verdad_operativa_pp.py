#!/usr/bin/env python3
"""
Auditoria read-only de verdad operativa PP -> FI -> Traspaso -> Movimiento -> Web.

Uso:
  python scripts/auditar_verdad_operativa_pp.py --pp PP-2026-0010
  python scripts/auditar_verdad_operativa_pp.py --pp PP-2026-0010 --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal


def _connect():
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:
        raise SystemExit(
            "Falta psycopg2. Instalar temporalmente con: python -m pip install psycopg2-binary"
        ) from exc

    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Faltan variables de entorno DB: {', '.join(missing)}")

    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode="require",
        cursor_factory=RealDictCursor,
    )
    return conn


def _num(value) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def auditar_pp(pp_nro: str) -> dict:
    sql = """
    WITH pp AS (
      SELECT id, numero_registro, estado
      FROM pedido_proveedor
      WHERE numero_registro = %(pp_nro)s
    ),
    ppd AS (
      SELECT
        ppd.id,
        ppd.linea,
        ppd.referencia,
        ppd.material_code,
        ppd.color_code,
        ppd.id_material,
        ppd.id_color,
        ppd.descp_material,
        ppd.descp_color,
        COALESCE(ppd.cantidad_pares, 0)::bigint AS cantidad_pares,
        COALESCE(ppd.pares_vendidos, 0)::bigint AS pares_vendidos
      FROM pedido_proveedor_detalle ppd
      WHERE ppd.pedido_proveedor_id = (SELECT id FROM pp)
        AND ppd.referencia IS NOT NULL
    ),
    fi AS (
      SELECT
        fi.id AS fi_id,
        fi.nro_factura,
        fi.estado,
        fid.id AS fid_id,
        fid.ppd_id,
        COALESCE(fid.pares, 0)::bigint AS pares,
        COALESCE(fid.cajas, 0)::bigint AS cajas
      FROM factura_interna fi
      JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
      WHERE fi.pp_id = (SELECT id FROM pp)
        AND fi.estado <> 'ANULADA'
    ),
    trp AS (
      SELECT
        t.id AS traspaso_id,
        t.numero_registro AS traspaso_nro,
        t.documento_ref,
        t.estado,
        t.almacen_destino_id
      FROM traspaso t
      WHERE t.documento_ref IN (SELECT nro_factura FROM fi)
    ),
    td AS (
      SELECT td.traspaso_id, td.combinacion_id, SUM(td.cantidad)::bigint AS pares
      FROM traspaso_detalle td
      WHERE td.traspaso_id IN (SELECT traspaso_id FROM trp)
      GROUP BY td.traspaso_id, td.combinacion_id
    ),
    mov AS (
      SELECT
        m.id AS movimiento_id,
        m.documento_ref,
        md.combinacion_id,
        SUM(md.cantidad * md.signo)::bigint AS pares
      FROM movimiento m
      JOIN movimiento_detalle md ON md.movimiento_id = m.id
      WHERE m.documento_ref IN (SELECT traspaso_nro FROM trp)
        AND m.almacen_destino_id = 1
        AND m.estado = 'CONFIRMADO'
      GROUP BY m.id, m.documento_ref, md.combinacion_id
    ),
    web AS (
      SELECT combinacion_id, SUM(stock_web)::bigint AS pares
      FROM v_stock_web
      GROUP BY combinacion_id
    )
    SELECT
      (SELECT id FROM pp) AS pp_id,
      (SELECT estado FROM pp) AS pp_estado,
      COALESCE((SELECT SUM(cantidad_pares) FROM ppd), 0)::bigint AS pp_pares,
      COALESCE((SELECT SUM(pares_vendidos) FROM ppd), 0)::bigint AS pp_vendidos,
      COALESCE((SELECT SUM(pares) FROM fi), 0)::bigint AS fi_pares,
      COALESCE((SELECT SUM(pares) FROM td), 0)::bigint AS traspaso_pares,
      COALESCE((SELECT SUM(pares) FROM mov), 0)::bigint AS movimiento_pares,
      COALESCE((SELECT SUM(web.pares) FROM web JOIN td ON td.combinacion_id = web.combinacion_id), 0)::bigint AS web_pares,
      (SELECT COUNT(*) FROM ppd)::int AS ppd_rows,
      (SELECT COUNT(DISTINCT nro_factura) FROM fi)::int AS fi_count,
      (SELECT COUNT(DISTINCT traspaso_id) FROM trp)::int AS trp_count,
      (SELECT COUNT(DISTINCT movimiento_id) FROM mov)::int AS mov_count;
    """

    detail_sql = """
    WITH pp AS (
      SELECT id FROM pedido_proveedor WHERE numero_registro = %(pp_nro)s
    )
    SELECT
      ppd.id AS ppd_id,
      ppd.linea,
      ppd.referencia,
      ppd.material_code,
      ppd.color_code,
      ppd.descp_material,
      ppd.descp_color,
      COALESCE(ppd.cantidad_pares, 0)::bigint AS pp_pares,
      COALESCE(ppd.pares_vendidos, 0)::bigint AS pp_vendidos,
      COALESCE(SUM(fid.pares) FILTER (WHERE fi.estado <> 'ANULADA'), 0)::bigint AS fi_pares
    FROM pedido_proveedor_detalle ppd
    LEFT JOIN factura_interna_detalle fid ON fid.ppd_id = ppd.id
    LEFT JOIN factura_interna fi ON fi.id = fid.factura_id
    WHERE ppd.pedido_proveedor_id = (SELECT id FROM pp)
      AND ppd.referencia IS NOT NULL
    GROUP BY ppd.id, ppd.linea, ppd.referencia, ppd.material_code, ppd.color_code,
             ppd.descp_material, ppd.descp_color, ppd.cantidad_pares, ppd.pares_vendidos
    ORDER BY ppd.id;
    """

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"pp_nro": pp_nro})
            summary = dict(cur.fetchone() or {})
            cur.execute(detail_sql, {"pp_nro": pp_nro})
            details = [dict(row) for row in cur.fetchall()]

    if not summary.get("pp_id"):
        return {"pp": pp_nro, "status": "BUG", "errores": ["PP no encontrado"], "summary": summary, "details": []}

    errores: list[str] = []
    warnings: list[str] = []

    pp_vendidos = _num(summary["pp_vendidos"])
    fi_pares = _num(summary["fi_pares"])
    traspaso_pares = _num(summary["traspaso_pares"])
    movimiento_pares = _num(summary["movimiento_pares"])
    web_pares = _num(summary["web_pares"])

    if fi_pares and pp_vendidos and fi_pares != pp_vendidos:
        warnings.append(f"FI activa ({fi_pares}) difiere de pares_vendidos PPD ({pp_vendidos})")
    if traspaso_pares and traspaso_pares != fi_pares:
        errores.append(f"Traspaso ({traspaso_pares}) difiere de FI ({fi_pares})")
    if movimiento_pares and movimiento_pares != traspaso_pares:
        errores.append(f"Movimiento ({movimiento_pares}) difiere de traspaso ({traspaso_pares})")
    if web_pares and movimiento_pares and web_pares != movimiento_pares:
        errores.append(f"Web ({web_pares}) difiere de movimiento ({movimiento_pares})")

    status = "BUG" if errores else ("WARN" if warnings else "OK")
    return {
        "pp": pp_nro,
        "status": status,
        "errores": errores,
        "warnings": warnings,
        "summary": {k: _num(v) if isinstance(v, Decimal) else v for k, v in summary.items()},
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pp", action="append", required=True, help="Numero PP, ej. PP-2026-0010. Repetible.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    results = [auditar_pp(pp) for pp in args.pp]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    else:
        for result in results:
            s = result["summary"]
            print(f"{result['status']} {result['pp']} estado={s.get('pp_estado')} pp={s.get('pp_pares')} vendidos={s.get('pp_vendidos')} fi={s.get('fi_pares')} trp={s.get('traspaso_pares')} mov={s.get('movimiento_pares')} web={s.get('web_pares')}")
            for msg in result["errores"]:
                print(f"  BUG: {msg}")
            for msg in result["warnings"]:
                print(f"  WARN: {msg}")
    return 1 if any(r["status"] == "BUG" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
