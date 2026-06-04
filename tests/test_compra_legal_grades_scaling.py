import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.compra_legal.grades import normalizar_tallas_a_pares


class GradeScalingTests(unittest.TestCase):
    def test_normalizar_tallas_multiplica_caja_base_a_pares_fi(self):
        base = {"25": 1, "26": 1, "27": 1, "28": 1, "29": 1, "30": 1, "31": 1, "32": 1, "33": 1, "34": 1, "35": 1, "36": 1}

        scaled = normalizar_tallas_a_pares(base, 36)

        self.assertEqual(sum(scaled.values()), 36)
        self.assertEqual(set(scaled.values()), {3})
        self.assertEqual(scaled["t25"], 3)
        self.assertEqual(scaled["t36"], 3)

    def test_normalizar_tallas_no_cambia_si_ya_suma_pares_objetivo(self):
        base = {"t35": 2, "t36": 3, "t37": 3, "t38": 2}

        self.assertEqual(normalizar_tallas_a_pares(base, 10), base)

    def test_normalizar_tallas_reparte_resto_sin_perder_pares(self):
        base = {"35": 1, "36": 2, "37": 1}

        scaled = normalizar_tallas_a_pares(base, 10)

        self.assertEqual(sum(scaled.values()), 10)
        self.assertTrue(all(qty > 0 for qty in scaled.values()))
        self.assertGreaterEqual(scaled["t36"], scaled["t35"])
        self.assertGreaterEqual(scaled["t36"], scaled["t37"])

    def test_normalizar_tallas_sin_objetivo_devuelve_curva_limpia(self):
        base = {"35": "1", "36": None, "37": "2"}

        self.assertEqual(normalizar_tallas_a_pares(base, None), {"t35": 1, "t37": 2})


if __name__ == "__main__":
    unittest.main()
