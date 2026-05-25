"""OT-009: Rastreo cadena precio para 1 SKU muestra."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from sqlalchemy import text
from core.database import engine

DET_ID = None  # se setea del primer SKU con stock


def q(conn, label, sql, params=None):
    print(f"\n{'='*60}\n{label}\n{'='*60}")
    r = conn.execute(text(sql), params or {})
    rows = r.fetchall()
    cols = list(r.keys()) if hasattr(r, "keys") else []
    if not rows:
        print("(sin filas)")
        return rows
    for row in rows[:15]:
        print(dict(zip(cols, row)) if cols else row)
    if len(rows) > 15:
        print(f"... +{len(rows)-15} filas")
    return rows


def main():
    with engine.connect() as conn:
        # Muestra
        rows = q(
            conn,
            "SKU muestra",
            """
            SELECT det_id, pp_id, pp_nro, descp_marca, linea_codigo, referencia_codigo, material_code, lpn
            FROM v_stock_rimec
            WHERE cajas_disponibles > 0
            ORDER BY pp_id, det_id
            LIMIT 1
            """,
        )
        if not rows:
            print("Sin SKUs en vista")
            return
        det_id, pp_id = rows[0]["det_id"], rows[0]["pp_id"]
        print(f"\n>>> Rastreando det_id={det_id} pp_id={pp_id}")

        q(
            conn,
            "Paso 2 — intencion_compra_pedido",
            """
            SELECT icp.id, icp.precio_evento_id, ic.id_marca AS ic_marca,
                   (SELECT id_marca FROM pedido_proveedor_detalle WHERE id = :det) AS ppd_marca
            FROM intencion_compra_pedido icp
            JOIN intencion_compra ic ON ic.id = icp.intencion_compra_id
            WHERE icp.pedido_proveedor_id = :pp
            """,
            {"pp": pp_id, "det": det_id},
        )

        q(
            conn,
            "Paso 3-5 — linea / referencia / material",
            """
            SELECT ppd.id AS det_id,
                   ppd.linea AS cod_linea_pp, l.id AS linea_id, l.codigo_proveedor AS cod_linea_tabla,
                   ppd.referencia AS cod_ref_pp, r.id AS referencia_id,
                   ppd.material_code AS cod_mat_pp, m.id AS material_id,
                   pp.proveedor_importacion_id AS prov_pp
            FROM pedido_proveedor_detalle ppd
            JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
            LEFT JOIN linea l ON l.codigo_proveedor::text = ppd.linea AND l.proveedor_id = pp.proveedor_importacion_id
            LEFT JOIN referencia r ON r.codigo_proveedor::text = ppd.referencia AND r.linea_id = l.id
            LEFT JOIN material m ON m.codigo_proveedor::text = ppd.material_code AND m.proveedor_id = pp.proveedor_importacion_id
            WHERE ppd.id = :det
            """,
            {"det": det_id},
        )

        ev_rows = q(
            conn,
            "precio_lista — conteo por evento del PP",
            """
            SELECT pl.evento_id, COUNT(*) AS filas, COUNT(*) FILTER (WHERE lpn > 0) AS con_lpn
            FROM precio_lista pl
            WHERE pl.evento_id IN (
                SELECT DISTINCT icp.precio_evento_id
                FROM intencion_compra_pedido icp
                WHERE icp.pedido_proveedor_id = :pp AND icp.precio_evento_id IS NOT NULL
            )
            GROUP BY pl.evento_id
            """,
            {"pp": pp_id},
        )

        q(
            conn,
            "Paso 6 — match triplete (como la vista)",
            """
            WITH ev AS (
              SELECT icp2.precio_evento_id
              FROM intencion_compra_pedido icp2
              JOIN intencion_compra ic2 ON ic2.id = icp2.intencion_compra_id
              JOIN pedido_proveedor_detalle ppd ON ppd.id = :det
              WHERE icp2.pedido_proveedor_id = :pp
                AND icp2.precio_evento_id IS NOT NULL
                AND (ppd.id_marca IS NULL OR ic2.id_marca = ppd.id_marca::bigint)
              ORDER BY CASE WHEN ppd.id_marca IS NOT NULL AND ic2.id_marca = ppd.id_marca::bigint THEN 0 ELSE 1 END, icp2.id
              LIMIT 1
            ),
            ids AS (
              SELECT ppd.id, pp.proveedor_importacion_id, ppd.linea, ppd.referencia, ppd.material_code,
                     l.id AS linea_id, r.id AS referencia_id, m.id AS material_id
              FROM pedido_proveedor_detalle ppd
              JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
              LEFT JOIN linea l ON l.codigo_proveedor::text = ppd.linea AND l.proveedor_id = pp.proveedor_importacion_id
              LEFT JOIN referencia r ON r.codigo_proveedor::text = ppd.referencia AND r.linea_id = l.id
              LEFT JOIN material m ON m.codigo_proveedor::text = ppd.material_code AND m.proveedor_id = pp.proveedor_importacion_id
              WHERE ppd.id = :det
            )
            SELECT ev.precio_evento_id, i.*,
                   (SELECT COUNT(*) FROM precio_lista pl
                    WHERE pl.evento_id = ev.precio_evento_id
                      AND pl.linea_id = i.linea_id AND pl.referencia_id = i.referencia_id AND pl.material_id = i.material_id) AS pl_match_triplete,
                   (SELECT COUNT(*) FROM precio_lista pl
                    WHERE pl.evento_id = ev.precio_evento_id
                      AND pl.linea_id = i.linea_id AND pl.referencia_id = i.referencia_id) AS pl_match_sin_material
            FROM ev, ids i
            """,
            {"pp": pp_id, "det": det_id},
        )


if __name__ == "__main__":
    main()
