"""
OT-COMBINACION-505-001 Fase 1 I1: Auditar por qué traspaso_detalle está vacío
Investiga combinacion table y _resolve_combinacion_id failures
"""
import psycopg2
import sys
import json
from datetime import datetime

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def main():
    traspaso_id = None
    compra_id = None

    # Parse args
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--traspaso-id' and i + 1 < len(sys.argv):
            traspaso_id = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--compra-id' and i + 1 < len(sys.argv):
            compra_id = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    if not traspaso_id:
        print("[ERROR] Especificar --traspaso-id <id>")
        return False

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    print("=" * 80)
    print(f"AUDIT COMBINACION TRASPASO (traspaso_id={traspaso_id})")
    print("=" * 80)
    print()

    resultado = {
        "audit_timestamp": datetime.now().isoformat(),
        "traspaso_id": traspaso_id,
        "compra_id": compra_id,
        "diagnostico": {},
        "entidades_faltantes": [],
        "resolucion_fallida": []
    }

    # 1. Traspaso header + snapshot
    print("[1] TRASPASO HEADER + SNAPSHOT")
    print("-" * 80)
    cur.execute("""
        SELECT id, numero_registro, estado, snapshot_json, documento_ref
        FROM traspaso
        WHERE id = %s
    """, (traspaso_id,))

    t_row = cur.fetchone()
    if not t_row:
        print(f"[ERROR] Traspaso {traspaso_id} not found")
        return False

    t_id, t_nro, t_estado, snap_json, doc_ref = t_row
    print(f"  Traspaso: {t_nro} (id={t_id})")
    print(f"  Estado: {t_estado}")
    print(f"  Documento: {doc_ref}")

    if isinstance(snap_json, str):
        snapshot = json.loads(snap_json)
    else:
        snapshot = snap_json

    items = snapshot.get("items", [])
    print(f"  Snapshot items: {len(items)}")

    resultado["traspaso_nro"] = t_nro
    resultado["traspaso_estado"] = t_estado
    resultado["documento_ref"] = doc_ref
    resultado["snapshot_items_count"] = len(items)

    print()

    # 2. Traspaso_detalle (esperado vacío)
    print("[2] TRASPASO_DETALLE")
    print("-" * 80)
    cur.execute("""
        SELECT COUNT(*), SUM(cantidad)
        FROM traspaso_detalle
        WHERE traspaso_id = %s
    """, (traspaso_id,))

    td_row = cur.fetchone()
    td_count, td_qty = td_row
    print(f"  Rows: {td_count or 0}")
    print(f"  Total pares: {td_qty or 0}")

    resultado["traspaso_detalle_rows"] = int(td_count or 0)
    resultado["traspaso_detalle_pares"] = int(td_qty or 0)

    print()

    # 3. Tabla combinacion global
    print("[3] TABLA COMBINACION (GLOBAL)")
    print("-" * 80)
    cur.execute("SELECT COUNT(*) FROM combinacion")
    comb_count = cur.fetchone()[0]
    print(f"  Total combinaciones: {comb_count}")

    resultado["combinacion_total_count"] = int(comb_count)

    if comb_count == 0:
        print("  [!!] Tabla combinacion VACIA - esto explica traspaso_detalle vacío")
        resultado["diagnostico"]["combinacion_vacia"] = True
    else:
        print("  [OK] Combinacion tiene datos")
        resultado["diagnostico"]["combinacion_vacia"] = False

    print()

    # 4. Analizar cada item del snapshot
    print("[4] ANALISIS POR ITEM SNAPSHOT")
    print("-" * 80)

    for idx, item in enumerate(items):
        linea = item.get("linea", "")
        ref = item.get("referencia", "")
        id_mat = item.get("id_material", 0)
        id_col = item.get("id_color", 0)
        tallas = item.get("tallas", {})

        print(f"\n  Item [{idx}]: {linea}-{ref}-{id_mat}-{id_col}")
        print(f"    Tallas: {list(tallas.keys())}")

        item_result = {
            "idx": idx,
            "sku": f"{linea}-{ref}-{id_mat}-{id_col}",
            "tallas_count": len(tallas),
            "checks": {}
        }

        # Check linea
        cur.execute("""
            SELECT l.id, l.proveedor_id
            FROM linea l
            WHERE l.codigo_proveedor::text = %s
            LIMIT 1
        """, (str(linea),))

        l_row = cur.fetchone()
        if l_row:
            linea_id, prov_id = l_row
            print(f"    + linea_id: {linea_id}, proveedor_id: {prov_id}")
            item_result["checks"]["linea"] = {"ok": True, "linea_id": linea_id, "proveedor_id": prov_id}
        else:
            print(f"    - linea NOT FOUND (codigo_proveedor={linea})")
            item_result["checks"]["linea"] = {"ok": False, "error": "not found"}
            resultado["entidades_faltantes"].append({"tipo": "linea", "codigo": linea, "item_idx": idx})
            continue

        # Check referencia
        cur.execute("""
            SELECT lr.id
            FROM linea_referencia lr
            WHERE lr.linea_id = %s
              AND lr.codigo_proveedor::text = %s
            LIMIT 1
        """, (linea_id, str(ref)))

        r_row = cur.fetchone()
        if r_row:
            ref_id = r_row[0]
            print(f"    + referencia_id: {ref_id}")
            item_result["checks"]["referencia"] = {"ok": True, "referencia_id": ref_id}
        else:
            print(f"    - referencia NOT FOUND (codigo_proveedor={ref}, linea_id={linea_id})")
            item_result["checks"]["referencia"] = {"ok": False, "error": "not found"}
            resultado["entidades_faltantes"].append({"tipo": "referencia", "codigo": ref, "linea_id": linea_id, "item_idx": idx})
            continue

        # Check material
        cur.execute("""
            SELECT m.id
            FROM material m
            WHERE m.id = %s
              AND m.proveedor_id = %s
            LIMIT 1
        """, (id_mat, prov_id))

        m_row = cur.fetchone()
        if m_row:
            mat_id = m_row[0]
            print(f"    + material_id: {mat_id}")
            item_result["checks"]["material"] = {"ok": True, "material_id": mat_id}
        else:
            print(f"    - material NOT FOUND (id={id_mat}, proveedor_id={prov_id})")
            item_result["checks"]["material"] = {"ok": False, "error": "not found"}
            resultado["entidades_faltantes"].append({"tipo": "material", "id": id_mat, "proveedor_id": prov_id, "item_idx": idx})
            continue

        # Check color
        cur.execute("""
            SELECT c.id
            FROM color c
            WHERE c.id = %s
              AND c.proveedor_id = %s
            LIMIT 1
        """, (id_col, prov_id))

        c_row = cur.fetchone()
        if c_row:
            col_id = c_row[0]
            print(f"    + color_id: {col_id}")
            item_result["checks"]["color"] = {"ok": True, "color_id": col_id}
        else:
            print(f"    - color NOT FOUND (id={id_col}, proveedor_id={prov_id})")
            item_result["checks"]["color"] = {"ok": False, "error": "not found"}
            resultado["entidades_faltantes"].append({"tipo": "color", "id": id_col, "proveedor_id": prov_id, "item_idx": idx})
            continue

        # Check tallas (if combinacion populated)
        if comb_count > 0:
            print(f"    Checking combinacion for tallas...")
            for talla_key, qty in tallas.items():
                talla_num = talla_key.replace("t", "")

                # Try to find talla_id
                cur.execute("""
                    SELECT t.id FROM talla t
                    WHERE t.numero = %s
                    LIMIT 1
                """, (int(talla_num),))

                t_row = cur.fetchone()
                if not t_row:
                    print(f"      - talla {talla_num} NOT FOUND in talla table")
                    continue

                talla_id = t_row[0]

                # Try to resolve combinacion_id
                cur.execute("""
                    SELECT c.id
                    FROM combinacion c
                    WHERE c.linea_id = %s
                      AND c.referencia_id = %s
                      AND c.material_id = %s
                      AND c.color_id = %s
                      AND c.talla_id = %s
                    LIMIT 1
                """, (linea_id, ref_id, mat_id, col_id, talla_id))

                comb_row = cur.fetchone()
                if comb_row:
                    print(f"      + combinacion_id for t{talla_num}: {comb_row[0]}")
                else:
                    print(f"      - combinacion NOT FOUND for t{talla_num}")
                    resultado["resolucion_fallida"].append({
                        "item_idx": idx,
                        "sku": f"{linea}-{ref}-{id_mat}-{id_col}",
                        "talla": talla_num,
                        "linea_id": linea_id,
                        "ref_id": ref_id,
                        "mat_id": mat_id,
                        "col_id": col_id,
                        "talla_id": talla_id
                    })

        resultado["snapshot_items_detail"] = resultado.get("snapshot_items_detail", [])
        resultado["snapshot_items_detail"].append(item_result)

    print()

    # 5. Diagnóstico final
    print("[5] DIAGNOSTICO FINAL")
    print("-" * 80)

    if comb_count == 0:
        print("  ROOT CAUSE: Tabla combinacion VACIA")
        print("  _resolve_combinacion_id() siempre retorna NULL")
        print("  INSERT traspaso_detalle se skippea")
        resultado["diagnostico"]["root_cause"] = "combinacion table empty"
        resultado["diagnostico"]["recomendacion"] = "R1: Backfill combinacion desde ppd + pilares"
    elif resultado["entidades_faltantes"]:
        print(f"  ROOT CAUSE: {len(resultado['entidades_faltantes'])} entidades base faltantes")
        print("  Linea/referencia/material/color no existen para snapshot items")
        resultado["diagnostico"]["root_cause"] = "missing base entities (linea/ref/mat/col)"
        resultado["diagnostico"]["recomendacion"] = "R2: crear_traspaso_por_factura crear entidades mínimas"
    elif resultado["resolucion_fallida"]:
        print(f"  ROOT CAUSE: {len(resultado['resolucion_fallida'])} combinaciones missing")
        print("  Entidades base OK, pero combinacion rows no existen")
        resultado["diagnostico"]["root_cause"] = "combinacion rows missing for existing entities"
        resultado["diagnostico"]["recomendacion"] = "R1: Backfill combinacion desde ppd grades_json"
    else:
        print("  [OK] Sin issues detectados (raro si traspaso_detalle está vacío)")
        resultado["diagnostico"]["root_cause"] = "unknown"

    print()

    # Save JSON
    import pathlib
    ROOT = pathlib.Path(__file__).resolve().parents[1]
    output_path = ROOT / "scripts" / f"audit_combinacion_traspaso_{traspaso_id}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print(f"Audit JSON guardado: {output_path}")

    cur.close()
    conn.close()
    return True

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
