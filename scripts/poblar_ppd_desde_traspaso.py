"""
Reconstruye `pedido_proveedor_detalle` desde `traspaso.snapshot_json`.

Motivación
----------
- `v_stock_rimec` lee de `pedido_proveedor_detalle` (la proforma del proveedor).
- En el demo actual los PP existen pero el detalle de proforma nunca se cargó.
- En cambio, los `traspaso` confirmados ya guardaron el detalle completo en
  `snapshot_json` (línea, referencia, material, color, tallas, id_pp, id_marca).
- Este script vuelca esa info al PPD para que rimec-web tenga catálogo sin
  necesidad de subir la Fatura Proforma desde Streamlit.

Salida esperada
---------------
Por cada traspaso con snapshot_json válido, inserta 1 fila en PPD por cada item
(par línea × referencia × material × color). Las cantidades por talla se
guardan en grades_json y en cantidad_pares como total.

Idempotente: borra previamente todas las filas de los PPs que va a poblar
(antes de re-insertar) para no duplicar.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# ── Conexión: misma URL que ya usaste en fix_traspasos_vacios.py ────────────
DB_URL = "postgresql://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"
engine = create_engine(DB_URL)


def _parse_snapshot(raw):
    """snapshot_json puede llegar como dict, str(json) o str(dict de Python)."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        try:
            return ast.literal_eval(raw)
        except Exception:
            return None


def main() -> int:
    procesados = 0
    insertados = 0
    saltados = 0

    with engine.begin() as conn:
        rows = conn.execute(text(
            """
            SELECT t.id, t.numero_registro, t.snapshot_json
            FROM traspaso t
            WHERE t.snapshot_json IS NOT NULL
            ORDER BY t.id
            """
        )).fetchall()

        pps_a_limpiar: set[int] = set()
        for _t_id, _numero, snap_raw in rows:
            snap = _parse_snapshot(snap_raw)
            if isinstance(snap, dict) and snap.get("id_pp"):
                pps_a_limpiar.add(int(snap["id_pp"]))

        if pps_a_limpiar:
            prev = conn.execute(text(
                "DELETE FROM pedido_proveedor_detalle "
                "WHERE pedido_proveedor_id = ANY(:ids)"
            ), {"ids": list(pps_a_limpiar)}).rowcount
            print(
                f"[init] limpiadas {prev} filas previas de "
                f"{len(pps_a_limpiar)} PPs antes de repoblar"
            )

        for t_id, numero, snap_raw in rows:
            snap = _parse_snapshot(snap_raw)
            if not isinstance(snap, dict):
                print(f"  [skip] {numero}: snapshot no parseable")
                saltados += 1
                continue

            id_pp = snap.get("id_pp")
            id_marca = snap.get("id_marca")
            numero_factura = snap.get("numero_factura")
            items = snap.get("items") or []
            if not id_pp or not items:
                print(f"  [skip] {numero}: id_pp={id_pp} items={len(items)}")
                saltados += 1
                continue

            pp_exists = conn.execute(text(
                "SELECT 1 FROM pedido_proveedor WHERE id = :id"
            ), {"id": id_pp}).fetchone()
            if not pp_exists:
                print(f"  [skip] {numero}: PP id={id_pp} no existe")
                saltados += 1
                continue

            procesados += 1
            for item in items:
                linea = str(item.get("linea") or "")
                referencia = str(item.get("referencia") or "")
                id_color = item.get("id_color")
                descp_color = item.get("color") or ""
                id_material = item.get("id_material")
                descp_material = item.get("material") or ""
                tallas = item.get("tallas") or {}
                if not isinstance(tallas, dict):
                    continue

                pares = 0
                grades = {}
                for k, v in tallas.items():
                    try:
                        qty = int(v or 0)
                    except (TypeError, ValueError):
                        qty = 0
                    if qty <= 0:
                        continue
                    pares += qty
                    grades[str(k)] = qty

                if pares <= 0:
                    continue

                style_code_lookup = conn.execute(text(
                    """
                    SELECT l.grupo_estilo_id
                    FROM linea l
                    WHERE l.codigo_proveedor::text = :linea
                    LIMIT 1
                    """
                ), {"linea": linea}).fetchone()
                style_code = (
                    str(style_code_lookup[0])
                    if style_code_lookup and style_code_lookup[0] is not None
                    else ""
                )

                material_code_row = None
                if id_material is not None:
                    material_code_row = conn.execute(text(
                        "SELECT codigo_proveedor::text FROM material "
                        "WHERE id = :id LIMIT 1"
                    ), {"id": id_material}).fetchone()
                if material_code_row is None and descp_material:
                    material_code_row = conn.execute(text(
                        "SELECT codigo_proveedor::text FROM material "
                        "WHERE descripcion = :d LIMIT 1"
                    ), {"d": descp_material}).fetchone()
                material_code = (
                    material_code_row[0] if material_code_row else None
                )

                color_code_row = None
                if id_color is not None:
                    color_code_row = conn.execute(text(
                        "SELECT codigo_proveedor::text FROM color "
                        "WHERE id = :id LIMIT 1"
                    ), {"id": id_color}).fetchone()
                if color_code_row is None and descp_color:
                    color_code_row = conn.execute(text(
                        "SELECT codigo_proveedor::text FROM color "
                        "WHERE nombre = :n LIMIT 1"
                    ), {"n": descp_color}).fetchone()
                color_code = color_code_row[0] if color_code_row else None

                conn.execute(text(
                    """
                    INSERT INTO pedido_proveedor_detalle (
                        pedido_proveedor_id,
                        linea, referencia,
                        id_marca,
                        id_material, descp_material, material_code,
                        id_color, descp_color, color_code,
                        cantidad, cantidad_pares, cantidad_cajas,
                        style_code, grades_json
                    ) VALUES (
                        :pp_id,
                        :linea, :ref,
                        :id_marca,
                        :id_material, :descp_material, :material_code,
                        :id_color, :descp_color, :color_code,
                        :pares, :pares, 0,
                        :style_code, CAST(:grades AS jsonb)
                    )
                    """
                ), {
                    "pp_id": id_pp,
                    "linea": linea,
                    "ref": referencia,
                    "id_marca": id_marca,
                    "id_material": id_material,
                    "descp_material": descp_material,
                    "material_code": material_code,
                    "id_color": id_color,
                    "descp_color": descp_color,
                    "color_code": color_code,
                    "pares": pares,
                    "style_code": style_code,
                    "grades": json.dumps(grades),
                })
                insertados += 1

            print(f"  [ok]   {numero}: PP={id_pp} factura={numero_factura} items={len(items)}")

        resumen = conn.execute(text(
            """
            SELECT pp.id, pp.numero_registro, pp.estado,
                   COUNT(ppd.id) AS items,
                   COALESCE(SUM(ppd.cantidad_pares), 0) AS pares
            FROM pedido_proveedor pp
            LEFT JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
            GROUP BY pp.id, pp.numero_registro, pp.estado
            ORDER BY pp.id
            """
        )).fetchall()

    print()
    print(f"Traspasos procesados: {procesados}")
    print(f"Filas insertadas en PPD: {insertados}")
    print(f"Saltados: {saltados}")
    print()
    print("=== Resumen por PP ===")
    print(f"{'pp_id':>6}  {'numero':<14}  {'estado':<10}  {'items':>5}  {'pares':>6}")
    for pp_id, numero, estado, items, pares in resumen:
        print(f"{pp_id:>6}  {numero:<14}  {estado:<10}  {items:>5}  {pares:>6}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
