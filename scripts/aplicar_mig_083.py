"""
Aplicar MIG-083: Descuentos por Factura Interna (Marca x Caso).
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backfill_combinacion_desde_ppd import _db_url


def main() -> int:
    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL / credenciales")
        return 1

    import psycopg2

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    print("=" * 72)
    print("APLICAR MIG-083: Descuentos por Factura Interna")
    print("=" * 72)

    path = ROOT / "migrations" / "083_descuentos_por_factura_interna.sql"
    sql = path.read_text(encoding="utf-8")
    print("\n>> 083_descuentos_por_factura_interna.sql")
    cur.execute(sql)
    conn.commit()
    print("   OK")

    # Verificar función creada
    cur.execute("""
        SELECT proname FROM pg_proc
        WHERE proname = 'carrito_calcular_facturas'
          AND pronamespace = 'public'::regnamespace
    """)
    if cur.fetchone():
        print("\n  Funcion carrito_calcular_facturas creada OK")
    else:
        print("\n  ERROR: Funcion no creada")
        return 1

    conn.close()

    print("\n" + "=" * 72)
    print("MIG-083 APLICADA")
    print("=" * 72)
    print("\nProximos pasos:")
    print("  1. Crear endpoint PATCH /api/carrito/factura en rimec-web")
    print("  2. Extender GET /api/carrito/sesion para incluir descuentos_lote")
    print("  3. Modificar UI app/carrito/page.tsx para inputs por factura")
    print("  4. Actualizar store/sesionVenta.ts con estado descuentosFactura")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
