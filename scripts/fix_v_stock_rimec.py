"""
Fix v_stock_rimec: reescribe el LATERAL para unir precio_lista via referencia
en vez de via linea.codigo_proveedor (que no existe para codigos reales 2164,2182).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.database import engine
from sqlalchemy import text

SQL = """
CREATE OR REPLACE VIEW v_stock_rimec AS
SELECT ppd.id AS det_id,
    pp.id AS pp_id,
    pp.numero_registro AS pp_nro,
    COALESCE(pp.numero_proforma, '') AS proforma,
    (pp.fecha_arribo_estimada)::text AS eta,
    pp.estado AS pp_estado,
    COALESCE(mv.descp_marca, '—') AS marca,
    COALESCE(ppd.linea, '') AS linea_codigo,
    COALESCE(ppd.referencia, '') AS referencia_codigo,
    COALESCE(ppd.nombre, '') AS nombre,
    COALESCE(ppd.style_code, '') AS style_code,
    COALESCE(ppd.material_code, '') AS material_code,
    COALESCE(ppd.descp_material, '') AS material_descripcion,
    COALESCE(ppd.color_code, '') AS color_code,
    COALESCE(ppd.descp_color, '') AS color_nombre,
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
    pl.nombre_caso_aplicado AS caso_precio
FROM pedido_proveedor_detalle ppd
JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
LEFT JOIN material m ON m.codigo_proveedor::text = ppd.material_code
LEFT JOIN referencia ref_j ON ref_j.codigo_proveedor::text = ppd.referencia
LEFT JOIN LATERAL (
    SELECT pl2.lpn, pl2.lpc02, pl2.lpc03, pl2.lpc04, pl2.nombre_caso_aplicado
    FROM precio_lista pl2
    WHERE pl2.evento_id = COALESCE(ic.precio_evento_id, (
        SELECT pe.id FROM precio_evento pe
        WHERE pe.estado = 'cerrado'
        ORDER BY pe.created_at DESC
        LIMIT 1
    ))
    AND pl2.linea_id    = ref_j.linea_id
    AND pl2.referencia_id = ref_j.id
    AND pl2.material_id = m.id
    LIMIT 1
) pl ON true
WHERE pp.estado = ANY(ARRAY['ABIERTO', 'ENVIADO'])
AND COALESCE(ppd.cantidad_pares, 0) > 0;
"""

try:
    with engine.begin() as conn:
        conn.execute(text(SQL))
    print("OK — v_stock_rimec recreada")
except Exception as e:
    print(f"ERROR: {e}")

# Verificar resultado
from core.database import get_dataframe
df = get_dataframe("""
    SELECT linea_codigo, referencia_codigo, material_descripcion,
           lpn, lpc02, caso_precio
    FROM v_stock_rimec
    LIMIT 5
""")
if df is not None and not df.empty:
    print(f"\nResultado ({len(df)} filas preview):")
    print(df.to_string())
else:
    print("\nVista vacia o error en query de verificacion")
