#!/usr/bin/env python3
"""
Corrección montos FI legacy — alinea factura_interna_detalle con cabecera.

Criterio canónico (PV147 / actualizar_fi_encabezado):
  precio_neto = round(precio_base * cascada descuentos)
  subtotal    = precio_neto * pares
  total_monto = SUM(subtotal)

precio_unit se conserva como precio lista (precio_base).
"""
from __future__ import annotations

from sqlalchemy import text as sqlt

from core.database import engine, get_dataframe
from core.auditoria import log_flujo


def _cascada(precio_base: float, d1, d2, d3, d4) -> int:
    p = float(precio_base)
    for d in (d1, d2, d3, d4):
        if d and float(d) > 0:
            p *= 1 - float(d) / 100
    return int(round(p))


def _fis_desalineadas():
    return get_dataframe("""
        SELECT fi.id AS fi_id, fi.pv_global, fi.total_monto,
               fi.descuento_1, fi.descuento_2, fi.descuento_3, fi.descuento_4
        FROM factura_interna fi
        JOIN LATERAL (
          SELECT SUM(subtotal) AS sum_det, SUM(pares) AS sum_pares
          FROM factura_interna_detalle WHERE factura_id = fi.id
        ) s ON true
        WHERE fi.estado = 'CONFIRMADA'
          AND (ABS(COALESCE(s.sum_pares, 0) - COALESCE(fi.total_pares, 0)) > 0
               OR ABS(COALESCE(s.sum_det, 0) - COALESCE(fi.total_monto, 0)) > 1)
        ORDER BY fi.pv_global
    """)


def corregir_fi(conn, fi_row) -> tuple[int, int, int]:
    """Retorna (n_lineas, total_monto_nuevo, fi_id)."""
    fi_id = int(fi_row.fi_id)
    d1, d2, d3, d4 = fi_row.descuento_1, fi_row.descuento_2, fi_row.descuento_3, fi_row.descuento_4

    detalles = conn.execute(sqlt("""
        SELECT id, pares, cajas, precio_unit, precio_neto, subtotal
        FROM factura_interna_detalle
        WHERE factura_id = :fi_id
        ORDER BY id
    """), {"fi_id": fi_id}).fetchall()

    total_monto = 0
    total_pares = 0
    n = 0

    for det in detalles:
        pares = int(det.pares or 0)
        pu = float(det.precio_unit or 0)
        pn_old = float(det.precio_neto or 0)
        # Lista: tomar el mayor (legacy guardaba neto en precio_neto y lista en precio_unit)
        precio_base = max(pu, pn_old) if pu and pn_old else (pu or pn_old)
        if precio_base <= 0:
            continue

        precio_neto = _cascada(precio_base, d1, d2, d3, d4)
        subtotal = precio_neto * pares
        total_monto += subtotal
        total_pares += pares

        conn.execute(sqlt("""
            UPDATE factura_interna_detalle
            SET precio_neto = :pn,
                subtotal = :sub,
                precio_unit = :pu
            WHERE id = :id
        """), {
            "pn": precio_neto,
            "sub": subtotal,
            "pu": int(round(precio_base)),
            "id": int(det.id),
        })
        n += 1

    conn.execute(sqlt("""
        UPDATE factura_interna
        SET total_monto = :monto,
            total_pares = :pares
        WHERE id = :fi_id
    """), {"monto": total_monto, "pares": total_pares, "fi_id": fi_id})

    return n, total_monto, fi_id


def main() -> None:
    antes = _fis_desalineadas()
    n_antes = 0 if antes is None or antes.empty else len(antes)
    print(f"FIs desalineadas antes: {n_antes}")

    if n_antes == 0:
        print("Nada que corregir.")
        return

    print(antes.to_string(index=False))

    corregidas = []
    with engine.begin() as conn:
        for row in antes.itertuples():
            n_lineas, monto, fi_id = corregir_fi(conn, row)
            pv = int(row.pv_global) if row.pv_global else None
            corregidas.append((fi_id, pv, int(row.total_monto or 0), monto, n_lineas))
            log_flujo(
                entidad="factura_interna",
                entidad_id=fi_id,
                accion="BACKFILL_MONTO_FI_LEGACY",
                snap={
                    "pv_global": pv,
                    "total_monto_antes": float(row.total_monto or 0),
                    "total_monto_despues": monto,
                    "lineas": n_lineas,
                },
            )

    print("\n--- Corregidas ---")
    for fi_id, pv, old, new, nl in corregidas:
        print(f"  fi_id={fi_id} PV{pv:06d}: {old:,} -> {new:,} ({nl} lineas)")

    despues = _fis_desalineadas()
    n_desp = 0 if despues is None or despues.empty else len(despues)
    print(f"\nFIs desalineadas después: {n_desp}")
    if n_desp:
        print(despues.to_string(index=False))
    else:
        print("OK: cabecera = suma detalle en todas las CONFIRMADA")


if __name__ == "__main__":
    main()
