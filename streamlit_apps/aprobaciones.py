#!/usr/bin/env python3
"""
Módulo de Aprobación de Pedidos RIMEC Web
Permite al administrador aprobar o rechazar pedidos generados desde rimec-web
"""
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Dict, Any, Optional

# Cargar variables de entorno
load_dotenv()

# Configuración de página
st.set_page_config(
    page_title="Aprobación de Pedidos",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e3a8a;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #64748b;
        margin-bottom: 2rem;
    }
    .pedido-card {
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        background-color: #f8fafc;
    }
    .factura-card {
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background-color: white;
    }
    .item-row {
        border-bottom: 1px solid #e2e8f0;
        padding: 0.75rem 0;
    }
    .badge-pendiente {
        background-color: #fef3c7;
        color: #92400e;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.875rem;
    }
    .badge-aprobado {
        background-color: #d1fae5;
        color: #065f46;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.875rem;
    }
    .badge-rechazado {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.875rem;
    }
</style>
""", unsafe_allow_html=True)


def get_db_connection():
    """Obtiene conexión a la base de datos"""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        st.error("❌ DATABASE_URL no configurada en .env")
        st.stop()
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)


def cargar_pedidos() -> List[Dict[str, Any]]:
    """Carga todos los pedidos con información de cliente y vendedor"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.id,
            p.nro_pedido,
            p.created_at,
            p.vendedor_id,
            p.cliente_id,
            p.total_monto,
            p.total_pares,
            p.estado,
            p.plazo_id,
            p.lista_precio_id,
            p.descuento_1,
            p.descuento_2,
            p.descuento_3,
            p.descuento_4,
            p.fecha_aprobacion,
            p.fecha_rechazo,
            p.motivo_rechazo,
            c.descp_cliente AS cliente_nombre,
            v.descp_usuario AS vendedor_nombre
        FROM pedido_venta_rimec p
        LEFT JOIN cliente_v2 c ON p.cliente_id = c.id_cliente
        LEFT JOIN usuario_v2 v ON p.vendedor_id = v.id_usuario
        ORDER BY p.id DESC
        LIMIT 50
    """)

    pedidos = cur.fetchall()
    conn.close()

    return [dict(p) for p in pedidos]


def cargar_facturas(pedido_id: int) -> List[Dict[str, Any]]:
    """Carga facturas internas de un pedido"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            fi.id,
            fi.nro_factura,
            fi.pp_id,
            fi.marca,
            fi.caso,
            fi.total_pares,
            fi.total_monto,
            fi.estado,
            fi.lista_precio_id,
            fi.descuento_1,
            fi.descuento_2,
            fi.descuento_3,
            fi.descuento_4,
            pp.numero_registro AS nro_pp,
            pp.fecha_arribo_estimada,
            qa.descripcion AS quincena_llegada
        FROM factura_interna fi
        LEFT JOIN pedido_proveedor pp ON fi.pp_id = pp.id
        LEFT JOIN quincena_arribo qa ON qa.id = pp.quincena_arribo_id
        WHERE fi.pedido_id = %s
        ORDER BY fi.pp_id, fi.marca, fi.caso
    """, (pedido_id,))

    facturas = cur.fetchall()
    conn.close()

    return [dict(f) for f in facturas]


def cargar_items(factura_id: int) -> List[Dict[str, Any]]:
    """Carga items de una factura interna"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            pares,
            cajas,
            precio_neto,
            subtotal,
            linea_snapshot
        FROM factura_interna_detalle
        WHERE factura_id = %s
        ORDER BY id
    """, (factura_id,))

    items = cur.fetchall()
    conn.close()

    # Parsear snapshot
    result = []
    for item in items:
        item_dict = dict(item)

        # Parsear linea_snapshot
        import json
        snapshot = {}
        if item_dict.get('linea_snapshot'):
            try:
                if isinstance(item_dict['linea_snapshot'], str):
                    snapshot = json.loads(item_dict['linea_snapshot'])
                else:
                    snapshot = item_dict['linea_snapshot']
            except:
                pass

        item_dict['linea_codigo'] = snapshot.get('linea_codigo') or snapshot.get('linea') or '?'
        item_dict['ref_codigo'] = snapshot.get('ref_codigo') or snapshot.get('referencia') or '?'
        item_dict['color_nombre'] = snapshot.get('color_nombre') or snapshot.get('color') or ''
        item_dict['material_nombre'] = snapshot.get('material_nombre') or snapshot.get('material') or ''
        item_dict['gradas_fmt'] = snapshot.get('gradas_fmt') or ''
        item_dict['imagen_url'] = snapshot.get('imagen_url') or ''

        result.append(item_dict)

    return result


def aprobar_pedido(pedido_id: int, admin_id: int = 1):
    """Aprueba un pedido usando la función RPC"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT aprobar_pedido(%s, %s)", (pedido_id, admin_id))
        result = cur.fetchone()
        conn.commit()
        conn.close()
        return result[0] if result else {'success': True}
    except Exception as e:
        conn.rollback()
        conn.close()
        return {'success': False, 'error': str(e)}


def rechazar_pedido(pedido_id: int, admin_id: int = 1, motivo: Optional[str] = None):
    """Rechaza un pedido usando la función RPC"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT rechazar_pedido(%s, %s, %s)", (pedido_id, admin_id, motivo))
        result = cur.fetchone()
        conn.commit()
        conn.close()
        return result[0] if result else {'success': True}
    except Exception as e:
        conn.rollback()
        conn.close()
        return {'success': False, 'error': str(e)}


def mapear_estado(estado: Optional[str]) -> str:
    """Mapea el estado de la BD a un formato legible"""
    if not estado:
        return "PENDIENTE"

    upper = estado.upper()
    if "APROBADO" in upper or "CONFIRMADO" in upper:
        return "APROBADO"
    elif "RECHAZADO" in upper or "CANCELADO" in upper:
        return "RECHAZADO"
    else:
        return "PENDIENTE"


def main():
    # Header
    st.markdown('<div class="main-header">✅ Aprobación de Pedidos RIMEC Web</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Control centralizado de pedidos · Director</div>', unsafe_allow_html=True)

    # Sidebar - Filtros
    st.sidebar.title("🎯 Filtros")
    filtro_estado = st.sidebar.selectbox(
        "Estado",
        ["TODOS", "PENDIENTE", "APROBADO", "RECHAZADO"],
        index=1  # Default: PENDIENTE
    )

    # Cargar pedidos
    with st.spinner("Cargando pedidos..."):
        pedidos = cargar_pedidos()

    # Filtrar pedidos
    if filtro_estado != "TODOS":
        pedidos = [p for p in pedidos if mapear_estado(p['estado']) == filtro_estado]

    # Métricas
    total = len([p for p in cargar_pedidos()])
    pendientes = len([p for p in cargar_pedidos() if mapear_estado(p['estado']) == "PENDIENTE"])
    aprobados = len([p for p in cargar_pedidos() if mapear_estado(p['estado']) == "APROBADO"])
    rechazados = len([p for p in cargar_pedidos() if mapear_estado(p['estado']) == "RECHAZADO"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Pedidos", total)
    with col2:
        st.metric("⏳ Pendientes", pendientes)
    with col3:
        st.metric("✅ Aprobados", aprobados)
    with col4:
        st.metric("❌ Rechazados", rechazados)

    st.divider()

    # Lista de pedidos
    if not pedidos:
        st.info(f"📭 No hay pedidos con el filtro: **{filtro_estado}**")
        return

    st.markdown(f"### 📋 {len(pedidos)} pedido(s) encontrado(s)")

    for pedido in pedidos:
        estado_display = mapear_estado(pedido['estado'])

        # Badge de estado
        if estado_display == "PENDIENTE":
            badge_class = "badge-pendiente"
            badge_icon = "⏳"
        elif estado_display == "APROBADO":
            badge_class = "badge-aprobado"
            badge_icon = "✅"
        else:
            badge_class = "badge-rechazado"
            badge_icon = "❌"

        # Expander para cada pedido
        with st.expander(
            f"{badge_icon} **{pedido['nro_pedido']}** · {pedido['cliente_nombre'] or f\"Cliente {pedido['cliente_id']}\"} · {pedido['total_pares']} pares · Gs. {pedido['total_monto']:,}",
            expanded=estado_display == "PENDIENTE"
        ):
            # Revisión del Pedido
            st.markdown("#### 📄 Revisión del Pedido")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"**Cliente:** {pedido['cliente_nombre'] or f\"Cliente {pedido['cliente_id']}\"}")
            with col2:
                st.markdown(f"**Lista:** LP{pedido['lista_precio_id'] or 1}")
            with col3:
                st.markdown(f"**Descuentos:** {pedido['descuento_1'] or 0}% / {pedido['descuento_2'] or 0}% / {pedido['descuento_3'] or 0}% / {pedido['descuento_4'] or 0}%")
            with col4:
                st.markdown(f"**Vendedor:** {pedido['vendedor_nombre'] or f\"Vendedor {pedido['vendedor_id']}\"}")

            col5, col6 = st.columns(2)
            with col5:
                st.markdown(f"**Plazo:** Plazo {pedido['plazo_id'] or 'EFECTIVO'}")
            with col6:
                fecha_str = pedido['created_at'].strftime("%d/%m/%Y %H:%M") if pedido['created_at'] else "-"
                st.markdown(f"**Fecha:** {fecha_str}")

            st.divider()

            # Cargar facturas
            facturas = cargar_facturas(pedido['id'])

            if not facturas:
                st.warning("⚠️ No hay facturas asociadas a este pedido")
            else:
                st.markdown(f"#### 📦 Facturas ({len(facturas)})")

                for factura in facturas:
                    st.markdown(f"##### 🔸 {factura['marca']} · Caso: {factura['caso']}")
                    st.caption(f"{factura['nro_pp'] or f\"PP-{factura['pp_id']}\"} · {factura['total_pares']} pares · Gs. {factura['total_monto']:,}")

                    # Cable de acero: mostrar quincena (dato duro) en lugar de ETA (variable)
                    if factura.get('quincena_llegada'):
                        st.caption(f"📦 {factura['quincena_llegada']}")
                    elif factura.get('fecha_arribo_estimada'):
                        st.caption(f"📅 Flt prevista: {factura['fecha_arribo_estimada']} (sin quincena asignada)")

                    # Lista de precios y descuentos
                    st.markdown("**Configuración de precios:**")
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.text(f"Lista: LP{factura['lista_precio_id'] or 1}")
                    with col2:
                        st.text(f"Desc 1: {factura['descuento_1'] or 0}%")
                    with col3:
                        st.text(f"Desc 2: {factura['descuento_2'] or 0}%")
                    with col4:
                        st.text(f"Desc 3: {factura['descuento_3'] or 0}%")
                    with col5:
                        st.text(f"Desc 4: {factura['descuento_4'] or 0}%")

                    # Items
                    items = cargar_items(factura['id'])

                    if items:
                        st.markdown("**Items:**")
                        for item in items:
                            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                            with col1:
                                st.text(f"L{item['linea_codigo']} · R{item['ref_codigo']}")
                                st.caption(f"{item['color_nombre']} {item['material_nombre']}".strip())
                            with col2:
                                if item['gradas_fmt']:
                                    st.caption(item['gradas_fmt'])
                            with col3:
                                st.text(f"{item['cajas']} caj · {item['pares']} p")
                            with col4:
                                st.text(f"Gs. {item['subtotal']:,}")

                    st.markdown("---")

            # Botones de acción
            if estado_display == "PENDIENTE":
                st.markdown("#### 🎯 Acciones")
                col1, col2, col3 = st.columns([1, 1, 4])

                with col1:
                    if st.button("✅ Aprobar", key=f"aprobar_{pedido['id']}", type="primary"):
                        result = aprobar_pedido(pedido['id'])
                        if isinstance(result, dict) and result.get('success'):
                            st.success(f"✅ Pedido {pedido['nro_pedido']} aprobado exitosamente")
                            st.rerun()
                        else:
                            st.error(f"❌ Error al aprobar: {result.get('error', 'Error desconocido')}")

                with col2:
                    if st.button("❌ Rechazar", key=f"rechazar_{pedido['id']}"  , type="secondary"):
                        motivo = st.text_input("Motivo del rechazo (opcional):", key=f"motivo_{pedido['id']}")
                        if st.button("Confirmar rechazo", key=f"confirmar_rechazo_{pedido['id']}"):
                            result = rechazar_pedido(pedido['id'], motivo=motivo if motivo else None)
                            if isinstance(result, dict) and result.get('success'):
                                st.success(f"❌ Pedido {pedido['nro_pedido']} rechazado")
                                st.rerun()
                            else:
                                st.error(f"❌ Error al rechazar: {result.get('error', 'Error desconocido')}")

            elif estado_display == "APROBADO":
                st.success(f"✅ Aprobado el {pedido['fecha_aprobacion'].strftime('%d/%m/%Y %H:%M') if pedido['fecha_aprobacion'] else '-'}")

            elif estado_display == "RECHAZADO":
                st.error(f"❌ Rechazado el {pedido['fecha_rechazo'].strftime('%d/%m/%Y %H:%M') if pedido['fecha_rechazo'] else '-'}")
                if pedido['motivo_rechazo']:
                    st.caption(f"**Motivo:** {pedido['motivo_rechazo']}")


if __name__ == "__main__":
    main()
