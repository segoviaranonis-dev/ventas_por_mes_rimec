"""
core/holding_governance.py
──────────────────────────
Cierre post-COMPRA · reversiones solo holding · bloqueo usuarios.
Protocolo: .claude/1_fundamentos/1.1_protocolos/PROTOCOLO_BITACORA_USUARIOS_Y_REVERSIONES.md
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import text

from core.database import engine, get_dataframe


def holding_reversal_enabled() -> bool:
    """Reversiones excepcionales: env NEXUS_HOLDING_REVERSAL=1 en máquina holding."""
    return os.environ.get("NEXUS_HOLDING_REVERSAL", "").strip() in ("1", "true", "TRUE", "yes", "YES")


def pp_en_compra(pp_id: int) -> bool:
    """True si el PP ya pasó a COMPRA (estado ENVIADO o vínculo CL)."""
    df = get_dataframe(
        """
        SELECT pp.estado,
               EXISTS (
                 SELECT 1 FROM compra_legal_pedido clp
                 WHERE clp.pedido_proveedor_id = pp.id
               ) AS en_cl
        FROM pedido_proveedor pp
        WHERE pp.id = :id
        """,
        {"id": pp_id},
    )
    if df.empty:
        return False
    row = df.iloc[0]
    return str(row["estado"]).upper() == "ENVIADO" or bool(row["en_cl"])


def cl_cerrada_para_edicion(cl_id: int) -> bool:
    """True si la CL ya no admite rechazo de PP (DISTRIBUIDA o posterior)."""
    df = get_dataframe(
        "SELECT estado FROM compra_legal WHERE id = :id",
        {"id": cl_id},
    )
    if df.empty:
        return True
    estado = str(df.iloc[0]["estado"]).upper()
    return estado not in ("PENDIENTE", "BORRADOR")


def require_pp_pre_compra(pp_id: int, accion: str = "modificar") -> tuple[bool, str]:
    """Guard server-side: PP en COMPRA no se muta."""
    if pp_en_compra(pp_id):
        return False, (
            f"No se puede {accion}: PP en COMPRA (cerrado). "
            "Contacte al Director — reversión solo holding vía OT."
        )
    return True, ""


def require_holding_reversal(motivo: str = "reversión") -> tuple[bool, str]:
    if not holding_reversal_enabled():
        return False, (
            f"{motivo.capitalize()} bloqueada. Solo holding con NEXUS_HOLDING_REVERSAL=1 + OT."
        )
    return True, ""


def log_pp_estado(
    pp_id: int,
    estado_anterior: str | None,
    estado_nuevo: str,
    usuario_id: int | None = None,
    compra_legal_id: int | None = None,
    observaciones: str | None = None,
) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO pedido_proveedor_log
                        (pp_id, estado_anterior, estado_nuevo, usuario_id,
                         compra_legal_id, observaciones)
                    VALUES
                        (:pp, :ea, :en, :uid, :cl, :obs)
                """),
                {
                    "pp": pp_id,
                    "ea": estado_anterior,
                    "en": estado_nuevo,
                    "uid": usuario_id,
                    "cl": compra_legal_id,
                    "obs": observaciones,
                },
            )
    except Exception:
        pass


def usuario_esta_bloqueado(id_usuario: int) -> tuple[bool, str | None]:
    df = get_dataframe(
        """
        SELECT bloqueado, bloqueado_motivo
        FROM usuario_v2
        WHERE id_usuario = :id
        """,
        {"id": id_usuario},
    )
    if df.empty:
        return False, None
    row = df.iloc[0]
    if not bool(row.get("bloqueado")):
        return False, None
    return True, (row.get("bloqueado_motivo") or "Usuario bloqueado por holding.")


def bloquear_usuario(
    id_usuario: int,
    *,
    bloquear: bool,
    motivo: str | None,
    ejecutor_id: int | None,
) -> tuple[bool, str]:
    from core.auditoria import log_flujo

    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE usuario_v2
                    SET bloqueado = :b,
                        bloqueado_motivo = CASE WHEN :b THEN :motivo ELSE NULL END,
                        bloqueado_at = CASE WHEN :b THEN now() ELSE NULL END,
                        bloqueado_por = CASE WHEN :b THEN :ej ELSE NULL END
                    WHERE id_usuario = :id
                """),
                {
                    "b": bloquear,
                    "motivo": (motivo or "").strip() or None,
                    "ej": ejecutor_id,
                    "id": id_usuario,
                },
            )
        accion = "USUARIO_BLOQUEADO" if bloquear else "USUARIO_DESBLOQUEADO"
        log_flujo(
            entidad="USUARIO",
            entidad_id=id_usuario,
            accion=accion,
            estado_antes="ACTIVO" if bloquear else "BLOQUEADO",
            estado_despues="BLOQUEADO" if bloquear else "ACTIVO",
            snap={"motivo": motivo, "ejecutor_id": ejecutor_id},
            usuario_id=ejecutor_id,
        )
        return True, "Usuario bloqueado." if bloquear else "Usuario desbloqueado."
    except Exception as e:
        return False, str(e)


def get_usuario_session_row(descp_usuario: str) -> dict[str, Any] | None:
    df = get_dataframe(
        """
        SELECT id_usuario, descp_usuario, categoria, password, password_hash, rol_id,
               COALESCE(bloqueado, false) AS bloqueado, bloqueado_motivo
        FROM usuario_v2
        WHERE LOWER(TRIM(descp_usuario)) = LOWER(TRIM(:u))
        LIMIT 1
        """,
        {"u": descp_usuario},
    )
    if df.empty:
        return None
    return dict(df.iloc[0])
