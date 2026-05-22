"""
Aplicar MIG-073 -> 076 (snapshot precios PPD + vista determinista).
Verificación post-apply: cobertura lpn en v_stock_rimec vs PPD.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backfill_combinacion_desde_ppd import _db_url

MIGS = (
    "073_snapshot_precio_ppd_columnas.sql",
    "074_fn_vincular_listado_a_pp.sql",
    "075_backfill_snapshot_precio_ppd.sql",
    "076_v_stock_rimec_snapshot_ppd.sql",
)


def main() -> int:
    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL / credenciales")
        return 1

    import psycopg2

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    print("=" * 72)
    print("APLICAR MIG-073 -> MIG-076")
    print("=" * 72)

    for name in MIGS:
        path = ROOT / "migrations" / name
        sql = path.read_text(encoding="utf-8")
        print(f"\n>> {name}")
        cur.execute(sql)
        conn.commit()
        print("   OK")

    cur.execute("""
        SELECT
          COUNT(*) AS total_vista,
          COUNT(*) FILTER (WHERE lpn IS NOT NULL) AS con_lpn_vista
        FROM public.v_stock_rimec
    """)
    total_v, con_v = cur.fetchone()

    cur.execute("""
        SELECT
          COUNT(*) AS total_saldo,
          COUNT(*) FILTER (WHERE ppd.precio_lpn IS NOT NULL) AS con_lpn_ppd
        FROM public.pedido_proveedor_detalle ppd
        JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
          AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
    """)
    total_p, con_p = cur.fetchone()

    cur.execute("""
        SELECT COUNT(*) FROM public.precio_lista pl
        WHERE pl.evento_id IN (
          SELECT DISTINCT icp.precio_evento_id
          FROM public.intencion_compra_pedido icp
          JOIN public.pedido_proveedor pp ON pp.id = icp.pedido_proveedor_id
          WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
            AND icp.precio_evento_id IS NOT NULL
        ) AND pl.lpn IS NOT NULL
    """)
    pl_rows = cur.fetchone()[0]

    conn.close()

    print("\n" + "=" * 72)
    print("VERIFICACIÓN")
    print("=" * 72)
    print(f"  v_stock_rimec:     {con_v}/{total_v} con lpn")
    print(f"  PPD (saldo>0):     {con_p}/{total_p} con precio_lpn")
    print(f"  precio_lista rows: {pl_rows} (eventos activos)")
    if total_v and con_v == total_p and con_p > 0:
        print("\n  OK — vista alineada con snapshot PPD")
    elif con_p == 0:
        print("\n  ALERTA — backfill no pobló PPD (revisar match precio_lista / pilares)")
    else:
        print(f"\n  REVISAR — gap vista/PPD: vista={con_v} ppd={con_p}")

    return 0 if con_p > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
