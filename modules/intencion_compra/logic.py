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

import streamlit as st
import pandas as pd
from datetime import date
from core.database import get_dataframe, commit_query


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

    ok = commit_query("""
        INSERT INTO intencion_compra (
            numero_registro,
            id_proveedor, id_cliente, id_vendedor, id_marca, id_plazo,
            cantidad_total_pares,
            monto_bruto, descuento_1, descuento_2, descuento_3, descuento_4,
            monto_neto, fecha_registro, fecha_llegada,
            estado, nota_pedido, observaciones
        ) VALUES (
            :numero,
            :id_proveedor, :id_cliente, :id_vendedor, :id_marca, :id_plazo,
            :pares,
            :bruto, :d1, :d2, :d3, :d4,
            :neto, :fecha_reg, :fecha_eta,
            'PENDIENTE_OPERATIVO', :nota_pedido, :obs
        )
    """, {
        "numero":       numero,
        "id_proveedor": int(data["id_proveedor"]),
        "id_cliente":   int(data["id_cliente"]),
        "id_vendedor":  int(data["id_vendedor"]),
        "id_marca":     int(data["id_marca"]),
        "id_plazo":     int(data["id_plazo"]) if data.get("id_plazo") else None,
        "pares":        int(data.get("cantidad_total_pares", 0)),
        "bruto":        bruto,
        "d1":           float(data.get("descuento_1", 0)),
        "d2":           float(data.get("descuento_2", 0)),
        "d3":           float(data.get("descuento_3", 0)),
        "d4":           float(data.get("descuento_4", 0)),
        "neto":         neto,
        "fecha_reg":    data["fecha_registro"],
        "fecha_eta":    data.get("fecha_llegada") or None,
        "nota_pedido":  data.get("nota_pedido") or None,
        "obs":          data.get("observaciones") or None,
    })
    return (ok, numero) if ok else (False, "Error en INSERT. Verificar BD.")
