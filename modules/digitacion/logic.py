"""
DIGITACIÓN — logic.py
Puente entre Intención de Compra y Pedido Proveedor.
Asigna nro_pedido_fabrica y agrupa ICs en PPs.
"""

from datetime import date
import pandas as pd
from sqlalchemy import text
from core.database import get_dataframe, engine, DBInspector
from core.auditoria import log_flujo, A


# ─────────────────────────────────────────────────────────────────────────────
# LECTURAS
# ─────────────────────────────────────────────────────────────────────────────

def get_ics_pendientes() -> pd.DataFrame:
    """ICs en estado AUTORIZADO sin asignación en la tabla puente."""
    return get_dataframe("""
        SELECT
            ic.id,
            ic.numero_registro                      AS nro_ic,
            mv.descp_marca                          AS marca,
            COALESCE(cv.descp_categoria, '—')       AS categoria,
            pe.nombre_evento                        AS evento_precio,
            ic.precio_evento_id,
            ic.fecha_llegada                        AS eta,
            ic.cantidad_total_pares                 AS pares,
            ic.estado
        FROM intencion_compra ic
        JOIN marca_v2       mv ON mv.id_marca       = ic.id_marca
        LEFT JOIN categoria_v2 cv ON cv.id_categoria = ic.categoria_id
        LEFT JOIN precio_evento pe ON pe.id          = ic.precio_evento_id
        WHERE ic.estado = 'AUTORIZADO'
          AND ic.id NOT IN (
              SELECT intencion_compra_id FROM intencion_compra_pedido
          )
        ORDER BY ic.fecha_llegada ASC NULLS LAST, ic.numero_registro
    """)


def get_pps_abiertos() -> pd.DataFrame:
    """PPs con estado_digitacion ABIERTO con conteo de ICs asignadas."""
    return get_dataframe("""
        SELECT
            pp.id,
            pp.numero_registro                          AS nro_pp,
            pp.nro_factura_importacion                  AS factura,
            pp.estado_digitacion,
            pp.fecha_pedido,
            COUNT(icp.id)                               AS ics_asignadas
        FROM pedido_proveedor pp
        LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
        WHERE pp.estado_digitacion = 'ABIERTO'
        GROUP BY pp.id, pp.numero_registro, pp.nro_factura_importacion,
                 pp.estado_digitacion, pp.fecha_pedido
        ORDER BY pp.fecha_pedido DESC
    """)


def get_ics_de_pp(pp_id: int) -> pd.DataFrame:
    """ICs asignadas a un PP específico."""
    return get_dataframe("""
        SELECT
            ic.numero_registro  AS nro_ic,
            mv.descp_marca      AS marca,
            icp.nro_pedido_fabrica,
            pe.nombre_evento    AS evento_precio
        FROM intencion_compra_pedido icp
        JOIN intencion_compra ic ON ic.id  = icp.intencion_compra_id
        JOIN marca_v2         mv ON mv.id_marca = ic.id_marca
        LEFT JOIN precio_evento pe ON pe.id = icp.precio_evento_id
        WHERE icp.pedido_proveedor_id = :pp_id
        ORDER BY ic.numero_registro
    """, {"pp_id": pp_id})


def get_eventos_cerrados() -> pd.DataFrame:
    """Eventos de precio cerrados disponibles para asignar a una IC."""
    return get_dataframe("""
        SELECT id, nombre_evento, fecha_vigencia_desde
        FROM precio_evento
        WHERE estado = 'cerrado'
        ORDER BY created_at DESC
    """)


# ─────────────────────────────────────────────────────────────────────────────
# CREACIÓN DE PP DESDE DIGITACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def _get_next_nro_pp(anio: int) -> str:
    df = get_dataframe(
        """SELECT COALESCE(MAX(CAST(SPLIT_PART(numero_registro,'-',3) AS INTEGER)),0) AS ultimo
           FROM pedido_proveedor
           WHERE numero_registro ~ '^PP-[0-9]{4}-[0-9]+$'
             AND numero_registro LIKE :patron""",
        {"patron": f"PP-{anio}-%"}
    )
    ultimo = int(df["ultimo"].iloc[0]) if df is not None and not df.empty else 0
    return f"PP-{anio}-{ultimo + 1:04d}"


def crear_pp_digitacion(usuario_id: int | None = None) -> int | None:
    """
    Crea un PP shell para agrupar ICs desde digitación.
    Retorna el id del PP creado.
    """
    anio = date.today().year
    nro  = _get_next_nro_pp(anio)
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""INSERT INTO pedido_proveedor
                        (numero_registro, anio_fiscal, estado, estado_digitacion)
                        VALUES (:nro, :anio, 'ABIERTO', 'ABIERTO')
                        RETURNING id"""),
                {"nro": nro, "anio": anio}
            ).fetchone()
            pp_id = int(row[0]) if row else None

        if pp_id:
            log_flujo(
                entidad="PP", entidad_id=pp_id, nro_registro=nro,
                accion=A.DIG_PP_CREADO,
                estado_despues="ABIERTO",
                snap={"numero_registro": nro, "anio_fiscal": anio,
                      "origen": "DIGITACION"},
                usuario_id=usuario_id,
            )
        DBInspector.log(f"[DIGITACION] PP creado: {nro} (id={pp_id})", "SUCCESS")
        return pp_id
    except Exception as e:
        DBInspector.log(f"[DIGITACION] Error creando PP: {e}", "ERROR")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ASIGNACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def asignar_ic(ic_id: int, pp_id: int, nro_pedido_fabrica: str,
               precio_evento_id: int, usuario_id: int | None = None) -> bool:
    """
    Inserta en tabla puente + actualiza IC: estado→DIGITADO.
    Hereda datos clave de la IC al PP (pares, proveedor, categoría).
    Registra snapshot forense en flujo_auditoria.
    """
    try:
        with engine.begin() as conn:
            # ── Leer datos completos de la IC para heredar y auditar ──────────
            ic_row = conn.execute(text("""
                SELECT ic.numero_registro, ic.id_proveedor, ic.categoria_id,
                       ic.cantidad_total_pares, ic.id_marca, ic.id_cliente,
                       ic.id_vendedor, ic.monto_neto, ic.fecha_llegada,
                       mv.descp_marca, pi2.nombre AS proveedor,
                       cv.descp_cliente, vv.descp_vendedor,
                       pe.nombre_evento
                FROM intencion_compra ic
                JOIN  marca_v2              mv  ON mv.id_marca    = ic.id_marca
                JOIN  proveedor_importacion pi2 ON pi2.id         = ic.id_proveedor
                JOIN  cliente_v2            cv  ON cv.id_cliente  = ic.id_cliente
                JOIN  vendedor_v2           vv  ON vv.id_vendedor = ic.id_vendedor
                LEFT JOIN precio_evento     pe  ON pe.id          = ic.precio_evento_id
                WHERE ic.id = :ic_id
            """), {"ic_id": ic_id}).fetchone()

            if not ic_row:
                return False

            pp_row = conn.execute(text(
                "SELECT numero_registro FROM pedido_proveedor WHERE id = :pp_id"
            ), {"pp_id": pp_id}).fetchone()
            pp_nro = pp_row[0] if pp_row else str(pp_id)

            # ── Insertar puente ───────────────────────────────────────────────
            conn.execute(text("""
                INSERT INTO intencion_compra_pedido
                    (intencion_compra_id, pedido_proveedor_id,
                     nro_pedido_fabrica, precio_evento_id, asignado_por)
                VALUES (:ic_id, :pp_id, :nro, :pe_id, :uid)
            """), {"ic_id": ic_id, "pp_id": pp_id,
                   "nro": nro_pedido_fabrica.strip(),
                   "pe_id": precio_evento_id, "uid": usuario_id})

            # ── IC → DIGITADO ─────────────────────────────────────────────────
            conn.execute(text("""
                UPDATE intencion_compra
                SET estado = 'DIGITADO', precio_evento_id = :pe_id
                WHERE id = :ic_id
            """), {"pe_id": precio_evento_id, "ic_id": ic_id})

            # ── Heredar datos de la IC al PP (acumulativo para multi-IC) ─────
            conn.execute(text("""
                UPDATE pedido_proveedor
                SET proveedor_importacion_id = COALESCE(proveedor_importacion_id, :prov),
                    categoria_id             = COALESCE(categoria_id, :cat),
                    pares_comprometidos      = COALESCE(pares_comprometidos, 0) + :pares
                WHERE id = :pp_id
            """), {
                "prov":  ic_row.id_proveedor,
                "cat":   ic_row.categoria_id,
                "pares": ic_row.cantidad_total_pares,
                "pp_id": pp_id,
            })

        # ── Snapshot forense IC ───────────────────────────────────────────────
        snap_ic = {
            "pp_asignado":        pp_nro,
            "nro_pedido_fabrica": nro_pedido_fabrica.strip(),
            "marca":              ic_row.descp_marca,
            "proveedor":          ic_row.proveedor,
            "cliente":            ic_row.descp_cliente,
            "vendedor":           ic_row.descp_vendedor,
            "pares":              ic_row.cantidad_total_pares,
            "monto_neto":         float(ic_row.monto_neto) if ic_row.monto_neto else None,
            "eta":                str(ic_row.fecha_llegada) if ic_row.fecha_llegada else None,
            "evento_precio":      ic_row.nombre_evento,
            "precio_evento_id":   precio_evento_id,
        }
        log_flujo(
            entidad="IC", entidad_id=ic_id,
            nro_registro=ic_row.numero_registro,
            accion=A.DIG_IC_ASIGNADA,
            estado_antes="AUTORIZADO", estado_despues="DIGITADO",
            snap=snap_ic, usuario_id=usuario_id,
        )

        # ── Snapshot forense PP ───────────────────────────────────────────────
        log_flujo(
            entidad="PP", entidad_id=pp_id, nro_registro=pp_nro,
            accion=A.DIG_IC_ASIGNADA,
            snap={
                "ic_asignada":        ic_row.numero_registro,
                "nro_pedido_fabrica": nro_pedido_fabrica.strip(),
                "marca":              ic_row.descp_marca,
                "proveedor":          ic_row.proveedor,
                "cliente":            ic_row.descp_cliente,
                "vendedor":           ic_row.descp_vendedor,
                "pares_heredados":    ic_row.cantidad_total_pares,
                "categoria_id":       ic_row.categoria_id,
            },
            usuario_id=usuario_id,
        )

        DBInspector.log(
            f"[DIGITACION] IC {ic_row.numero_registro} → PP {pp_nro} "
            f"({ic_row.cantidad_total_pares} pares)", "SUCCESS"
        )
        return True

    except Exception as e:
        DBInspector.log(f"[DIGITACION] Error asignando IC {ic_id}: {e}", "ERROR")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# DEVOLUCIÓN
# ─────────────────────────────────────────────────────────────────────────────

def devolver_ic(ic_id: int, motivo: str, usuario_id: int | None = None) -> bool:
    """
    Devuelve la IC a Administración: estado→DEVUELTO_ADMIN + guarda motivo.
    La IC desaparece de Digitación y reaparece en IC módulo pestaña DEVUELTAS.
    """
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc)
    try:
        with engine.begin() as conn:
            ic_row = conn.execute(text("""
                SELECT ic.numero_registro, mv.descp_marca, ic.cantidad_total_pares
                FROM intencion_compra ic
                JOIN marca_v2 mv ON mv.id_marca = ic.id_marca
                WHERE ic.id = :ic_id
            """), {"ic_id": ic_id}).fetchone()

            conn.execute(text("""
                UPDATE intencion_compra
                SET estado = 'DEVUELTO_ADMIN',
                    motivo_devolucion = :motivo,
                    devuelto_at = :ts
                WHERE id = :ic_id AND estado = 'AUTORIZADO'
            """), {"motivo": motivo.strip(), "ts": ts, "ic_id": ic_id})

        nro = ic_row.numero_registro if ic_row else str(ic_id)
        log_flujo(
            entidad="IC", entidad_id=ic_id, nro_registro=nro,
            accion=A.DIG_IC_DEVUELTA,
            estado_antes="AUTORIZADO", estado_despues="DEVUELTO_ADMIN",
            snap={
                "motivo": motivo.strip(),
                "marca":  ic_row.descp_marca if ic_row else None,
                "pares":  ic_row.cantidad_total_pares if ic_row else None,
                "devuelto_at": str(ts),
            },
            usuario_id=usuario_id,
        )
        DBInspector.log(f"[DIGITACION] IC {nro} devuelta. Motivo: {motivo[:60]}", "INFO")
        return True
    except Exception as e:
        DBInspector.log(f"[DIGITACION] Error devolviendo IC {ic_id}: {e}", "ERROR")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# CIERRE DE PP
# ─────────────────────────────────────────────────────────────────────────────

def cerrar_pp(pp_id: int, nro_factura: str, usuario_id: int | None = None) -> bool:
    """
    Cierra el PP para digitación: registra número de factura de importación
    y cambia estado_digitacion→CERRADO. El PP queda disponible para Compra Legal.
    """
    try:
        with engine.begin() as conn:
            pp_row = conn.execute(text("""
                SELECT pp.numero_registro, pp.pares_comprometidos,
                       pi2.nombre AS proveedor,
                       STRING_AGG(DISTINCT mv.descp_marca, ' / ') AS marcas,
                       COUNT(icp.id) AS n_ics
                FROM pedido_proveedor pp
                LEFT JOIN proveedor_importacion pi2 ON pi2.id = pp.proveedor_importacion_id
                LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
                LEFT JOIN intencion_compra ic ON ic.id = icp.intencion_compra_id
                LEFT JOIN marca_v2 mv ON mv.id_marca = ic.id_marca
                WHERE pp.id = :pp_id
                GROUP BY pp.numero_registro, pp.pares_comprometidos, pi2.nombre
            """), {"pp_id": pp_id}).fetchone()

            conn.execute(text("""
                UPDATE pedido_proveedor
                SET estado_digitacion = 'CERRADO',
                    nro_factura_importacion = :fac
                WHERE id = :pp_id AND estado_digitacion = 'ABIERTO'
            """), {"fac": nro_factura.strip(), "pp_id": pp_id})

        nro = pp_row.numero_registro if pp_row else str(pp_id)
        log_flujo(
            entidad="PP", entidad_id=pp_id, nro_registro=nro,
            accion=A.DIG_PP_CERRADO,
            estado_antes="ABIERTO", estado_despues="CERRADO",
            snap={
                "nro_factura_importacion": nro_factura.strip(),
                "proveedor":               pp_row.proveedor if pp_row else None,
                "marcas":                  pp_row.marcas if pp_row else None,
                "pares_comprometidos":     int(pp_row.pares_comprometidos or 0) if pp_row else 0,
                "ics_asignadas":           int(pp_row.n_ics or 0) if pp_row else 0,
            },
            usuario_id=usuario_id,
        )
        DBInspector.log(f"[DIGITACION] PP {nro} cerrado. Factura: {nro_factura}", "SUCCESS")
        return True
    except Exception as e:
        DBInspector.log(f"[DIGITACION] Error cerrando PP {pp_id}: {e}", "ERROR")
        return False
