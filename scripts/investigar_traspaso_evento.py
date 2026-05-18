"""
OT-DEPOSITO-WEB-510-001: Investigar cómo obtener precio_evento_id desde traspaso.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
from core.database import get_dataframe


def main():
    print("=" * 80)
    print("INVESTIGAR: Evento precio desde traspaso")
    print("=" * 80)
    print()

    # Verificar estructura snapshot_json
    print("[1] Estructura snapshot_json de traspaso:")
    df_traspaso = get_dataframe("""
        SELECT numero_registro, snapshot_json, documento_ref
        FROM traspaso
        WHERE estado = 'CONFIRMADO'
        ORDER BY id DESC
        LIMIT 3
    """)

    if df_traspaso is not None and not df_traspaso.empty:
        for idx, row in df_traspaso.iterrows():
            print(f"\n  Traspaso: {row['numero_registro']}")
            print(f"  documento_ref: {row['documento_ref']}")
            snapshot = row['snapshot_json']
            if snapshot:
                print(f"  snapshot keys: {list(snapshot.keys())}")
                if 'id_pp' in snapshot:
                    print(f"  id_pp: {snapshot['id_pp']}")
                if 'id_marca' in snapshot:
                    print(f"  id_marca: {snapshot['id_marca']}")
            else:
                print("  snapshot_json: NULL")
    else:
        print("  No hay traspasos confirmados")

    print()
    print("[2] Obtener precio_evento_id desde PP:")
    # Para cada traspaso, obtener el evento de precio del PP
    df_pp_evento = get_dataframe("""
        SELECT
            tr.numero_registro AS traspaso_nro,
            (tr.snapshot_json->>'id_pp')::int AS pp_id,
            pp.numero_registro AS pp_nro,
            icp.precio_evento_id,
            pe.nombre_evento
        FROM traspaso tr
        LEFT JOIN pedido_proveedor pp ON pp.id = (tr.snapshot_json->>'id_pp')::int
        LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
        LEFT JOIN precio_evento pe ON pe.id = icp.precio_evento_id
        WHERE tr.estado = 'CONFIRMADO'
        ORDER BY tr.id DESC
        LIMIT 5
    """)

    if df_pp_evento is not None and not df_pp_evento.empty:
        print(df_pp_evento.to_string(index=False))
    else:
        print("  Sin datos")

    print()
    print("[3] Test JOIN precio_lista desde depósito web:")
    # Simular query enriquecida
    df_test = get_dataframe("""
        SELECT
            COALESCE(mv.descp_marca, '-') AS marca,
            l.codigo_proveedor AS linea,
            r.codigo_proveedor AS referencia,
            COALESCE(mat.descripcion, '-') AS material,
            COALESCE(col.nombre, '-') AS color,
            SUM(md.cantidad * md.signo) AS stock_total,
            -- OT-510: Enriquecimiento precio
            icp.precio_evento_id,
            pl.lpn,
            pl.nombre_caso_aplicado AS caso_precio,
            fn_precio_venta_web(pl.lpn, pl.nombre_caso_aplicado) AS precio_venta
        FROM movimiento_detalle md
        JOIN movimiento m ON m.id = md.movimiento_id
        JOIN traspaso tr ON tr.numero_registro = m.documento_ref
        LEFT JOIN marca_v2 mv ON mv.id_marca = (tr.snapshot_json->>'id_marca')::int
        -- OT-510 L1: Resolver evento precio
        LEFT JOIN pedido_proveedor pp ON pp.id = (tr.snapshot_json->>'id_pp')::int
        LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
        JOIN combinacion c ON c.id = md.combinacion_id
        JOIN linea l ON l.id = c.linea_id
        JOIN referencia r ON r.id = c.referencia_id
        LEFT JOIN material mat ON mat.id = c.material_id
        LEFT JOIN color col ON col.id = c.color_id
        -- OT-510 L2: JOIN precio_lista
        LEFT JOIN LATERAL (
            SELECT pl2.lpn, pl2.nombre_caso_aplicado
            FROM precio_lista pl2
            WHERE pl2.evento_id = icp.precio_evento_id
              AND pl2.linea_id = l.id
              AND pl2.referencia_id = r.id
              AND pl2.material_id = mat.id
            LIMIT 1
        ) pl ON true
        WHERE m.almacen_destino_id = 1
          AND m.estado = 'CONFIRMADO'
          AND m.tipo = 'INGRESO_COMPRA'
        GROUP BY mv.descp_marca, l.codigo_proveedor, r.codigo_proveedor,
                 mat.descripcion, col.nombre, icp.precio_evento_id, pl.lpn,
                 pl.nombre_caso_aplicado
        HAVING SUM(md.cantidad * md.signo) > 0
        ORDER BY mv.descp_marca, l.codigo_proveedor, r.codigo_proveedor
        LIMIT 10
    """)

    if df_test is not None and not df_test.empty:
        print(df_test.to_string(index=False))
        print()
        print(f"[RESUMEN] {len(df_test)} moléculas con precio enriquecido")
        con_lpn = df_test['lpn'].notna().sum()
        print(f"  Con LPN: {con_lpn}/{len(df_test)}")
        con_precio = df_test['precio_venta'].notna().sum()
        print(f"  Con precio_venta: {con_precio}/{len(df_test)}")
    else:
        print("  Sin stock en ALM_WEB_01 o error query")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
