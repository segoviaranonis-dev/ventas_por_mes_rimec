"""
MIG-077 — extender vincular_listado_a_pp con match por códigos denormalizados.
Re-corre vinculación sobre PP 6 (74 huérfanos) y reporta cobertura final.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backfill_combinacion_desde_ppd import _db_url


def main() -> int:
    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return 1

    import psycopg2

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    print("=" * 72)
    print("APLICAR MIG-077 + RE-VINCULAR PP 6")
    print("=" * 72)

    sql_path = ROOT / "migrations" / "077_vincular_match_por_codigos.sql"
    sql = sql_path.read_text(encoding="utf-8")
    print("\n>> 077_vincular_match_por_codigos.sql")
    cur.execute(sql)
    conn.commit()
    print("   OK")

    cur.execute("""
        SELECT COUNT(*)
        FROM public.pedido_proveedor_detalle ppd
        WHERE ppd.pedido_proveedor_id = 6
          AND ppd.precio_lpn IS NULL
          AND GREATEST(0, COALESCE(ppd.cantidad_pares,0) - COALESCE(ppd.pares_vendidos,0)) > 0
    """)
    sin_precio_pre = cur.fetchone()[0]
    print(f"\nPP 6 huérfanos antes: {sin_precio_pre}")

    cur.execute("SELECT public.vincular_listado_a_pp(6, NULL, NULL) AS r")
    row = cur.fetchone()[0]
    if isinstance(row, str):
        row = json.loads(row)
    conn.commit()
    print(f"\nResultado vincular_listado_a_pp(6):\n  {json.dumps(row, indent=2, ensure_ascii=False)}")

    cur.execute("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE lpn IS NOT NULL) AS con_lpn
        FROM public.v_stock_rimec
    """)
    total_v, con_v = cur.fetchone()

    cur.execute("""
        SELECT pp.numero_registro,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE ppd.precio_lpn IS NOT NULL) AS con_precio
        FROM public.pedido_proveedor_detalle ppd
        JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
        WHERE pp.estado = ANY(ARRAY['ABIERTO','ENVIADO'])
          AND GREATEST(0, COALESCE(ppd.cantidad_pares,0) - COALESCE(ppd.pares_vendidos,0)) > 0
        GROUP BY pp.numero_registro
        ORDER BY pp.numero_registro
    """)
    desglose = cur.fetchall()

    cur.execute("""
        SELECT ppd.id, ppd.linea, ppd.referencia, ppd.material_code,
               ppd.descp_color, ppd.cantidad_pares - COALESCE(ppd.pares_vendidos,0) AS saldo
        FROM public.pedido_proveedor_detalle ppd
        WHERE ppd.pedido_proveedor_id = 6
          AND ppd.precio_lpn IS NULL
          AND GREATEST(0, COALESCE(ppd.cantidad_pares,0) - COALESCE(ppd.pares_vendidos,0)) > 0
        ORDER BY ppd.id
        LIMIT 20
    """)
    residuales = cur.fetchall()

    conn.close()

    print("\n" + "=" * 72)
    print("VERIFICACIÓN POST MIG-077")
    print("=" * 72)
    print(f"  v_stock_rimec: {con_v}/{total_v} con lpn ({(con_v/total_v*100) if total_v else 0:.1f}%)")
    print("\nDesglose por PP:")
    for nro, total, con_precio in desglose:
        pct = (con_precio / total * 100) if total else 0
        flag = "OK" if con_precio == total else "REVISAR"
        print(f"  {nro:<18} {con_precio:>4}/{total:<4} ({pct:5.1f}%) [{flag}]")

    if residuales:
        print(f"\nResiduales PP 6 (primeros 20 de {len(residuales)}):")
        print("  det_id | linea | ref | material | color | saldo")
        for r in residuales:
            print(f"  {r[0]:<6} | {r[1]:<5} | {r[2]:<5} | {r[3]:<8} | {r[4]:<10} | {r[5]}")
    else:
        print("\n  PP 6 al 100%: cobertura total alcanzada.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
