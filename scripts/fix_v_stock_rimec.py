"""
Unifica Proforma ↔ Excel-normalizado sin tocar el Frontend.

- linea_codigo / referencia_codigo: texto del pedido (orden típico marca, linea_codigo, …).
- CAST seguro solo-dígitos → linea_id / referencia_id desde el texto de proforma.
- JOIN linea_referencia en esos bigint (misma clave que pobló el Excel).
- grupo_estilo_id: preferido desde lr; fallback numeric puro en style_code si no hubo match.
- style_code: sigue existiendo; valor expuesto prioriza el grupo_estilo_id efectivo (normalizado).
- descp_grupo_estilo / descp_tipo_1: textos para pantalla (lr + maestras); sin alias estilo/tipo_1.

Requiere columnas lr.descp_grupo_estilo y lr.descp_tipo_1 si existen ( migración 017 ).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pandas as pd

from core.database import engine, get_dataframe
from sqlalchemy import text

SQL = r"""
CREATE OR REPLACE VIEW v_stock_rimec AS
SELECT ppd.id AS det_id,
    pp.id AS pp_id,
    pp.numero_registro AS pp_nro,
    COALESCE(pp.numero_proforma, '') AS proforma,
    (pp.fecha_arribo_estimada)::text AS eta,
    pp.estado AS pp_estado,
    ppd.id_marca::bigint AS marca_id,
    COALESCE(mv.descp_marca, '—') AS descp_marca,
    COALESCE(lr.linea_id, x.cast_linea_id)::bigint AS linea_id,
    COALESCE(lr.referencia_id, x.cast_referencia_id)::bigint AS referencia_id,
    COALESCE(lr.grupo_estilo_id, x.cast_style_id)::bigint AS grupo_estilo_id,
    lr.tipo_1_id::bigint AS tipo_1_id,
    COALESCE(ppd.linea, '') AS linea_codigo,
    COALESCE(ppd.referencia, '') AS referencia_codigo,
    COALESCE(
        (COALESCE(lr.grupo_estilo_id, x.cast_style_id))::text,
        btrim(COALESCE(ppd.style_code::text, '')),
        ''
    ) AS style_code,
    COALESCE(ppd.nombre, '') AS nombre,
    COALESCE(ppd.material_code, '') AS material_code,
    COALESCE(ppd.descp_material, '') AS descp_material,
    COALESCE(ppd.color_code, '') AS color_code,
    COALESCE(ppd.descp_color, '') AS descp_color,
    -- Hex del pilar `color` (chip del frontend lee este valor)
    col_j.hex_web AS color_hex,
    ppd.grades_json,
    COALESCE(ppd.cantidad_cajas, 0) AS cantidad_cajas,
    COALESCE(ppd.cantidad_pares, 0) AS cantidad_pares,
    CASE
        WHEN COALESCE(ppd.cantidad_cajas, 0) > 0 THEN ppd.cantidad_pares / ppd.cantidad_cajas
        ELSE 0
    END AS pares_por_caja,
    ppd.unit_fob_ajustado,
    pl.lpn,
    pl.lpc02,
    pl.lpc03,
    pl.lpc04,
    pl.nombre_caso_aplicado AS caso_precio,
    -- Caso conceptual asignado a la linea (fuente unica: linea.caso_id)
    l.caso_id AS caso_id,
    COALESCE(cpb.nombre_caso, '') AS descp_caso,
    COALESCE(lr.descp_grupo_estilo, ge.descp_grupo_estilo, '') AS descp_grupo_estilo,
    COALESCE(lr.descp_tipo_1, t1.descp_tipo_1, '') AS descp_tipo_1,
    CASE
        WHEN COALESCE(ppd.linea, '') <> ''
         AND COALESCE(ppd.referencia, '') <> ''
         AND COALESCE(ppd.material_code, '') <> ''
         AND COALESCE(ppd.color_code, '') <> ''
        THEN 'https://extrlcvcgypwazxipvqm.supabase.co/storage/v1/object/public/productos/'
             || ppd.linea || '-' || ppd.referencia || '-'
             || ppd.material_code || '-' || ppd.color_code || '.jpg'
        ELSE NULL
    END AS imagen_url
FROM pedido_proveedor_detalle ppd
JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
LEFT JOIN material m ON m.codigo_proveedor::text = ppd.material_code
LEFT JOIN linea l ON l.codigo_proveedor::text = ppd.linea
LEFT JOIN caso_precio_biblioteca cpb ON cpb.id = l.caso_id
-- Lookup del hex del color desde el pilar
LEFT JOIN color col_j ON col_j.codigo_proveedor::text = ppd.color_code
                     AND col_j.activo = TRUE
LEFT JOIN referencia ref_j
    ON ref_j.codigo_proveedor::text = ppd.referencia
   AND ref_j.linea_id = l.id
CROSS JOIN LATERAL (
    SELECT
        CASE
            WHEN nullif(btrim(ppd.linea::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.linea::text)::bigint
            ELSE NULL::bigint
        END AS cast_linea_id,
        CASE
            WHEN nullif(btrim(ppd.referencia::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.referencia::text)::bigint
            ELSE NULL::bigint
        END AS cast_referencia_id,
        CASE
            WHEN nullif(btrim(ppd.style_code::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.style_code::text)::bigint
            ELSE NULL::bigint
        END AS cast_style_id
) x
LEFT JOIN linea_referencia lr
    ON lr.linea_id = x.cast_linea_id
   AND lr.referencia_id = x.cast_referencia_id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = COALESCE(lr.grupo_estilo_id, x.cast_style_id)
LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
LEFT JOIN LATERAL (
    SELECT pl2.lpn, pl2.lpc02, pl2.lpc03, pl2.lpc04, pl2.nombre_caso_aplicado
    FROM precio_lista pl2
    WHERE pl2.evento_id = COALESCE(ic.precio_evento_id, (
        SELECT pe.id FROM precio_evento pe
        WHERE pe.estado = 'cerrado'
        ORDER BY pe.created_at DESC
        LIMIT 1
    ))
    AND pl2.linea_id = ref_j.linea_id
    AND pl2.referencia_id = ref_j.id
    AND pl2.material_id = m.id
    LIMIT 1
) pl ON true
WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
  AND COALESCE(ppd.cantidad_pares, 0) > 0;
"""


def main() -> None:
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 240)
    pd.set_option("display.max_colwidth", 120)

    with engine.begin() as conn:
        conn.execute(text("DROP VIEW IF EXISTS v_stock_rimec CASCADE"))
        conn.execute(text(SQL))
    print("OK — v_stock_rimec recreada (CAST línea/ref + JOIN lr; style_code alineado a grupo_estilo_id)")

    df = get_dataframe("SELECT * FROM v_stock_rimec ORDER BY descp_marca, linea_codigo, referencia_codigo LIMIT 10")
    if df is not None and not df.empty:
        print("\n—— Primeras 10 filas (todas las columnas) ——\n")
        print(df.to_string(index=False))
    else:
        print("\nSin filas que cumplan el WHERE (ABIERTO/ENVIADO con pares) o vista vacía.")


if __name__ == "__main__":
    main()
