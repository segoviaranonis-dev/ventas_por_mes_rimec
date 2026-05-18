"""
Test unitario: normalizacion de moleculas duplicadas en import PP
Modulo 500 standard: 1 molecula = 1 fila en pedido_proveedor_detalle
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.pedido_proveedor.logic import _mol_key_import
from collections import defaultdict


def test_mol_key():
    """Verifica que clave molecular identifique duplicados correctamente"""
    print("TEST 1: Clave molecular")
    print("=" * 70)

    row1 = {
        "linea_cod": "7320",
        "ref_cod": "239",
        "material_code": "30998",
        "color_code": "100196",
        "grades_json": {"35": 1, "36": 1, "37": 2, "38": 2, "39": 1, "40": 1},
    }

    row2 = {
        "linea_cod": "7320",
        "ref_cod": "239",
        "material_code": "30998",
        "color_code": "100196",
        "grades_json": {"35": 1, "36": 1, "37": 2, "38": 2, "39": 1, "40": 1},
    }

    row3 = {
        "linea_cod": "7320",
        "ref_cod": "239",
        "material_code": "30998",
        "color_code": "15745",  # Diferente color
        "grades_json": {"35": 1, "36": 1, "37": 2, "38": 2, "39": 1, "40": 1},
    }

    row4 = {
        "linea_cod": "7320",
        "ref_cod": "239",
        "material_code": "30998",
        "color_code": "15745",
        "grades_json": {"35": 1, "36": 2, "37": 3, "38": 2, "39": 2, "40": 2},  # Diferente curva
    }

    key1 = _mol_key_import(row1)
    key2 = _mol_key_import(row2)
    key3 = _mol_key_import(row3)
    key4 = _mol_key_import(row4)

    print(f"Row1 key: {key1}")
    print(f"Row2 key: {key2}")
    print(f"Row3 key: {key3}")
    print(f"Row4 key: {key4}")
    print()

    assert key1 == key2, "Filas identicas deben tener misma clave"
    assert key1 != key3, "Color distinto debe generar clave distinta"
    assert key3 != key4, "Curva distinta debe generar clave distinta"

    print("[OK] Clave molecular funciona correctamente\n")


def test_normalization():
    """Simula deduplicacion como en populate_pp_from_proforma"""
    print("TEST 2: Normalizacion con duplicados (caso 7320/239)")
    print("=" * 70)

    # Simulando 8 filas del Excel auditado (caso real 7320/239)
    detalle_rows = [
        {"item": 216, "linea_cod": "7320", "ref_cod": "239", "material_code": "30998", "color_code": "100196",
         "color": "AVELA 1248", "boxes": 1, "pairs": 8, "amount_fob": 50.0,
         "grades_json": {"35": 1, "36": 1, "37": 2, "38": 2, "39": 1, "40": 1}},
        {"item": 217, "linea_cod": "7320", "ref_cod": "239", "material_code": "30998", "color_code": "100196",
         "color": "AVELA 1248", "boxes": 1, "pairs": 8, "amount_fob": 50.0,
         "grades_json": {"35": 1, "36": 1, "37": 2, "38": 2, "39": 1, "40": 1}},
        {"item": 219, "linea_cod": "7320", "ref_cod": "239", "material_code": "30998", "color_code": "100196",
         "color": "AVELA 1248", "boxes": 1, "pairs": 8, "amount_fob": 50.0,
         "grades_json": {"35": 1, "36": 1, "37": 2, "38": 2, "39": 1, "40": 1}},
        {"item": 220, "linea_cod": "7320", "ref_cod": "239", "material_code": "30998", "color_code": "100196",
         "color": "AVELA 1248", "boxes": 1, "pairs": 8, "amount_fob": 50.0,
         "grades_json": {"35": 1, "36": 1, "37": 2, "38": 2, "39": 1, "40": 1}},
        {"item": 214, "linea_cod": "7320", "ref_cod": "239", "material_code": "30998", "color_code": "15745",
         "color": "NEGRO 01", "boxes": 1, "pairs": 8, "amount_fob": 48.0,
         "grades_json": {"35": 1, "36": 1, "37": 2, "38": 2, "39": 1, "40": 1}},
        {"item": 215, "linea_cod": "7320", "ref_cod": "239", "material_code": "30998", "color_code": "15745",
         "color": "NEGRO 01", "boxes": 1, "pairs": 12, "amount_fob": 72.0,
         "grades_json": {"35": 1, "36": 2, "37": 3, "38": 2, "39": 2, "40": 2}},
        {"item": 218, "linea_cod": "7320", "ref_cod": "239", "material_code": "30998", "color_code": "15745",
         "color": "NEGRO 01", "boxes": 1, "pairs": 8, "amount_fob": 48.0,
         "grades_json": {"35": 1, "36": 1, "37": 2, "38": 2, "39": 1, "40": 1}},
        {"item": 221, "linea_cod": "7320", "ref_cod": "239", "material_code": "30998", "color_code": "15745",
         "color": "NEGRO 01", "boxes": 1, "pairs": 12, "amount_fob": 72.0,
         "grades_json": {"35": 1, "36": 2, "37": 3, "38": 2, "39": 2, "40": 2}},
    ]

    # Aplicar normalizacion
    mol_buckets: dict[str, list[dict]] = defaultdict(list)
    for r in detalle_rows:
        mol_buckets[_mol_key_import(r)].append(r)

    normalized_rows: list[dict] = []
    duplicates_found = 0
    for mol_key, group in mol_buckets.items():
        if len(group) > 1:
            duplicates_found += 1
            total_boxes = sum(int(r.get("boxes", 0)) for r in group)
            total_pairs = sum(int(r.get("pairs", 0)) for r in group)
            items = ", ".join(str(r.get("item", "?")) for r in group)
            print(f"  Duplicado {len(group)}x: {group[0]['color']} (items {items})")
            print(f"    -> Consolidado: {total_boxes} cjs / {total_pairs} pares")
            merged = group[0].copy()
            merged["boxes"] = total_boxes
            merged["pairs"] = total_pairs
            merged["amount_fob"] = sum(float(r.get("amount_fob", 0)) for r in group)
            merged["item"] = items
            normalized_rows.append(merged)
        else:
            normalized_rows.append(group[0])

    print()
    print(f"Filas Excel: {len(detalle_rows)}")
    print(f"Filas unicas (moleculas): {len(normalized_rows)}")
    print(f"Duplicados consolidados: {duplicates_found}")
    print()

    # Verificaciones
    assert len(detalle_rows) == 8, "Input debe tener 8 filas"
    assert len(normalized_rows) == 3, "Deben quedar 3 moleculas unicas"
    assert duplicates_found == 3, "Deben detectarse 3 claves duplicadas"

    # Verificar consolidacion AVELA 1248
    avela = [r for r in normalized_rows if r["color_code"] == "100196"]
    assert len(avela) == 1, "AVELA debe consolidarse en 1 fila"
    assert avela[0]["boxes"] == 4, "AVELA debe tener 4 cajas consolidadas"
    assert avela[0]["pairs"] == 32, "AVELA debe tener 32 pares consolidados"
    assert avela[0]["amount_fob"] == 200.0, "AVELA debe sumar FOB"

    # Verificar NEGRO 01 (2 curvas distintas)
    negro = [r for r in normalized_rows if r["color_code"] == "15745"]
    assert len(negro) == 2, "NEGRO debe tener 2 filas (2 curvas distintas)"

    print("[OK] Normalizacion correcta: 8 filas Excel -> 3 moleculas unicas\n")

    # Mostrar resultado final
    print("Resultado final (filas a insertar en BD):")
    print("=" * 70)
    for r in normalized_rows:
        print(f"  {r['color']:15} | {r['boxes']:2} cjs | {r['pairs']:3} pares | item(s): {r['item']}")
    print()


if __name__ == "__main__":
    test_mol_key()
    test_normalization()
    print("=" * 70)
    print("TODOS LOS TESTS PASARON [OK]")
    print("=" * 70)
