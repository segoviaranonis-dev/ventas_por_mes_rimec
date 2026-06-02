-- Diagnóstico trazabilidad PPD -> FI
-- Molécula: línea 4853, referencia 100, material 30340, color 104721.
-- Ley Director: cantidad por caja sale de pedido_proveedor_detalle por ppd_id.

WITH mol AS (
  SELECT
    ppd.id AS ppd_id,
    pp.id AS pp_id,
    pp.numero_registro AS pp_nro,
    pp.numero_proforma AS proforma,
    ppd.linea,
    ppd.referencia,
    ppd.material_code,
    ppd.color_code,
    ppd.descp_material,
    ppd.descp_color,
    ppd.grada,
    ppd.grades_json,
    ppd.cantidad_cajas,
    ppd.cantidad_pares,
    COALESCE(ppd.pares_vendidos, 0) AS pares_vendidos,
    CASE
      WHEN COALESCE(ppd.cantidad_cajas, 0) > 0
      THEN ppd.cantidad_pares::numeric / ppd.cantidad_cajas
      ELSE NULL
    END AS pares_por_caja_ppd,
    (
      SELECT COALESCE(SUM(v::int), 0)
      FROM jsonb_each_text(COALESCE(ppd.grades_json, '{}'::jsonb)) AS g(k, v)
    ) AS pares_por_caja_grades_json
  FROM pedido_proveedor_detalle ppd
  JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
  WHERE ppd.linea::text = '4853'
    AND ppd.referencia::text = '100'
    AND ppd.material_code::text = '30340'
    AND ppd.color_code::text = '104721'
),
fi AS (
  SELECT
    fid.id AS fid_id,
    fid.ppd_id,
    fi.id AS fi_id,
    fi.nro_factura,
    fi.estado,
    fid.cajas AS fi_cajas,
    fid.pares AS fi_pares,
    CASE
      WHEN COALESCE(fid.cajas, 0) > 0
      THEN fid.pares::numeric / fid.cajas
      ELSE NULL
    END AS pares_por_caja_fi,
    fid.linea_snapshot,
    fid.linea_snapshot->>'gradas_fmt' AS snapshot_gradas_fmt
  FROM factura_interna_detalle fid
  JOIN factura_interna fi ON fi.id = fid.factura_id
  WHERE fi.estado <> 'ANULADA'
    AND (
      fid.ppd_id IN (SELECT ppd_id FROM mol)
      OR (
        fid.linea_snapshot->>'linea_codigo' = '4853'
        AND fid.linea_snapshot->>'ref_codigo' = '100'
      )
    )
)
SELECT
  m.pp_nro,
  m.proforma,
  m.ppd_id,
  m.linea,
  m.referencia,
  m.material_code,
  m.color_code,
  m.descp_color,
  m.grada,
  m.cantidad_cajas AS ppd_cajas,
  m.cantidad_pares AS ppd_pares,
  m.pares_vendidos,
  m.pares_por_caja_ppd,
  m.pares_por_caja_grades_json,
  vs.pares_por_caja AS pares_por_caja_v_stock,
  vs.saldo_pares,
  vs.cajas_disponibles,
  fi.fi_id,
  fi.fid_id,
  fi.nro_factura,
  fi.estado AS fi_estado,
  fi.fi_cajas,
  fi.fi_pares,
  fi.pares_por_caja_fi,
  fi.snapshot_gradas_fmt,
  fi.linea_snapshot
FROM mol m
LEFT JOIN v_stock_rimec vs ON vs.det_id = m.ppd_id
LEFT JOIN fi ON fi.ppd_id = m.ppd_id
ORDER BY m.pp_nro, m.ppd_id, fi.fi_id, fi.fid_id;
