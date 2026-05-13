# =============================================================================
# MÓDULO: Pedidos Web — Capa de datos
# ARCHIVO: modules/pedido_web/logic.py
# =============================================================================

import streamlit as st
import pandas as pd
from datetime import date
from core.database import get_dataframe, commit_query

ALM_WEB_01 = 1


def get_resumen_estados() -> dict:
    df = get_dataframe("SELECT estado, COUNT(*) AS cant FROM pedido_web GROUP BY estado")
    if df.empty:
        return {}
    return dict(zip(df['estado'], df['cant']))


def get_pedidos(estado_filtro: str = 'PENDIENTE') -> pd.DataFrame:
    return get_dataframe("""
        SELECT
            pw.id, pw.created_at, pw.estado,
            pw.cliente_nombre, pw.cliente_telefono, pw.cliente_email,
            pw.total, pw.notas_cliente, pw.notas_admin,
            cw.cedula
        FROM pedido_web pw
        LEFT JOIN cliente_web cw ON cw.id = pw.cliente_web_id
        WHERE pw.estado = :estado
        ORDER BY pw.created_at DESC
    """, params={"estado": estado_filtro})


def get_detalle_pedido(pedido_id: int) -> pd.DataFrame:
    return get_dataframe("""
        SELECT id, linea_id, referencia_id, linea_codigo, referencia_codigo, color_nombre,
               talla_codigo, material_desc, marca, cantidad,
               precio_unitario, imagen_url
        FROM pedido_web_detalle
        WHERE pedido_id = :pid
        ORDER BY id
    """, params={"pid": pedido_id})


def _buscar_combinacion_id(linea: str, referencia: str, color: str, talla: str) -> int | None:
    # OT-2026-020: Usar nombres correctos post-migración 004
    df = get_dataframe("""
        SELECT c.id
        FROM combinacion c
        JOIN linea      l   ON l.id   = c.linea_id
        JOIN referencia r   ON r.id   = c.referencia_id
        JOIN color      col ON col.id = c.color_id
        JOIN talla      tl  ON tl.id  = c.talla_id
        WHERE l.codigo_proveedor = :linea
          AND r.codigo_proveedor = :ref
          AND col.nombre         = :color
          AND tl.talla_etiqueta  = :talla
        LIMIT 1
    """, params={"linea": linea, "ref": referencia, "color": color, "talla": talla})
    if df.empty:
        return None
    return int(df.iloc[0]["id"])


def confirmar_pedido(pedido_id: int, usuario_id: int = 1) -> tuple[bool, str]:
    detalle = get_detalle_pedido(pedido_id)
    if detalle.empty:
        return False, "El pedido no tiene items."

    hoy     = date.today().isoformat()
    doc_ref = f"PW-{pedido_id:06d}"

    ok = commit_query("""
        INSERT INTO movimiento
            (tipo, fecha, almacen_origen_id, almacen_destino_id,
             documento_ref, usuario_id, estado, notas)
        VALUES
            ('VENTA_WEB', :fecha, :alm, NULL,
             :doc, :uid, 'CONFIRMADO', 'Venta desde catálogo web')
    """, params={"fecha": hoy, "alm": ALM_WEB_01, "doc": doc_ref, "uid": usuario_id})

    if not ok:
        return False, "Error al crear el movimiento de salida."

    df_mov = get_dataframe(
        "SELECT id FROM movimiento WHERE documento_ref = :doc LIMIT 1",
        params={"doc": doc_ref}
    )
    if df_mov.empty:
        return False, "No se pudo recuperar el movimiento creado."
    movimiento_id = int(df_mov.iloc[0]["id"])

    sin_match = []
    for _, row in detalle.iterrows():
        comb_id = _buscar_combinacion_id(
            str(row["linea_codigo"]), str(row["referencia_codigo"]),
            str(row["color_nombre"]),  str(row["talla_codigo"]),
        )
        if comb_id is None:
            sin_match.append(f"{row['linea_codigo']}-{row['referencia_codigo']} T.{row['talla_codigo']}")
            continue

        commit_query("""
            INSERT INTO movimiento_detalle
                (movimiento_id, combinacion_id, cantidad, signo, precio_unitario)
            VALUES (:mov, :comb, :cant, 1, :precio)
        """, params={
            "mov":    movimiento_id,
            "comb":   comb_id,
            "cant":   int(row["cantidad"]),
            "precio": float(row["precio_unitario"] or 0),
        })

    commit_query("""
        UPDATE pedido_web SET estado = 'CONFIRMADO', updated_at = NOW()
        WHERE id = :pid
    """, params={"pid": pedido_id})

    aviso = f" ⚠ Sin combinación (no descontados): {', '.join(sin_match)}" if sin_match else ""
    return True, f"Pedido #{pedido_id:06d} confirmado y stock descontado.{aviso}"


def rechazar_pedido(pedido_id: int, motivo: str = '') -> tuple[bool, str]:
    ok = commit_query("""
        UPDATE pedido_web
        SET estado = 'RECHAZADO', notas_admin = :motivo, updated_at = NOW()
        WHERE id = :pid
    """, params={"pid": pedido_id, "motivo": motivo or None})

    return (True, f"Pedido #{pedido_id:06d} rechazado.") if ok else (False, "Error al rechazar.")
