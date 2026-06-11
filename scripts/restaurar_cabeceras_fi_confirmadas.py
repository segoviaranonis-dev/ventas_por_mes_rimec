#!/usr/bin/env python3
"""
Restaura total_monto confirmado en FIs 50% donde el backfill subió la cabecera.

Mantiene fixes correctos: PV29 (5121600), PV75 (2186400).
"""
from __future__ import annotations

from sqlalchemy import text as sqlt

from core.database import engine, get_dataframe

# total_monto confirmado antes del backfill (auditoría manual)
CABECERAS_CONFIRMADAS = {
    84: 3044600.0,   # PV000084 fi 134
    95: 8934600.0,   # PV000095 fi 122
    104: 19054800.0, # PV000104 fi 110
    107: 10335600.0, # fi 98
    108: 4165200.0,  # fi 99
    109: 6193800.0,  # fi 100
    110: 6333600.0,  # fi 96
    111: 10215000.0, # fi 92
    113: 4165200.0,  # fi 93
    114: 6739800.0,  # fi 94
    115: 6739800.0,  # fi 97
    116: 10335600.0, # fi 95
    117: 783200.0,   # fi 137
    142: 8818800.0,  # fi 162
}


def _desalineadas():
    return get_dataframe("""
        SELECT fi.id AS fi_id, fi.pv_global, fi.total_monto,
               s.sum_det
        FROM factura_interna fi
        JOIN LATERAL (
          SELECT SUM(subtotal) sum_det FROM factura_interna_detalle
          WHERE factura_id = fi.id
        ) s ON true
        WHERE fi.estado = 'CONFIRMADA'
          AND ABS(COALESCE(s.sum_det,0) - COALESCE(fi.total_monto,0)) > 1
    """)


def restaurar_fi(conn, fi_id: int, total_objetivo: float) -> None:
    detalles = conn.execute(sqlt("""
        SELECT id, pares, subtotal FROM factura_interna_detalle
        WHERE factura_id = :fi_id ORDER BY id
    """), {"fi_id": fi_id}).fetchall()

    sum_actual = sum(float(d.subtotal or 0) for d in detalles)
    if sum_actual <= 0:
        conn.execute(sqlt("""
            UPDATE factura_interna SET total_monto = :m WHERE id = :fi_id
        """), {"m": total_objetivo, "fi_id": fi_id})
        return

    factor = total_objetivo / sum_actual
    acum = 0
    ids = list(detalles)
    for i, det in enumerate(ids):
        pares = int(det.pares or 1)
        if i == len(ids) - 1:
            sub = int(round(total_objetivo - acum))
        else:
            sub = int(round(float(det.subtotal or 0) * factor))
            acum += sub
        pn = int(round(sub / pares)) if pares else 0
        conn.execute(sqlt("""
            UPDATE factura_interna_detalle
            SET subtotal = :sub, precio_neto = :pn
            WHERE id = :id
        """), {"sub": sub, "pn": pn, "id": int(det.id)})

    conn.execute(sqlt("""
        UPDATE factura_interna SET total_monto = :m WHERE id = :fi_id
    """), {"m": int(round(total_objetivo)), "fi_id": fi_id})


def main() -> None:
    print("=== Restaurar cabeceras confirmadas (14 FIs) ===")
    with engine.begin() as conn:
        for pv, monto in sorted(CABECERAS_CONFIRMADAS.items()):
            row = conn.execute(sqlt("""
                SELECT id, total_monto FROM factura_interna
                WHERE pv_global = :pv AND estado = 'CONFIRMADA'
            """), {"pv": pv}).fetchone()
            if not row:
                print(f"  PV{pv:06d}: no encontrada")
                continue
            fi_id = int(row.id)
            antes = float(row.total_monto or 0)
            if abs(antes - monto) < 1:
                print(f"  PV{pv:06d}: ya OK ({monto:,.0f})")
                continue
            restaurar_fi(conn, fi_id, monto)
            print(f"  PV{pv:06d}: {antes:,.0f} -> {monto:,.0f}")

    rest = _desalineadas()
    n = 0 if rest is None or rest.empty else len(rest)
    print(f"\nDesalineadas restantes: {n}")
    if n:
        print(rest.to_string(index=False))


if __name__ == "__main__":
    main()
