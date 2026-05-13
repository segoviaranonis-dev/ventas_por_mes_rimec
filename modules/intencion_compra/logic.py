# =============================================================================
# MÓDULO: Intención de Compra
# ARCHIVO: modules/intencion_compra/logic.py
# DESCRIPCIÓN: Capa de datos exclusiva del módulo.
#              Solo get_dataframe() y commit_query(). Sin lógica en UI.
#
#  Columnas reales BD:
#    cliente_v2          → id_cliente,  descp_cliente
#    vendedor_v2         → id_vendedor, descp_vendedor
#    marca_v2            → id_marca,    descp_marca
#    plazo_v2            → id_plazo,    descp_plazo
#    proveedor_importacion → id,        nombre
#
#  Formato número de registro: IC-YYYY-XXXX  (ej: IC-2026-0001)
# =============================================================================

import logging
import streamlit as st
import pandas as pd
from datetime import date
from sqlalchemy import text
from core.database import get_dataframe, commit_query, engine
from core.auditoria import log_flujo, A

_log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGOS (caché 1 hora — son maestros estables)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def get_proveedores() -> pd.DataFrame:
    return get_dataframe(
        "SELECT id, nombre FROM proveedor_importacion WHERE activo = true ORDER BY nombre"
    )


@st.cache_data(ttl=3600)
def get_clientes() -> pd.DataFrame:
    return get_dataframe(
        "SELECT id_cliente, descp_cliente FROM cliente_v2 ORDER BY id_cliente"
    )


@st.cache_data(ttl=3600)
def get_vendedores() -> pd.DataFrame:
    return get_dataframe(
        "SELECT id_vendedor, descp_vendedor FROM vendedor_v2 ORDER BY descp_vendedor"
    )


@st.cache_data(ttl=3600)
def get_marcas() -> pd.DataFrame:
    return get_dataframe(
        "SELECT id_marca, descp_marca FROM marca_v2 ORDER BY descp_marca"
    )


@st.cache_data(ttl=3600)
def get_plazos() -> pd.DataFrame:
    return get_dataframe(
        "SELECT id_plazo, descp_plazo FROM plazo_v2 ORDER BY id_plazo"
    )


@st.cache_data(ttl=3600)
def get_tipos() -> pd.DataFrame:
    return get_dataframe(
        "SELECT id_tipo, descp_tipo FROM tipo_v2 ORDER BY id_tipo"
    )


@st.cache_data(ttl=3600)
def get_categorias() -> pd.DataFrame:
    # STOCK (id_categoria=1) excluido: nace en gestión de ventas, no en intención de compra
    return get_dataframe(
        "SELECT id_categoria, descp_categoria FROM categoria_v2 WHERE id_categoria != 1 ORDER BY id_categoria"
    )


# ─────────────────────────────────────────────────────────────────────────────
# IC CRUD — bandeja de trabajo del Director
# ─────────────────────────────────────────────────────────────────────────────

def get_ics_pendientes() -> pd.DataFrame:
    """ICs en estado PENDIENTE_OPERATIVO — tarjetas editables en la bandeja."""
    return get_dataframe("""
        SELECT ic.id, ic.numero_registro,
               ic.tipo_id,     COALESCE(tv.descp_tipo,      '—') AS tipo,
               ic.categoria_id,COALESCE(cv2.descp_categoria,'—') AS categoria,
               ic.id_marca,    mv.descp_marca                    AS marca,
               pi2.nombre                                        AS proveedor,
               cv.descp_cliente                                  AS cliente,
               vv.descp_vendedor                                 AS vendedor,
               ic.fecha_llegada,
               ic.cantidad_total_pares AS pares,
               ic.monto_neto,
               ic.precio_evento_id,
               pe.nombre_evento AS evento_precio,
               ic.nota_pedido
        FROM intencion_compra ic
        JOIN  marca_v2              mv   ON mv.id_marca       = ic.id_marca
        JOIN  cliente_v2            cv   ON cv.id_cliente     = ic.id_cliente
        JOIN  vendedor_v2           vv   ON vv.id_vendedor    = ic.id_vendedor
        JOIN  proveedor_importacion pi2  ON pi2.id            = ic.id_proveedor
        LEFT JOIN tipo_v2           tv   ON tv.id_tipo         = ic.tipo_id
        LEFT JOIN categoria_v2      cv2  ON cv2.id_categoria   = ic.categoria_id
        LEFT JOIN precio_evento     pe   ON pe.id              = ic.precio_evento_id
        WHERE ic.estado = 'PENDIENTE_OPERATIVO'
        ORDER BY ic.fecha_llegada ASC NULLS LAST, ic.numero_registro ASC
    """)


def get_ics_historial() -> pd.DataFrame:
    """ICs autorizadas o en etapas posteriores — vista de solo lectura."""
    return get_dataframe("""
        SELECT ic.numero_registro,
               COALESCE(tv.descp_tipo,      '—') AS tipo,
               COALESCE(cv2.descp_categoria,'—') AS categoria,
               mv.descp_marca                    AS marca,
               cv.descp_cliente                  AS cliente,
               vv.descp_vendedor                 AS vendedor,
               ic.fecha_llegada                  AS eta,
               ic.cantidad_total_pares           AS pares,
               ic.monto_neto,
               pe.nombre_evento                  AS evento_precio,
               ic.estado
        FROM intencion_compra ic
        JOIN  marca_v2     mv   ON mv.id_marca       = ic.id_marca
        JOIN  cliente_v2   cv   ON cv.id_cliente     = ic.id_cliente
        JOIN  vendedor_v2  vv   ON vv.id_vendedor    = ic.id_vendedor
        LEFT JOIN tipo_v2  tv   ON tv.id_tipo         = ic.tipo_id
        LEFT JOIN categoria_v2 cv2 ON cv2.id_categoria = ic.categoria_id
        LEFT JOIN precio_evento pe ON pe.id            = ic.precio_evento_id
        WHERE ic.estado != 'PENDIENTE_OPERATIVO'
        ORDER BY ic.fecha_llegada DESC NULLS LAST, ic.numero_registro DESC
    """)


def update_campo_ic(ic_id: int, campo: str, valor) -> bool:
    """Actualiza un campo de una IC editable (PENDIENTE_OPERATIVO o DEVUELTO_ADMIN)."""
    _PERMITIDOS = {
        "tipo_id", "categoria_id", "id_marca", "fecha_llegada",
        "cantidad_total_pares", "precio_evento_id", "nota_pedido", "monto_neto",
    }
    if campo not in _PERMITIDOS:
        return False
    return commit_query(
        f"UPDATE intencion_compra SET {campo} = :v"
        f" WHERE id = :id AND estado IN ('PENDIENTE_OPERATIVO', 'DEVUELTO_ADMIN')",
        {"v": valor, "id": ic_id},
    )


def _snap_ic(conn, ic_id: int) -> dict:
    """Lee snapshot completo de una IC para auditoría forense."""
    row = conn.execute(text("""
        SELECT ic.numero_registro, ic.estado,
               ic.cantidad_total_pares, ic.monto_neto,
               ic.fecha_llegada, ic.nota_pedido,
               mv.descp_marca      AS marca,
               pi2.nombre          AS proveedor,
               cv.descp_cliente    AS cliente,
               vv.descp_vendedor   AS vendedor,
               COALESCE(tv.descp_tipo,      '—') AS tipo,
               COALESCE(cv2.descp_categoria,'—') AS categoria,
               pe.nombre_evento    AS evento_precio
        FROM intencion_compra ic
        JOIN  marca_v2              mv  ON mv.id_marca    = ic.id_marca
        JOIN  proveedor_importacion pi2 ON pi2.id         = ic.id_proveedor
        JOIN  cliente_v2            cv  ON cv.id_cliente  = ic.id_cliente
        JOIN  vendedor_v2           vv  ON vv.id_vendedor = ic.id_vendedor
        LEFT JOIN tipo_v2       tv  ON tv.id_tipo         = ic.tipo_id
        LEFT JOIN categoria_v2  cv2 ON cv2.id_categoria   = ic.categoria_id
        LEFT JOIN precio_evento pe  ON pe.id              = ic.precio_evento_id
        WHERE ic.id = :ic_id
    """), {"ic_id": ic_id}).fetchone()
    if not row:
        return {}
    return {
        "numero_registro": row.numero_registro,
        "estado":          row.estado,
        "marca":           row.marca,
        "proveedor":       row.proveedor,
        "cliente":         row.cliente,
        "vendedor":        row.vendedor,
        "tipo":            row.tipo,
        "categoria":       row.categoria,
        "pares":           row.cantidad_total_pares,
        "monto_neto":      float(row.monto_neto) if row.monto_neto else None,
        "eta":             str(row.fecha_llegada) if row.fecha_llegada else None,
        "evento_precio":   row.evento_precio,
        "nota_pedido":     row.nota_pedido,
    }


def autorizar_ic(ic_id: int) -> tuple[bool, str]:
    """
    Cambia estado a AUTORIZADO. La IC pasa a la bandeja de Digitación.
    Retorna (True, "") en éxito o (False, mensaje_error) en fallo.
    """
    from core.database import DBInspector
    try:
        with engine.begin() as conn:
            snap = _snap_ic(conn, ic_id)
            result = conn.execute(text("""
                UPDATE intencion_compra SET estado = 'AUTORIZADO'
                WHERE id = :id AND estado = 'PENDIENTE_OPERATIVO'
            """), {"id": ic_id})
            if result.rowcount == 0:
                return False, "La IC no está en estado PENDIENTE_OPERATIVO o no existe."
        log_flujo(
            entidad="IC", entidad_id=ic_id,
            nro_registro=snap.get("numero_registro"),
            accion=A.IC_AUTORIZADA,
            estado_antes="PENDIENTE_OPERATIVO", estado_despues="AUTORIZADO",
            snap=snap,
        )
        DBInspector.log(f"[IC] {snap.get('numero_registro')} → AUTORIZADO", "SUCCESS")
        return True, ""
    except Exception as e:
        from core.database import DBInspector
        DBInspector.log(f"[IC] Error autorizando IC {ic_id}: {e}", "ERROR")
        return False, str(e)


def eliminar_ic(ic_id: int) -> bool:
    """Elimina la IC solo si está en PENDIENTE_OPERATIVO."""
    return commit_query(
        "DELETE FROM intencion_compra WHERE id = :id AND estado = 'PENDIENTE_OPERATIVO'",
        {"id": ic_id},
    )


def reutorizar_ic(ic_id: int) -> bool:
    """Re-autoriza una IC devuelta: DEVUELTO_ADMIN → AUTORIZADO."""
    try:
        with engine.begin() as conn:
            snap = _snap_ic(conn, ic_id)
            conn.execute(text("""
                UPDATE intencion_compra SET estado = 'AUTORIZADO'
                WHERE id = :id AND estado = 'DEVUELTO_ADMIN'
            """), {"id": ic_id})
        log_flujo(
            entidad="IC", entidad_id=ic_id,
            nro_registro=snap.get("numero_registro"),
            accion=A.IC_REAUTORIZADA,
            estado_antes="DEVUELTO_ADMIN", estado_despues="AUTORIZADO",
            snap=snap,
        )
        return True
    except Exception:
        return False


def anular_ic(ic_id: int) -> bool:
    """Anula una IC devuelta: DEVUELTO_ADMIN → ANULADO."""
    try:
        with engine.begin() as conn:
            snap = _snap_ic(conn, ic_id)
            conn.execute(text("""
                UPDATE intencion_compra SET estado = 'ANULADO'
                WHERE id = :id AND estado = 'DEVUELTO_ADMIN'
            """), {"id": ic_id})
        log_flujo(
            entidad="IC", entidad_id=ic_id,
            nro_registro=snap.get("numero_registro"),
            accion=A.IC_ANULADA,
            estado_antes="DEVUELTO_ADMIN", estado_despues="ANULADO",
            snap=snap,
        )
        return True
    except Exception:
        return False


def get_ics_devueltas() -> pd.DataFrame:
    """ICs en estado DEVUELTO_ADMIN — bandeja del administrador para revisar."""
    return get_dataframe("""
        SELECT ic.id, ic.numero_registro,
               ic.tipo_id,     COALESCE(tv.descp_tipo,      '—') AS tipo,
               ic.categoria_id,COALESCE(cv2.descp_categoria,'—') AS categoria,
               ic.id_marca,    mv.descp_marca                    AS marca,
               pi2.nombre                                        AS proveedor,
               cv.descp_cliente                                  AS cliente,
               vv.descp_vendedor                                 AS vendedor,
               ic.fecha_llegada,
               ic.cantidad_total_pares AS pares,
               ic.monto_neto,
               ic.precio_evento_id,
               pe.nombre_evento AS evento_precio,
               ic.nota_pedido,
               ic.motivo_devolucion,
               ic.devuelto_at
        FROM intencion_compra ic
        JOIN  marca_v2              mv   ON mv.id_marca       = ic.id_marca
        JOIN  cliente_v2            cv   ON cv.id_cliente     = ic.id_cliente
        JOIN  vendedor_v2           vv   ON vv.id_vendedor    = ic.id_vendedor
        JOIN  proveedor_importacion pi2  ON pi2.id            = ic.id_proveedor
        LEFT JOIN tipo_v2           tv   ON tv.id_tipo         = ic.tipo_id
        LEFT JOIN categoria_v2      cv2  ON cv2.id_categoria   = ic.categoria_id
        LEFT JOIN precio_evento     pe   ON pe.id              = ic.precio_evento_id
        WHERE ic.estado = 'DEVUELTO_ADMIN'
        ORDER BY ic.devuelto_at DESC NULLS LAST, ic.numero_registro ASC
    """)


def get_eventos_precio_cerrados() -> pd.DataFrame:
    """Retorna eventos de precio cerrados disponibles para vincular a una IC."""
    return get_dataframe(
        """SELECT pe.id, pe.nombre_evento, pe.fecha_vigencia_desde,
                  COUNT(pl.id) AS total_skus
           FROM precio_evento pe
           LEFT JOIN precio_lista pl ON pl.evento_id = pe.id
           WHERE pe.estado = 'cerrado'
           GROUP BY pe.id, pe.nombre_evento, pe.fecha_vigencia_desde
           ORDER BY pe.created_at DESC"""
    )


def buscar_cliente(id_cliente: int) -> str | None:
    """Retorna descp_cliente dado un id_cliente, o None si no existe."""
    df = get_dataframe(
        "SELECT descp_cliente FROM cliente_v2 WHERE id_cliente = :id",
        {"id": id_cliente}
    )
    if df.empty:
        return None
    return str(df["descp_cliente"].iloc[0])


# ─────────────────────────────────────────────────────────────────────────────
# NUMERACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def get_next_numero_registro(anio: int | None = None) -> str:
    """
    Genera el próximo IC-YYYY-XXXX consultando el máximo actual en BD.
    Thread-safe a nivel de aplicación (no usa secuencia PostgreSQL).
    """
    if anio is None:
        anio = date.today().year
    df = get_dataframe(
        """
        SELECT COALESCE(
            MAX(CAST(SPLIT_PART(numero_registro, '-', 3) AS INTEGER)), 0
        ) AS ultimo
        FROM intencion_compra
        WHERE numero_registro LIKE :patron
        """,
        {"patron": f"IC-{anio}-%"},
    )
    ultimo = int(df["ultimo"].iloc[0]) if not df.empty else 0
    return f"IC-{anio}-{ultimo + 1:04d}"


# ─────────────────────────────────────────────────────────────────────────────
# LECTURA DE INTENCIONES
# ─────────────────────────────────────────────────────────────────────────────

def get_intenciones(filtros: dict | None = None) -> pd.DataFrame:
    """
    Lista de intenciones con todos los JOINs resueltos.
    Filtros opcionales: estado (str), id_marca (int).
    """
    where_clauses = ["1=1"]
    params: dict = {}

    if filtros:
        if filtros.get("estado") and filtros["estado"] != "TODOS":
            where_clauses.append("ic.estado = :estado")
            params["estado"] = filtros["estado"]
        if filtros.get("id_marca"):
            where_clauses.append("ic.id_marca = :id_marca")
            params["id_marca"] = int(filtros["id_marca"])

    where = " AND ".join(where_clauses)

    return get_dataframe(f"""
        SELECT
            ic.numero_registro,
            ic.id,
            pi2.nombre                  AS proveedor,
            ic.id_cliente,
            cv.descp_cliente            AS cliente,
            vv.descp_vendedor           AS vendedor,
            mv.descp_marca              AS marca,
            pz.descp_plazo              AS plazo,
            ic.cantidad_total_pares     AS pares,
            ic.monto_bruto,
            ic.descuento_1,
            ic.descuento_2,
            ic.descuento_3,
            ic.descuento_4,
            ic.monto_neto,
            ic.fecha_registro,
            ic.fecha_llegada,
            ic.estado,
            ic.nota_pedido,
            ic.observaciones
        FROM intencion_compra ic
        JOIN proveedor_importacion pi2 ON pi2.id         = ic.id_proveedor
        JOIN cliente_v2            cv  ON cv.id_cliente  = ic.id_cliente
        JOIN vendedor_v2           vv  ON vv.id_vendedor = ic.id_vendedor
        JOIN marca_v2              mv  ON mv.id_marca    = ic.id_marca
        LEFT JOIN plazo_v2         pz  ON pz.id_plazo   = ic.id_plazo
        WHERE {where}
        ORDER BY ic.fecha_llegada ASC NULLS LAST, ic.numero_registro ASC
    """, params or None)


def get_dashboard_eta() -> pd.DataFrame:
    """Pares y monto neto agrupados por ETA y marca. Para el dashboard."""
    return get_dataframe("""
        SELECT
            ic.numero_registro,
            ic.fecha_llegada,
            mv.descp_marca              AS marca,
            ic.cantidad_total_pares     AS pares,
            ic.monto_neto               AS neto,
            ic.estado
        FROM intencion_compra ic
        JOIN marca_v2 mv ON mv.id_marca = ic.id_marca
        ORDER BY ic.fecha_llegada ASC NULLS LAST, mv.descp_marca
    """)


def get_dashboard_v2(filtros: dict | None = None) -> pd.DataFrame:
    """Dashboard V2: tabla completa con Tipo, Categoría, Marca, ETA, Pares, Neto, Estado."""
    where_clauses = ["1=1"]
    params: dict = {}

    if filtros:
        if filtros.get("estado") and filtros["estado"] != "TODOS":
            where_clauses.append("ic.estado = :estado")
            params["estado"] = filtros["estado"]
        if filtros.get("id_marca"):
            where_clauses.append("ic.id_marca = :id_marca")
            params["id_marca"] = int(filtros["id_marca"])

    where = " AND ".join(where_clauses)

    return get_dataframe(f"""
        SELECT
            ic.numero_registro,
            COALESCE(tv.descp_tipo, '—')       AS tipo,
            COALESCE(cv2.descp_categoria, '—') AS categoria,
            mv.descp_marca                     AS marca,
            ic.fecha_llegada,
            ic.cantidad_total_pares            AS pares,
            ic.monto_neto                      AS neto,
            ic.estado
        FROM intencion_compra ic
        JOIN  marca_v2    mv   ON mv.id_marca      = ic.id_marca
        LEFT JOIN tipo_v2 tv   ON tv.id_tipo        = ic.tipo_id
        LEFT JOIN categoria_v2 cv2 ON cv2.id_categoria = ic.categoria_id
        WHERE {where}
        ORDER BY ic.fecha_llegada ASC NULLS LAST, ic.numero_registro ASC
    """, params or None)


# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULO Y ESCRITURA
# ─────────────────────────────────────────────────────────────────────────────

def calcular_neto(bruto: float, d1: float, d2: float, d3: float, d4: float) -> float:
    """Descuento en cascada: bruto × (1−d1%) × (1−d2%) × (1−d3%) × (1−d4%)."""
    neto = bruto
    for pct in (d1, d2, d3, d4):
        if pct > 0:
            neto *= (1 - pct / 100)
    return round(neto, 2)


def save_intencion(data: dict) -> tuple[bool, str]:
    """
    Inserta una nueva intención de compra.
    Genera numero_registro automáticamente.
    Retorna (True, numero_registro) si éxito, (False, mensaje_error) si falla.
    """
    numero = get_next_numero_registro()
    bruto  = float(data.get("monto_bruto", 0))
    neto   = calcular_neto(
        bruto,
        float(data.get("descuento_1", 0)),
        float(data.get("descuento_2", 0)),
        float(data.get("descuento_3", 0)),
        float(data.get("descuento_4", 0)),
    )

    params = {
        "numero":                   numero,
        "id_proveedor":             int(data["id_proveedor"]),
        "id_cliente":               int(data["id_cliente"]),
        "id_vendedor":              int(data["id_vendedor"]),
        "id_marca":                 int(data["id_marca"]),
        "id_plazo":                 int(data["id_plazo"]) if data.get("id_plazo") else None,
        "tipo_id":                  int(data["tipo_id"]) if data.get("tipo_id") else None,
        "categoria_id":             int(data["categoria_id"]) if data.get("categoria_id") else None,
        "pares":                    int(data.get("cantidad_total_pares", 0)),
        "bruto":                    bruto,
        "d1":                       float(data.get("descuento_1", 0)),
        "d2":                       float(data.get("descuento_2", 0)),
        "d3":                       float(data.get("descuento_3", 0)),
        "d4":                       float(data.get("descuento_4", 0)),
        "neto":                     neto,
        "fecha_reg":                data["fecha_registro"],
        "fecha_eta":                data.get("fecha_llegada") or None,
        "nota_pedido":              data.get("nota_pedido") or None,
        "obs":                      data.get("observaciones") or None,
        "precio_evento_id":         int(data["precio_evento_id"]) if data.get("precio_evento_id") else None,
        "listado_precio_id":        int(data["listado_precio_id"]) if data.get("listado_precio_id") else None,
        "comision_vendedor_id":     int(data["comision_vendedor_id"]) if data.get("comision_vendedor_id") else None,
        "comision_porcentaje_snap": float(data["comision_porcentaje_snap"]) if data.get("comision_porcentaje_snap") else None,
    }
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO intencion_compra (
                    numero_registro,
                    id_proveedor, id_cliente, id_vendedor, id_marca, id_plazo,
                    tipo_id, categoria_id,
                    cantidad_total_pares,
                    monto_bruto, descuento_1, descuento_2, descuento_3, descuento_4,
                    monto_neto, fecha_registro, fecha_llegada,
                    estado, nota_pedido, observaciones, precio_evento_id,
                    listado_precio_id, comision_vendedor_id, comision_porcentaje_snap
                ) VALUES (
                    :numero,
                    :id_proveedor, :id_cliente, :id_vendedor, :id_marca, :id_plazo,
                    :tipo_id, :categoria_id,
                    :pares,
                    :bruto, :d1, :d2, :d3, :d4,
                    :neto, :fecha_reg, :fecha_eta,
                    'PENDIENTE_OPERATIVO', :nota_pedido, :obs, :precio_evento_id,
                    :listado_precio_id, :comision_vendedor_id, :comision_porcentaje_snap
                ) RETURNING id
            """), params)
            new_id = result.fetchone()[0]

        log_flujo(
            entidad="IC", entidad_id=new_id, nro_registro=numero,
            accion=A.IC_CREADA,
            estado_despues="PENDIENTE_OPERATIVO",
            snap={
                "marca":           data.get("_marca_label"),
                "proveedor":       data.get("_proveedor_label"),
                "cliente":         data.get("_cliente_label"),
                "vendedor":        data.get("_vendedor_label"),
                "pares":           int(data.get("cantidad_total_pares", 0)),
                "monto_bruto":     bruto,
                "monto_neto":      neto,
                "descuento_1":     float(data.get("descuento_1", 0)),
                "descuento_2":     float(data.get("descuento_2", 0)),
                "descuento_3":     float(data.get("descuento_3", 0)),
                "descuento_4":     float(data.get("descuento_4", 0)),
                "eta":             str(data.get("fecha_llegada") or ""),
                "categoria_id":    params["categoria_id"],
                "tipo_id":         params["tipo_id"],
                "precio_evento_id":params["precio_evento_id"],
            },
        )
        return True, numero
    except Exception as e:
        # Loggeo completo para que el operador vea la causa en consola/Streamlit
        msg = f"INSERT intencion_compra falló: {type(e).__name__}: {e}"
        _log.exception(msg)
        try:
            import streamlit as _st
            _st.error(msg)
            _st.expander("📋 Parámetros enviados").write(params)
        except Exception:
            pass
        return False, f"Error en INSERT: {type(e).__name__}: {e}"[:280]


# ─────────────────────────────────────────────────────────────────────────────
# MATRIZ DE NEGOCIACIÓN — Línea → Caso → Listado → Comisión
# ─────────────────────────────────────────────────────────────────────────────

# Tipos canónicos de caso que se asignan a una línea (independiente del evento)
CASOS_CANONICOS = ["NORMAL", "CHINELO", "CARTERAS", "NORMAL_MENOR", "OTRO"]

# Patrón SQL para matching con nombre_caso del evento
_CASO_SQL_FILTER = {
    "NORMAL":       "UPPER(TRIM(pec.nombre_caso)) LIKE '%NORMAL%' AND UPPER(TRIM(pec.nombre_caso)) NOT LIKE '%MENOR%' AND UPPER(TRIM(pec.nombre_caso)) NOT LIKE '%CHINELO%' AND UPPER(TRIM(pec.nombre_caso)) NOT LIKE '%CARTERA%'",
    "CHINELO":      "UPPER(TRIM(pec.nombre_caso)) LIKE '%CHINELO%'",
    "CARTERAS":     "UPPER(TRIM(pec.nombre_caso)) LIKE '%CARTERA%'",
    "NORMAL_MENOR": "UPPER(TRIM(pec.nombre_caso)) LIKE '%NORMAL%' AND UPPER(TRIM(pec.nombre_caso)) LIKE '%MENOR%'",
    "OTRO":         "1=1",
}


def get_lineas_con_caso(proveedor_id: int | None = None) -> pd.DataFrame:
    """
    Lista de lineas (Pilar 1) con sus 3 FKs canonicas:
      - marca_id  (FK marca_v2)
      - genero_id (FK genero)
      - caso_id   (FK caso_precio_biblioteca)
    + sus descripciones para visualizacion. Estilo/Tipo viven en linea_referencia.
    """
    where = ["l.activo = true"]
    params: dict = {}
    if proveedor_id:
        where.append("l.proveedor_id = :pid")
        params["pid"] = proveedor_id
    return get_dataframe(f"""
        SELECT l.id, l.codigo_proveedor, l.descripcion,
               l.marca_id,
               COALESCE(mv.descp_marca, '')   AS marca,
               l.genero_id,
               COALESCE(g.descripcion, '')    AS descp_genero,
               l.caso_id,
               COALESCE(cpb.nombre_caso, '')  AS caso_nombre
        FROM linea l
        LEFT JOIN marca_v2 mv               ON mv.id_marca = l.marca_id
        LEFT JOIN genero   g                ON g.id        = l.genero_id
        LEFT JOIN caso_precio_biblioteca cpb ON cpb.id     = l.caso_id
        WHERE {' AND '.join(where)}
        ORDER BY l.codigo_proveedor
    """, params or None)


def update_linea_clasificacion(linea_id: int, *,
                                marca_id: int | None = None,
                                genero_id: int | None = None,
                                caso_id: int | None = None,
                                _campos: set | None = None) -> bool:
    """
    Actualiza las 3 FKs canonicas de UNA linea (Pilar 1).
    Solo escribe los campos pasados en `_campos` (set de nombres).
    Si _campos es None, escribe todos los campos no-None.
    """
    permitidos = {"marca_id", "genero_id", "caso_id"}
    valores = {"marca_id": marca_id, "genero_id": genero_id, "caso_id": caso_id}
    if _campos is None:
        _campos = {k for k, v in valores.items() if v is not None}
    campos = _campos & permitidos
    if not campos:
        return False
    sets = ", ".join(f"{c} = :{c}" for c in campos)
    params = {c: valores[c] for c in campos}
    params["id"] = linea_id
    return commit_query(f"UPDATE linea SET {sets} WHERE id = :id", params)


def update_linea_caso_detalle(linea_id: int, genero: str | None, *_args) -> bool:
    """DEPRECATED. Wrapper compatible. Traduce genero (texto) a genero_id y delega."""
    if genero is None or str(genero).strip() == "":
        gid = None
    else:
        df = get_dataframe(
            "SELECT id FROM genero WHERE descripcion = :g OR codigo = :g LIMIT 1",
            {"g": str(genero).strip()},
        )
        gid = int(df["id"].iloc[0]) if df is not None and not df.empty else None
    return update_linea_clasificacion(linea_id, genero_id=gid, _campos={"genero_id"})


def get_caso_por_linea(linea_id: int) -> str | None:
    """Retorna el nombre del caso asignado a la linea, o None."""
    df = get_dataframe(
        """SELECT cpb.nombre_caso
           FROM linea l
           JOIN caso_precio_biblioteca cpb ON cpb.id = l.caso_id
           WHERE l.id = :id AND l.activo = true""",
        {"id": linea_id},
    )
    if df is None or df.empty:
        return None
    v = df["nombre_caso"].iloc[0]
    return str(v) if v and str(v) not in ("None", "nan", "") else None


def get_listados_para_caso(evento_id: int, caso_nombre: str) -> list[dict]:
    """
    Retorna listados disponibles (LPN/LPC03/LPC04) para el caso en el evento dado.
    Excluye LPC02. Verifica que existan filas no-nulas en precio_lista.
    """
    filtro = _CASO_SQL_FILTER.get(caso_nombre.upper(), "1=1")
    resultado = []

    for col, lp_id, label in [
        ("lpn",   1, "LPN — Precio neto"),
        ("lpc03", 3, "LPC03 — LPN + 12%"),
        ("lpc04", 4, "LPC04 — LPN + 20%"),
    ]:
        df = get_dataframe(f"""
            SELECT COUNT(*) AS n
            FROM precio_lista pl
            JOIN precio_evento_caso pec ON pec.id = pl.caso_id
            WHERE pl.evento_id = :eid
              AND {filtro}
              AND pl.{col} IS NOT NULL AND pl.{col} > 0
        """, {"eid": evento_id})
        if df is not None and not df.empty and int(df["n"].iloc[0]) > 0:
            resultado.append({"id": lp_id, "nombre": label})

    return resultado


def get_comisiones() -> pd.DataFrame:
    """Lista todas las comisiones disponibles en comision_v2."""
    return get_dataframe(
        "SELECT id_comision AS id, descp_comision AS nombre, valor_comision AS porcentaje "
        "FROM comision_v2 ORDER BY valor_comision"
    )


def get_lineas_filtradas(proveedor_id: int, marca: str | None = None,
                          caso: str | None = None, genero: str | None = None,
                          **_kwargs) -> pd.DataFrame:
    """
    Lista de TODAS las lineas activas del proveedor con filtros opcionales.
    Para Admin Lineas. Fuente unica: tabla linea.
    """
    where = ["l.activo = true", "l.proveedor_id = :pid"]
    params: dict = {"pid": proveedor_id}

    if marca and marca != "Todas":
        where.append("mv.descp_marca = :marca")
        params["marca"] = marca
    if caso == "— Sin caso —":
        where.append("l.caso_id IS NULL")
    elif caso and caso != "Todos":
        where.append("cpb.nombre_caso = :caso")
        params["caso"] = caso
    if genero == "— Vacío —":
        where.append("l.genero_id IS NULL")
    elif genero and genero != "Todos":
        where.append("g.descripcion = :genero")
        params["genero"] = genero

    return get_dataframe(f"""
        SELECT l.id, l.codigo_proveedor, l.descripcion,
               l.marca_id,
               COALESCE(mv.descp_marca, '')  AS marca,
               l.genero_id,
               COALESCE(g.descripcion, '')   AS descp_genero,
               l.caso_id,
               COALESCE(cpb.nombre_caso, '') AS caso_nombre
        FROM linea l
        LEFT JOIN marca_v2 mv                ON mv.id_marca = l.marca_id
        LEFT JOIN genero   g                 ON g.id        = l.genero_id
        LEFT JOIN caso_precio_biblioteca cpb ON cpb.id      = l.caso_id
        WHERE {' AND '.join(where)}
        ORDER BY l.codigo_proveedor
    """, params)


def get_valores_filtro_lineas(proveedor_id: int, campo: str) -> list:
    """
    Valores distintos no-nulos de un campo conceptual desde la tabla linea.
    Campos permitidos: 'marca', 'caso_nombre', 'descp_genero'.
    """
    _MAPA = {
        "marca": "SELECT DISTINCT mv.descp_marca AS v FROM linea l "
                 "JOIN marca_v2 mv ON mv.id_marca = l.marca_id "
                 "WHERE l.proveedor_id = :pid AND l.activo = true "
                 "AND mv.descp_marca IS NOT NULL ORDER BY v",
        "caso_nombre": "SELECT DISTINCT cpb.nombre_caso AS v FROM linea l "
                       "JOIN caso_precio_biblioteca cpb ON cpb.id = l.caso_id "
                       "WHERE l.proveedor_id = :pid AND l.activo = true "
                       "AND cpb.nombre_caso IS NOT NULL ORDER BY v",
        "descp_genero": "SELECT DISTINCT g.descripcion AS v FROM linea l "
                        "JOIN genero g ON g.id = l.genero_id "
                        "WHERE l.proveedor_id = :pid AND l.activo = true "
                        "AND g.descripcion IS NOT NULL ORDER BY v",
    }
    sql = _MAPA.get(campo)
    if sql is None:
        return []
    df = get_dataframe(sql, {"pid": proveedor_id})
    return [] if df is None or df.empty else df["v"].tolist()


def actualizar_lineas_por_lote(linea_ids: list, campo: str,
                                valor) -> tuple[bool, int]:
    """
    Actualiza un campo escalar en multiples lineas (tabla linea).
    Campos permitidos (todos FK numericas): marca_id, genero_id, caso_id.
    """
    _PERMITIDOS = {"marca_id", "genero_id", "caso_id"}
    if campo not in _PERMITIDOS or not linea_ids:
        return False, 0
    ids_str = ", ".join(str(int(i)) for i in linea_ids)
    val = None
    if valor is not None and str(valor) != "":
        try:
            val = int(valor)
        except (ValueError, TypeError):
            return False, 0
    ok = commit_query(
        f"UPDATE linea SET {campo} = :val WHERE id IN ({ids_str})",
        {"val": val},
    )
    return ok, len(linea_ids) if ok else 0


def guardar_negociacion_ic(ic_id: int, listado_precio_id: int | None,
                           comision_id: int | None,
                           comision_pct: float | None) -> bool:
    """Graba el snapshot de listado + comisión en la IC (campos nuevos)."""
    return commit_query(
        """UPDATE intencion_compra
           SET listado_precio_id        = :lp,
               comision_vendedor_id     = :com,
               comision_porcentaje_snap = :pct
           WHERE id = :id
             AND estado IN ('PENDIENTE_OPERATIVO', 'DEVUELTO_ADMIN')""",
        {"lp": listado_precio_id, "com": comision_id, "pct": comision_pct, "id": ic_id},
    )


# ─────────────────────────────────────────────────────────────────────────────
# PREVENTA — catálogo de stock y creación de IC
# ─────────────────────────────────────────────────────────────────────────────

def get_pps_para_preventa() -> pd.DataFrame:
    """PPs en ABIERTO/ENVIADO con al menos un artículo en detalle."""
    return get_dataframe("""
        SELECT
            pp.id,
            pp.numero_registro,
            COALESCE(pp.numero_proforma, '—')         AS proforma,
            COALESCE(pi2.nombre, '—')                 AS proveedor,
            STRING_AGG(DISTINCT mv.descp_marca, ' / '
                       ORDER BY mv.descp_marca)        AS marcas,
            SUM(ppd.cantidad_pares)                    AS pares_total,
            pp.fecha_arribo_estimada                   AS eta
        FROM pedido_proveedor pp
        LEFT JOIN proveedor_importacion pi2 ON pi2.id = pp.proveedor_importacion_id
        JOIN pedido_proveedor_detalle ppd ON ppd.pedido_proveedor_id = pp.id
        LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
        WHERE pp.estado IN ('ABIERTO', 'ENVIADO')
          AND ppd.cantidad_pares > 0
        GROUP BY pp.id, pp.numero_registro, pp.numero_proforma,
                 pi2.nombre, pp.fecha_arribo_estimada
        ORDER BY pp.fecha_arribo_estimada ASC NULLS LAST, pp.numero_registro
    """)


def get_marcas_del_pp(pp_id: int) -> list[str]:
    """Lista de marcas presentes en el detalle del PP."""
    df = get_dataframe("""
        SELECT DISTINCT mv.descp_marca
        FROM pedido_proveedor_detalle ppd
        JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
        WHERE ppd.pedido_proveedor_id = :pp_id
          AND mv.descp_marca IS NOT NULL
        ORDER BY mv.descp_marca
    """, {"pp_id": pp_id})
    return [] if df.empty else df["descp_marca"].tolist()


def cargar_stock_preventa_pp(pp_id: int,
                              filtro_marca: str = "Todas",
                              buscar: str = "") -> list[dict]:
    """
    Stock del PP para el catálogo de preventa.
    Cruza con precio_lista via LATERAL JOIN (misma lógica que get_precios_stock_pp).
    Retorna list[dict] con campos listos para render_miniatura.
    """
    buscar_like = f"%{buscar.lower()}%" if buscar.strip() else "%"
    marca_filtro = None if filtro_marca == "Todas" else filtro_marca
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    ppd.id                                                        AS det_id,
                    ppd.pedido_proveedor_id                                       AS pp_id,
                    ppd.id_marca,
                    COALESCE(mv.descp_marca, '—')                                 AS marca,
                    ppd.linea,
                    ppd.referencia,
                    COALESCE(ppd.nombre, '')                                      AS nombre,
                    ppd.style_code,
                    ppd.material_code,
                    COALESCE(ppd.descp_material, '')                              AS mat_desc,
                    ppd.color_code,
                    COALESCE(ppd.descp_color, '')                                 AS col_desc,
                    ppd.grada,
                    ppd.cantidad_cajas,
                    ppd.cantidad_pares,
                    CASE WHEN ppd.cantidad_cajas > 0
                         THEN ppd.cantidad_pares / ppd.cantidad_cajas
                         ELSE 0 END                                               AS pares_por_caja,
                    ppd.grades_json::text                                         AS grades_json,
                    pp.proveedor_importacion_id,
                    ic.precio_evento_id                                           AS evento_id,
                    pl.lpn,
                    pl.lpc03,
                    pl.lpc04,
                    pl.nombre_caso_aplicado                                       AS caso
                FROM pedido_proveedor_detalle ppd
                JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
                LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
                LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
                LEFT JOIN linea l    ON l.codigo_proveedor::text = ppd.linea
                LEFT JOIN material m ON m.codigo_proveedor::text = ppd.material_code
                LEFT JOIN LATERAL (
                    SELECT lpn, lpc03, lpc04, nombre_caso_aplicado
                    FROM precio_lista
                    WHERE evento_id          = COALESCE(ic.precio_evento_id,
                              (SELECT id FROM precio_evento
                               WHERE estado = 'cerrado'
                               ORDER BY created_at DESC LIMIT 1))
                      AND linea_id        = l.id
                      AND material_id = m.id
                    LIMIT 1
                ) pl ON true
                WHERE ppd.pedido_proveedor_id = :pp_id
                  AND ppd.cantidad_pares > 0
                  AND (:marca IS NULL OR COALESCE(mv.descp_marca, '—') = :marca)
                  AND (
                      LOWER(COALESCE(ppd.linea, ''))          LIKE :buscar
                      OR LOWER(COALESCE(ppd.referencia, ''))  LIKE :buscar
                      OR LOWER(COALESCE(ppd.descp_material,'')) LIKE :buscar
                      OR LOWER(COALESCE(ppd.style_code, ''))  LIKE :buscar
                      OR LOWER(COALESCE(ppd.nombre, ''))      LIKE :buscar
                  )
                ORDER BY ppd.id
            """), {
                "pp_id":  pp_id,
                "marca":  marca_filtro,
                "buscar": buscar_like,
            }).fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception as e:
        from core.database import DBInspector
        DBInspector.log(f"[PREVENTA] cargar_stock_preventa_pp: {e}", "ERROR")
        return []


def crear_ic_preventa(
    carrito: dict,
    id_cliente: int,
    id_vendedor: int,
    tipo_id: int,
    fecha_eta,
    nota: str,
) -> tuple[bool, list[str]]:
    """
    Crea una IC COMPRA PREVIA (categoria_id=2) por cada PP en el carrito.
    Retorna (True, [numeros_creados]) o (False, [msg_error]).
    """
    # Agrupar por PP
    por_pp: dict[int, list[dict]] = {}
    for item in carrito.values():
        pp_id = item["pp_id"]
        if pp_id not in por_pp:
            por_pp[pp_id] = []
        por_pp[pp_id].append(item)

    if not por_pp:
        return False, ["El carrito está vacío."]

    # Pre-generar números de registro (uno por PP)
    anio = date.today().year
    df_max = get_dataframe(
        "SELECT COALESCE(MAX(CAST(SPLIT_PART(numero_registro, '-', 3) AS INTEGER)), 0) AS ultimo "
        "FROM intencion_compra WHERE numero_registro LIKE :pat",
        {"pat": f"IC-{anio}-%"},
    )
    ultimo = int(df_max["ultimo"].iloc[0]) if not df_max.empty else 0
    pp_ids_ordered = list(por_pp.keys())
    numeros = [f"IC-{anio}-{ultimo + i + 1:04d}" for i in range(len(pp_ids_ordered))]

    try:
        creados: list[str] = []
        with engine.begin() as conn:
            for i, pp_id in enumerate(pp_ids_ordered):
                items   = por_pp[pp_id]
                numero  = numeros[i]
                total_pares = sum(it["pares"] for it in items)
                total_monto = round(
                    sum(it["pares"] * (it.get("lpn") or 0) for it in items), 2
                )
                id_prov  = items[0]["proveedor_importacion_id"]
                id_marca = items[0]["id_marca"]
                ev_id    = items[0].get("evento_id") or None

                result = conn.execute(text("""
                    INSERT INTO intencion_compra (
                        numero_registro,
                        id_proveedor, id_cliente, id_vendedor, id_marca,
                        tipo_id, categoria_id,
                        cantidad_total_pares, monto_neto,
                        fecha_registro, fecha_llegada,
                        estado, nota_pedido, precio_evento_id
                    ) VALUES (
                        :numero,
                        :id_prov, :id_cli, :id_vend, :id_marc,
                        :tipo_id, 2,
                        :pares, :monto,
                        CURRENT_DATE, :eta,
                        'PENDIENTE_OPERATIVO', :nota, :ev_id
                    ) RETURNING id
                """), {
                    "numero":   numero,
                    "id_prov":  int(id_prov) if id_prov else None,
                    "id_cli":   int(id_cliente),
                    "id_vend":  int(id_vendedor),
                    "id_marc":  int(id_marca) if id_marca else None,
                    "tipo_id":  int(tipo_id) if tipo_id else None,
                    "pares":    total_pares,
                    "monto":    total_monto,
                    "eta":      fecha_eta or None,
                    "nota":     nota or f"PREVENTA · PP-{pp_id}",
                    "ev_id":    int(ev_id) if ev_id else None,
                })
                new_id = result.fetchone()[0]
                creados.append(numero)

                log_flujo(
                    entidad="IC", entidad_id=new_id,
                    nro_registro=numero,
                    accion=A.IC_CREADA,
                    estado_despues="PENDIENTE_OPERATIVO",
                    snap={
                        "origen":      "PREVENTA",
                        "pp_origen_id": pp_id,
                        "pares":        total_pares,
                        "monto_neto":   total_monto,
                        "n_articulos":  len(items),
                    },
                )

        return True, creados
    except Exception as e:
        from core.database import DBInspector
        DBInspector.log(f"[PREVENTA] crear_ic_preventa: {e}", "ERROR")
        return False, [str(e)]
