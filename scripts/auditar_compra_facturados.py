"""
I1: Auditar métricas facturados en Compra Legal
Investiga desvíos entre header, PP rows, y acordeón FAC-INT
"""
import psycopg2
import sys
import json
from datetime import datetime

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def main():
    compra_id = None
    proforma = None

    # Parse args
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--compra-id' and i + 1 < len(sys.argv):
            compra_id = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--proforma' and i + 1 < len(sys.argv):
            proforma = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Get compra_id from proforma if needed
    if proforma and not compra_id:
        cur.execute("""
            SELECT id FROM compra_legal
            WHERE numero_factura_proveedor = %s
            LIMIT 1
        """, (proforma,))
        row = cur.fetchone()
        if row:
            compra_id = row[0]
        else:
            print(f"[ERROR] Proforma {proforma} no encontrada")
            return

    if not compra_id:
        print("[ERROR] Especificar --compra-id <id> o --proforma <nro>")
        return

    print("=" * 80)
    print(f"AUDIT COMPRA FACTURADOS (compra_legal.id={compra_id})")
    print("=" * 80)
    print()

    resultado = {
        "audit_timestamp": datetime.now().isoformat(),
        "compra_id": compra_id,
        "proforma": proforma,
        "metricas": {},
        "desvios": [],
        "diagnostico": {}
    }

    # 1. Header metrics
    print("[1] HEADER METRICS (get_compra_header)")
    print("-" * 80)
    cur.execute("""
        SELECT
            cl.numero_registro,
            cl.numero_factura_proveedor AS proforma,
            COALESCE(
                (SELECT SUM(vt.cantidad_vendida)
                 FROM venta_transito vt
                 WHERE vt.pedido_proveedor_id IN (
                     SELECT pedido_proveedor_id FROM compra_legal_pedido
                     WHERE compra_legal_id = cl.id
                 )),
                0
            ) AS vt_sum,
            COALESCE(
                (SELECT SUM(fid.pares)
                 FROM factura_interna fi
                 JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
                 WHERE fi.pp_id IN (
                     SELECT pedido_proveedor_id FROM compra_legal_pedido
                     WHERE compra_legal_id = cl.id
                 )
                 AND fi.estado IN ('CONFIRMADA', 'RESERVADA')),
                0
            ) AS fi_sum,
            COALESCE(
                (SELECT SUM(vt.cantidad_vendida)
                 FROM venta_transito vt
                 WHERE vt.pedido_proveedor_id IN (
                     SELECT pedido_proveedor_id FROM compra_legal_pedido
                     WHERE compra_legal_id = cl.id
                 )),
                0
            ) +
            COALESCE(
                (SELECT SUM(fid.pares)
                 FROM factura_interna fi
                 JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
                 WHERE fi.pp_id IN (
                     SELECT pedido_proveedor_id FROM compra_legal_pedido
                     WHERE compra_legal_id = cl.id
                 )
                 AND fi.estado IN ('CONFIRMADA', 'RESERVADA')),
                0
            ) AS header_facturados
        FROM compra_legal cl
        WHERE cl.id = %s
    """, (compra_id,))

    header_row = cur.fetchone()
    if header_row:
        nro_reg, prof, vt_sum, fi_sum, header_total = header_row
        print(f"  numero_registro: {nro_reg}")
        print(f"  proforma: {prof}")
        print(f"  VT sum: {vt_sum}")
        print(f"  FI sum: {fi_sum}")
        print(f"  header_facturados (VT + FI): {header_total}")

        resultado["proforma"] = prof
        resultado["metricas"]["header_vt"] = int(vt_sum)
        resultado["metricas"]["header_fi"] = int(fi_sum)
        resultado["metricas"]["header_facturados"] = int(header_total)

    print()

    # 2. PP rows (get_pps_de_compra) - NEW implementation with FI+VT
    print("[2] PP ROWS (get_pps_de_compra)")
    print("-" * 80)
    cur.execute("""
        SELECT
            pp.id,
            pp.numero_registro,
            COALESCE(SUM(ppd.cantidad_pares), 0) AS total_pares,
            (
                COALESCE(
                    (SELECT SUM(fid.pares)
                     FROM factura_interna fi
                     JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
                     WHERE fi.pp_id = pp.id
                       AND fi.estado IN ('CONFIRMADA', 'RESERVADA')),
                    0
                )
                + COALESCE(
                    (SELECT SUM(vt.cantidad_vendida)
                     FROM venta_transito vt
                     WHERE vt.pedido_proveedor_id = pp.id
                       AND NOT EXISTS (
                         SELECT 1 FROM factura_interna fi2
                         WHERE fi2.pp_id = vt.pedido_proveedor_id
                           AND fi2.nro_factura = vt.numero_factura_interna
                       )),
                    0
                )
            ) AS total_vendido
        FROM compra_legal_pedido clp
        JOIN pedido_proveedor pp ON pp.id = clp.pedido_proveedor_id
        LEFT JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
        WHERE clp.compra_legal_id = %s
        GROUP BY pp.id, pp.numero_registro
        ORDER BY pp.numero_registro
    """, (compra_id,))

    pp_rows = cur.fetchall()
    pp_list = []
    total_pp_vendido_new = 0

    for row in pp_rows:
        pp_id, pp_nro, total_pares, total_vendido = row
        print(f"  PP {pp_nro}: total_pares={total_pares}, total_vendido={total_vendido} (FI+VT sin overlap)")
        pp_list.append({
            "pp_id": pp_id,
            "pp_nro": pp_nro,
            "total_pares": int(total_pares),
            "total_vendido": int(total_vendido)
        })
        total_pp_vendido_new += int(total_vendido)

    print(f"  TOTAL PP vendido (NEW: FI+VT sin overlap): {total_pp_vendido_new}")

    resultado["metricas"]["pp_total_vendido_new"] = total_pp_vendido_new
    resultado["metricas"]["pp_rows"] = pp_list

    print()

    # 3. FAC-INT expander (get_compra_hija_facturacion)
    print("[3] FAC-INT EXPANDER (get_compra_hija_facturacion)")
    print("-" * 80)
    cur.execute("""
        -- Count FI rows
        SELECT 'FI', COUNT(*), SUM(pares_sum) FROM (
            SELECT fi.nro_factura, SUM(fid.pares) AS pares_sum
            FROM factura_interna fi
            JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
            WHERE fi.pp_id IN (
                SELECT pedido_proveedor_id FROM compra_legal_pedido
                WHERE compra_legal_id = %s
            )
            AND fi.estado IN ('CONFIRMADA', 'RESERVADA')
            GROUP BY fi.marca, fi.nro_factura, fi.created_at, fi.cliente_id, fid.linea_snapshot
        ) sub

        UNION ALL

        -- Count VT rows
        SELECT 'VT', COUNT(*), SUM(pares_sum) FROM (
            SELECT vt.numero_factura_interna, SUM(vt.cantidad_vendida) AS pares_sum
            FROM venta_transito vt
            WHERE vt.pedido_proveedor_id IN (
                SELECT pedido_proveedor_id FROM compra_legal_pedido
                WHERE compra_legal_id = %s
            )
            GROUP BY vt.numero_factura_interna, vt.codigo_cliente,
                     vt.pedido_proveedor_detalle_id
        ) sub
    """, (compra_id, compra_id))

    fac_rows = cur.fetchall()
    fac_expander_total = 0
    fac_fi_rows = 0
    fac_fi_pares = 0
    fac_vt_rows = 0
    fac_vt_pares = 0

    for row in fac_rows:
        tipo, count, sum_pares = row
        print(f"  {tipo} rows: {count}, pares: {sum_pares}")
        if tipo == 'FI':
            fac_fi_rows = int(count or 0)
            fac_fi_pares = int(sum_pares or 0)
        elif tipo == 'VT':
            fac_vt_rows = int(count or 0)
            fac_vt_pares = int(sum_pares or 0)
        fac_expander_total += int(sum_pares or 0)

    print(f"  TOTAL expander (FI + VT UNION ALL): {fac_expander_total}")

    resultado["metricas"]["fac_expander_fi_rows"] = fac_fi_rows
    resultado["metricas"]["fac_expander_fi_pares"] = fac_fi_pares
    resultado["metricas"]["fac_expander_vt_rows"] = fac_vt_rows
    resultado["metricas"]["fac_expander_vt_pares"] = fac_vt_pares
    resultado["metricas"]["fac_expander_total"] = fac_expander_total

    print()

    # 4. Overlap check (same pares in both VT and FI)
    print("[4] OVERLAP CHECK (VT+FI double counting)")
    print("-" * 80)
    cur.execute("""
        SELECT
            COUNT(*) AS overlap_count,
            SUM(vt_pares) AS overlap_vt_pares,
            SUM(fi_pares) AS overlap_fi_pares
        FROM (
            SELECT
                vt.numero_factura_interna,
                SUM(vt.cantidad_vendida) AS vt_pares,
                COALESCE(
                    (SELECT SUM(fid.pares)
                     FROM factura_interna fi
                     JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
                     WHERE fi.nro_factura = vt.numero_factura_interna
                     AND fi.estado IN ('CONFIRMADA', 'RESERVADA')),
                    0
                ) AS fi_pares
            FROM venta_transito vt
            WHERE vt.pedido_proveedor_id IN (
                SELECT pedido_proveedor_id FROM compra_legal_pedido
                WHERE compra_legal_id = %s
            )
            GROUP BY vt.numero_factura_interna
        ) sub
        WHERE fi_pares > 0
    """, (compra_id,))

    overlap_row = cur.fetchone()
    if overlap_row:
        overlap_count, overlap_vt, overlap_fi = overlap_row
        print(f"  Facturas con overlap: {overlap_count or 0}")
        print(f"  VT pares en overlap: {overlap_vt or 0}")
        print(f"  FI pares en overlap: {overlap_fi or 0}")

        resultado["metricas"]["overlap_facturas"] = int(overlap_count or 0)
        resultado["metricas"]["overlap_vt_pares"] = int(overlap_vt or 0)
        resultado["metricas"]["overlap_fi_pares"] = int(overlap_fi or 0)

    print()
    print("=" * 80)
    print("DESVIOS DETECTADOS")
    print("=" * 80)

    # Detect deviations
    if header_row and pp_rows:
        # Check 1: Header vs PP sum (should be equal after fix)
        if header_total != total_pp_vendido_new:
            desvio = {
                "tipo": "H-A",
                "descripcion": "Header vs PP sum desalineados",
                "header_facturados": int(header_total),
                "pp_sum_vendido": total_pp_vendido_new,
                "diferencia": int(header_total) - total_pp_vendido_new,
                "causa": "Métrica no unificada o lógica diferente"
            }
            resultado["desvios"].append(desvio)
            print(f"[!!] H-A: Header ({header_total}) != PP sum ({total_pp_vendido_new})")
            print(f"     Diferencia: {desvio['diferencia']}")
        else:
            print(f"[OK] Header ({header_total}) == PP sum ({total_pp_vendido_new})")

        # Check 2: Header vs Expander (should be equal)
        if header_total != fac_expander_total:
            desvio = {
                "tipo": "H-B",
                "descripcion": "Header vs Expander desalineados",
                "header_facturados": int(header_total),
                "fac_expander_total": fac_expander_total,
                "diferencia": fac_expander_total - int(header_total),
                "causa_posible": "UNION ALL genera filas duplicadas por GROUP BY diferente"
            }
            resultado["desvios"].append(desvio)
            print(f"[!!] H-B: Header ({header_total}) != Expander ({fac_expander_total})")
            print(f"     Diferencia: {desvio['diferencia']}")
        else:
            print(f"[OK] Header ({header_total}) == Expander ({fac_expander_total})")

        # Check 3: All three should be equal
        if header_total == total_pp_vendido_new == fac_expander_total:
            print(f"[OK] ALINEACION COMPLETA: Header = PP = Expander = {header_total}")

    # Save JSON
    import pathlib
    ROOT = pathlib.Path(__file__).resolve().parents[1]
    output_path = ROOT / "scripts" / f"audit_compra_{compra_id}_{proforma or 'sin-proforma'}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print()
    print(f"Audit JSON guardado: {output_path}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
