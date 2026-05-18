"""
OT-TRASPASO-504-001 Fase 1: Auditar duplicados traspaso_detalle
Investiga UniqueViolation (traspaso_id, combinacion_id) al finalizar Compra
"""
import psycopg2
import sys
import json
from datetime import datetime

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def main():
    compra_id = None

    # Parse args
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--compra-id' and i + 1 < len(sys.argv):
            compra_id = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    if not compra_id:
        print("[ERROR] Especificar --compra-id <id>")
        return False

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("=" * 80)
    print(f"AUDIT TRASPASO DUPLICADOS (compra_legal.id={compra_id})")
    print("=" * 80)
    print()

    resultado = {
        "audit_timestamp": datetime.now().isoformat(),
        "compra_id": compra_id,
        "diagnostico": {},
        "duplicados": [],
        "fi_detalle": [],
        "desvios": []
    }

    # 1. Header Compra
    print("[1] COMPRA LEGAL HEADER")
    print("-" * 80)
    cur.execute("""
        SELECT cl.id, cl.numero_registro, cl.numero_factura_proveedor, cl.estado
        FROM compra_legal cl
        WHERE cl.id = %s
    """, (compra_id,))

    cl_row = cur.fetchone()
    if not cl_row:
        print(f"[ERROR] Compra {compra_id} not found")
        return False

    cl_id, cl_nro, proforma, cl_estado = cl_row
    print(f"  CL: {cl_nro} (id={cl_id})")
    print(f"  Proforma: {proforma}")
    print(f"  Estado: {cl_estado}")

    resultado["compra_nro"] = cl_nro
    resultado["proforma"] = proforma
    resultado["estado"] = cl_estado

    print()

    # 2. Traspaso creado
    print("[2] TRASPASO ASOCIADO")
    print("-" * 80)
    cur.execute("""
        SELECT t.id, t.numero_registro, t.compra_legal_id, t.estado
        FROM traspaso t
        WHERE t.compra_legal_id = %s
        ORDER BY t.id
    """, (compra_id,))

    traspaso_rows = cur.fetchall()
    if traspaso_rows:
        print(f"  Total traspasos: {len(traspaso_rows)}")
        for t in traspaso_rows:
            t_id, t_nro, t_cl_id, t_estado = t
            print(f"    Traspaso {t_nro} (id={t_id}) - estado={t_estado}")
            resultado["traspaso_id"] = t_id
            resultado["traspaso_nro"] = t_nro
            resultado["traspaso_estado"] = t_estado
    else:
        print("  Sin traspasos creados")
        resultado["traspaso_id"] = None

    print()

    # 3. Check duplicados en traspaso_detalle
    print("[3] DUPLICADOS EN TRASPASO_DETALLE")
    print("-" * 80)

    if not traspaso_rows:
        print("  SKIP: Sin traspasos")
    else:
        for t in traspaso_rows:
            t_id = t[0]
            cur.execute("""
                SELECT
                    td.traspaso_id,
                    td.combinacion_id,
                    COUNT(*) AS count,
                    SUM(td.cantidad) AS total_qty,
                    STRING_AGG(CAST(td.id AS TEXT), ', ') AS td_ids
                FROM traspaso_detalle td
                WHERE td.traspaso_id = %s
                GROUP BY td.traspaso_id, td.combinacion_id
                HAVING COUNT(*) > 1
            """, (t_id,))

            dup_rows = cur.fetchall()
            if dup_rows:
                print(f"  [!!] Traspaso {t_id}: {len(dup_rows)} combinaciones duplicadas")
                for dup in dup_rows:
                    t_id_dup, comb_id, count, total_qty, td_ids = dup
                    print(f"    (traspaso_id, combinacion_id)=({t_id_dup}, {comb_id})")
                    print(f"      Ocurrencias: {count}")
                    print(f"      Total qty: {total_qty}")
                    print(f"      td.id: {td_ids}")

                    resultado["duplicados"].append({
                        "traspaso_id": t_id_dup,
                        "combinacion_id": comb_id,
                        "ocurrencias": int(count),
                        "total_qty": int(total_qty),
                        "td_ids": td_ids
                    })
            else:
                print(f"  [OK] Traspaso {t_id}: sin duplicados")

    print()

    # 4. Analizar FI -> SKU mapping (ppd rows)
    print("[4] FI DETALLE -> PPD (SKU mapping)")
    print("-" * 80)

    cur.execute("""
        SELECT
            fi.id AS fi_id,
            fi.nro_factura,
            fid.id AS fid_id,
            fid.ppd_id,
            ppd.linea,
            ppd.referencia,
            ppd.id_material,
            ppd.id_color,
            ppd.grades_json,
            fid.linea_snapshot,
            fid.pares
        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        LEFT JOIN pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
        WHERE fi.pp_id IN (
            SELECT pedido_proveedor_id FROM compra_legal_pedido
            WHERE compra_legal_id = %s
        )
        AND fi.estado IN ('CONFIRMADA', 'RESERVADA')
        ORDER BY fi.id, fid.id
    """, (compra_id,))

    fi_rows = cur.fetchall()
    print(f"  Total FI detalle rows: {len(fi_rows)}")

    # Simulate _crear_traspasos_para_pp logic
    # Group by SKU (linea+ref+mat+col) and check for duplicates
    sku_groups = {}
    talla_expansion = []

    for fi_row in fi_rows:
        (fi_id, fi_nro, fid_id, ppd_id, linea, ref,
         id_mat, id_col, grades_json, linea_snapshot, pares) = fi_row

        # Parse tallas (same logic as _crear_traspasos_para_pp)
        tallas = {}

        # Try grades_json first
        if grades_json:
            try:
                grades = json.loads(grades_json) if isinstance(grades_json, str) else grades_json
                for talla_str, qty in (grades or {}).items():
                    talla_num = int(talla_str)
                    tallas[f"t{talla_num}"] = int(qty)
            except:
                pass

        # Fallback to linea_snapshot gradas_fmt
        if not tallas and linea_snapshot:
            try:
                snapshot = json.loads(linea_snapshot) if isinstance(linea_snapshot, str) else linea_snapshot
                gradas_fmt = snapshot.get("gradas_fmt", "") if snapshot else ""
                if gradas_fmt and "(" in gradas_fmt and ")" in gradas_fmt:
                    inicio_str, resto = gradas_fmt.split("(", 1)
                    cantidades_str, fin_str = resto.split(")", 1)
                    talla_inicio = int(inicio_str.strip())
                    cantidades = [int(x.strip()) for x in cantidades_str.split("-") if x.strip()]
                    for idx, qty in enumerate(cantidades):
                        talla_num = talla_inicio + idx
                        if qty > 0:
                            tallas[f"t{talla_num}"] = qty
            except:
                pass

        # Last fallback: t37 generic
        if not tallas and pares and pares > 0:
            tallas["t37"] = int(pares)

        if not tallas:
            continue

        # Track SKU grouping
        sku_key = (linea or "", ref or "", id_mat, id_col)
        if sku_key not in sku_groups:
            sku_groups[sku_key] = []
        sku_groups[sku_key].append({
            "fi_id": fi_id,
            "fi_nro": fi_nro,
            "fid_id": fid_id,
            "ppd_id": ppd_id,
            "tallas": tallas
        })

        # Expand tallas for traspaso_detalle simulation
        for talla_key, qty in tallas.items():
            talla_expansion.append({
                "fi_id": fi_id,
                "fi_nro": fi_nro,
                "fid_id": fid_id,
                "sku": f"{linea}-{ref}-{id_mat}-{id_col}",
                "talla": talla_key,
                "qty": qty
            })

    print(f"  Total SKU groups: {len(sku_groups)}")
    print(f"  Total talla expansions: {len(talla_expansion)}")

    # Check for SKUs with multiple fid_id (potential duplicate combinacion_id)
    multi_fid_skus = {k: v for k, v in sku_groups.items() if len(v) > 1}
    if multi_fid_skus:
        print(f"  [!!] {len(multi_fid_skus)} SKUs con multiples fid_id:")
        for sku_key, entries in list(multi_fid_skus.items())[:5]:
            linea, ref, mat, col = sku_key
            print(f"    SKU {linea}-{ref}-{mat}-{col}: {len(entries)} fid rows")
            for e in entries:
                print(f"      fid={e['fid_id']}, tallas={list(e['tallas'].keys())}")

        resultado["diagnostico"]["skus_con_multiples_fid"] = len(multi_fid_skus)
        resultado["diagnostico"]["ejemplo_multi_fid_skus"] = [
            {
                "sku": f"{k[0]}-{k[1]}-{k[2]}-{k[3]}",
                "ocurrencias": len(v),
                "fid_ids": [e["fid_id"] for e in v],
                "tallas_overlap": any(
                    set(v[i]["tallas"].keys()) & set(v[j]["tallas"].keys())
                    for i in range(len(v)) for j in range(i+1, len(v))
                )
            }
            for k, v in list(multi_fid_skus.items())[:5]
        ]
    else:
        print("  [OK] Sin SKUs con multiples fid")

    # Save expansion for analysis
    resultado["fi_detalle"] = talla_expansion

    print()

    # 5. Root cause diagnosis
    print("[5] DIAGNOSTICO ROOT CAUSE")
    print("-" * 80)

    if resultado["duplicados"]:
        print("  [!!] CAUSA: crear_traspaso_por_factura INSERT sin agrupar por combinacion_id")
        print("  Cuando multiples fid_id resuelven a mismo (linea+ref+mat+color+talla):")
        print("  -> Mismo combinacion_id insertado N veces")
        print("  -> UniqueViolation en UNIQUE (traspaso_id, combinacion_id)")
        resultado["diagnostico"]["root_cause"] = "INSERT sin GROUP BY combinacion_id"
        resultado["diagnostico"]["fix_required"] = "Agrupar qty por combinacion_id antes de INSERT o UPSERT"
    else:
        print("  [OK] Sin duplicados detectados")
        resultado["diagnostico"]["root_cause"] = "N/A"

    print()

    # Save JSON
    import pathlib
    ROOT = pathlib.Path(__file__).resolve().parents[1]
    output_path = ROOT / "scripts" / f"audit_traspaso_duplicados_{compra_id}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print(f"Audit JSON guardado: {output_path}")

    cur.close()
    conn.close()
    return True

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
