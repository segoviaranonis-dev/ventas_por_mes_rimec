"""
core/auditoria.py
─────────────────────────────────────────────────────────────────────
Auditoría forense del flujo de abastecimiento.

Cada transición significativa de estado genera un registro inmutable
en flujo_auditoria con un snapshot JSONB completo del objeto en ese
instante exacto. Los registros nunca se borran ni modifican.

Uso desde cualquier módulo:
    from core.auditoria import log_flujo
    log_flujo(
        entidad="IC",
        entidad_id=ic_id,
        nro_registro="IC-2026-0001",
        accion="IC_AUTORIZADA",
        estado_antes="PENDIENTE_OPERATIVO",
        estado_despues="AUTORIZADO",
        snap={
            "marca": "MOLEKINHA",
            "pares": 540,
            "proveedor": "BEIRA RIO",
            "cliente": "MERCADERIA PARA STOCK",
            "vendedor": "ADM",
            "evento_precio": "Temporada 2026-1",
            "monto_neto": 125000,
            "eta": "2026-05-01",
        },
    )
"""

import json
from datetime import datetime, timezone

from sqlalchemy import text
from core.database import engine


# ─────────────────────────────────────────────────────────────────────────────
# ACCIONES ESTÁNDAR — catálogo de eventos auditables
# ─────────────────────────────────────────────────────────────────────────────

class A:
    # IC
    IC_CREADA               = "IC_CREADA"
    IC_AUTORIZADA           = "IC_AUTORIZADA"
    IC_DEVUELTA_ADMIN       = "IC_DEVUELTA_ADMIN"
    IC_REAUTORIZADA         = "IC_REAUTORIZADA"
    IC_ANULADA              = "IC_ANULADA"

    # Digitación
    DIG_PP_CREADO           = "DIG_PP_CREADO"
    DIG_IC_ASIGNADA         = "DIG_IC_ASIGNADA"
    DIG_IC_DEVUELTA         = "DIG_IC_DEVUELTA"
    DIG_PP_CERRADO          = "DIG_PP_CERRADO"

    # PP
    PP_F9_CARGADO           = "PP_F9_CARGADO"
    PP_ENVIADO_COMPRA       = "PP_ENVIADO_COMPRA"
    PP_RECHAZADO_COMPRA     = "PP_RECHAZADO_COMPRA"

    # Compra Legal
    CL_CREADA               = "CL_CREADA"
    CL_PP_AGREGADO          = "CL_PP_AGREGADO"
    CL_FINALIZADA           = "CL_FINALIZADA"

    # PP — operaciones logísticas
    PP_ETA_ACTUALIZADA      = "PP_ETA_ACTUALIZADA"
    PP_CONFIGURADO          = "PP_CONFIGURADO"
    DIG_IC_DESASIGNADA      = "DIG_IC_DESASIGNADA"

    # Traspaso / Movimiento
    TRASPASO_ENVIADO        = "TRASPASO_ENVIADO"
    TRASPASO_CONFIRMADO     = "TRASPASO_CONFIRMADO"


# ─────────────────────────────────────────────────────────────────────────────
# ESCRITURA FORENSE
# ─────────────────────────────────────────────────────────────────────────────

def log_flujo(
    entidad:        str,
    entidad_id:     int,
    accion:         str,
    snap:           dict,
    nro_registro:   str  | None = None,
    estado_antes:   str  | None = None,
    estado_despues: str  | None = None,
    usuario_id:     int  | None = None,
) -> None:
    """
    Registra una transición en flujo_auditoria.
    Nunca lanza excepciones — un fallo de auditoría no debe bloquear
    la operación principal. Silencia errores y continúa.
    """
    try:
        snap_json = json.dumps(snap, ensure_ascii=False, default=str)
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO flujo_auditoria
                    (entidad, entidad_id, nro_registro,
                     accion, estado_antes, estado_despues,
                     snap, usuario_id, created_at)
                VALUES
                    (:ent, :eid, :nro,
                     :accion, :ea, :ed,
                     :snap::jsonb, :uid, :ts)
            """), {
                "ent":    entidad,
                "eid":    entidad_id,
                "nro":    nro_registro,
                "accion": accion,
                "ea":     estado_antes,
                "ed":     estado_despues,
                "snap":   snap_json,
                "uid":    usuario_id,
                "ts":     datetime.now(timezone.utc),
            })
    except Exception:
        pass  # auditoría nunca bloquea el flujo principal


# ─────────────────────────────────────────────────────────────────────────────
# LECTURA FORENSE
# ─────────────────────────────────────────────────────────────────────────────

def get_historial_entidad(entidad: str, entidad_id: int) -> list[dict]:
    """
    Retorna el historial completo de una entidad ordenado cronológicamente.
    Cada ítem: {accion, estado_antes, estado_despues, snap, usuario_id, created_at}
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT accion, estado_antes, estado_despues,
                       snap, usuario_id, created_at
                FROM flujo_auditoria
                WHERE entidad = :ent AND entidad_id = :eid
                ORDER BY created_at ASC
            """), {"ent": entidad, "eid": entidad_id}).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []


def get_historial_nro(nro_registro: str) -> list[dict]:
    """Historial por número de registro (IC-2026-0001, PP-2026-0001, etc.)."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT entidad, entidad_id, accion,
                       estado_antes, estado_despues,
                       snap, usuario_id, created_at
                FROM flujo_auditoria
                WHERE nro_registro = :nro
                ORDER BY created_at ASC
            """), {"nro": nro_registro}).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []


def get_feed_reciente(limit: int = 50) -> list[dict]:
    """Feed cronológico inverso de las últimas N acciones en todo el sistema."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT entidad, entidad_id, nro_registro,
                       accion, estado_antes, estado_despues,
                       snap, usuario_id, created_at
                FROM flujo_auditoria
                ORDER BY created_at DESC
                LIMIT :lim
            """), {"lim": limit}).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception:
        return []
