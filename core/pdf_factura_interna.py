"""
SISTEMA: RIMEC Business Intelligence - NEXUS CORE
MÓDULO: core/pdf_factura_interna.py
VERSION: 1.0.0 (GENERADOR DE PDF DE FACTURAS INTERNAS)
AUTOR: Héctor & Claude AI
DESCRIPCIÓN: Lógica específica para generar PDFs de Facturas Internas.
             Orquesta la obtención de datos desde DB y la generación del PDF.

ARQUITECTURA:
    Pedido Venta RIMEC (ID)
         ↓
    [obtener_datos_factura_interna()]
         ↓
    Context completo con:
      - Datos del pedido (cliente, vendedor, plazo, lista)
      - Múltiples facturas (PP × Marca × Caso)
      - Items detallados (SKU, gradas, precios, imágenes)
      - Descuentos y totales
         ↓
    PDFEngine.generate()
         ↓
    PDF bytes

USO:
    from core.pdf_factura_interna import generar_pdf_factura_interna

    pdf_bytes = generar_pdf_factura_interna(pedido_id=123)
"""

import json
from typing import Dict, List, Optional
from decimal import Decimal
from core.database import get_dataframe
from core.pdf_engine import PDFEngine
from core.settings import settings


def _formatear_gradas(gradas_dict: dict) -> str:
    """
    Formatea el diccionario de gradas en string legible.

    Args:
        gradas_dict: {"35": 2, "36": 3, "37": 1}

    Returns:
        "35:2 · 36:3 · 37:1"
    """
    if not gradas_dict:
        return "N/A"

    try:
        # Ordenar por número de grada
        sorted_gradas = sorted(gradas_dict.items(), key=lambda x: float(x[0]))
        return " · ".join([f"{num}:{cant}" for num, cant in sorted_gradas])
    except:
        return str(gradas_dict)


def _obtener_metadata_pedido(pedido_id: int) -> Optional[Dict]:
    """
    Obtiene metadatos del pedido (cliente, vendedor, plazo, lista).

    Args:
        pedido_id: ID del pedido_venta_rimec

    Returns:
        Dict con metadatos o None si no existe
    """
    query = """
        SELECT
            pvr.id,
            pvr.nro_pedido,
            pvr.cliente_id,
            c.id_cliente as cliente_codigo,
            c.descp_cliente as cliente_nombre,
            pvr.vendedor_id,
            v.descp_usuario as vendedor_nombre,
            pvr.lista_precio_id,
            'Lista ' || CAST(pvr.lista_precio_id AS TEXT) as lista_nombre,
            pvr.plazo_id,
            pl.descp_plazo as plazo_nombre,
            pvr.estado,
            pvr.created_at as fecha_creacion
        FROM public.pedido_venta_rimec pvr
        LEFT JOIN public.cliente_v2 c ON c.id_cliente = pvr.cliente_id
        LEFT JOIN public.usuario_v2 v ON v.id_usuario = pvr.vendedor_id
        LEFT JOIN public.plazo_v2 pl ON pl.id_plazo = pvr.plazo_id
        WHERE pvr.id = :pedido_id
        LIMIT 1
    """

    df = get_dataframe(query, {"pedido_id": pedido_id})

    if df is None or df.empty:
        return None

    row = df.iloc[0]
    return {
        "pedido_id": int(row["id"]),
        "nro_pedido": row["nro_pedido"],
        "cliente_id": int(row["cliente_id"]) if row["cliente_id"] else None,
        "cliente_codigo": int(row["cliente_codigo"]) if row["cliente_codigo"] else 0,
        "cliente_nombre": row["cliente_nombre"] or "SIN CLIENTE",
        "vendedor_id": int(row["vendedor_id"]) if row["vendedor_id"] else None,
        "vendedor_nombre": row["vendedor_nombre"] or "SIN VENDEDOR",
        "lista_id": int(row["lista_precio_id"]) if row["lista_precio_id"] else None,
        "lista_nombre": row["lista_nombre"] or "SIN LISTA",
        "plazo_id": int(row["plazo_id"]) if row["plazo_id"] else None,
        "plazo_nombre": row["plazo_nombre"] or "SIN PLAZO",
        "estado": row["estado"],
        "fecha_creacion": row["fecha_creacion"]
    }


def _obtener_facturas_del_pedido(pedido_id: int) -> List[Dict]:
    """
    Obtiene todas las Facturas Internas (agrupadas) de un pedido.

    Estructura de retorno:
    [
        {
            "nro_factura": "FI-2026-0045",
            "pp_nro": "PP-2026-0010",
            "marca": "ADIDAS",
            "caso": "NORMAL",
            "items": [...],
            "descuentos": [5, 10],
            "subtotal": 5500000,
            "descuentos_aplicados": 825000,
            "total_neto": 4675000
        },
        ...
    ]

    Args:
        pedido_id: ID del pedido_venta_rimec

    Returns:
        Lista de diccionarios con facturas agrupadas
    """
    query = """
        SELECT
            fi.id as fi_id,
            fi.nro_factura,
            fi.pp_id,
            pp.numero_registro as pp_nro,
            qa.descripcion as quincena_llegada,
            fi.marca_id,
            fi.marca as marca_nombre,
            fi.caso_id,
            fi.caso as caso_nombre,
            fi.estado as fi_estado,
            fi.descuento_1 as fi_desc_1,
            fi.descuento_2 as fi_desc_2,
            fi.descuento_3 as fi_desc_3,
            fi.descuento_4 as fi_desc_4,

            -- Datos del ítem
            fid.id as fid_id,
            fid.ppd_id,
            ppd.sku,
            ppd.id_producto_cab,
            pc.id_linea,
            l.cod_linea as linea_codigo,
            pc.id_referencia,
            r.cod_ref as ref_codigo,
            pc.nombre as producto_nombre,
            pc.imagen_url,
            ppd.id_color,
            col.nombre as color_nombre,
            ppd.descp_material as material_nombre,
            fid.gradas,
            fid.cajas,
            fid.pares,
            fid.precio_unit,
            fid.subtotal,
            fid.precio_neto,
            fid.linea_snapshot

        FROM public.factura_interna fi
        LEFT JOIN public.pedido_proveedor pp ON pp.id = fi.pp_id
        LEFT JOIN public.quincena_arribo qa ON qa.id = pp.quincena_arribo_id
        LEFT JOIN public.factura_interna_detalle fid ON fid.factura_id = fi.id
        LEFT JOIN public.pedido_proveedor_det ppd ON ppd.id = fid.ppd_id
        LEFT JOIN public.producto_cab pc ON pc.id = ppd.id_producto_cab
        LEFT JOIN public.linea l ON l.id = pc.id_linea
        LEFT JOIN public.referencia r ON r.id = pc.id_referencia
        LEFT JOIN public.color col ON col.id = ppd.id_color

        WHERE fi.pedido_id = :pedido_id
           OR (
                fi.pedido_id IS NULL
                AND ABS(EXTRACT(EPOCH FROM (
                  fi.created_at -
                  (SELECT created_at FROM public.pedido_venta_rimec WHERE id = :pedido_id)
                ))) < 10
              )
        ORDER BY fi.id, fid.id
    """

    df = get_dataframe(query, {"pedido_id": pedido_id})

    if df is None or df.empty:
        return []

    # Agrupar por factura
    facturas_dict = {}

    for idx, row in df.iterrows():
        fi_id = int(row["fi_id"])

        # Crear factura si no existe
        if fi_id not in facturas_dict:
            facturas_dict[fi_id] = {
                "fi_id": fi_id,
                "nro_factura": row["nro_factura"],
                "pp_id": int(row["pp_id"]) if row["pp_id"] else None,
                "pp_nro": row["pp_nro"] or "SIN PP",
                "quincena": row.get("quincena_llegada") or "Sin definir",
                "marca": row["marca_nombre"] or "SIN MARCA",
                "caso": row["caso_nombre"] or "SIN CASO",
                "items": [],
                "descuentos": [],
                "subtotal": Decimal(0),
                "descuentos_aplicados": Decimal(0),
                "total_neto": Decimal(0)
            }

            # Recolectar descuentos de la factura (nivel FI)
            for desc_key in ["fi_desc_1", "fi_desc_2", "fi_desc_3", "fi_desc_4"]:
                desc_val = row.get(desc_key)
                if desc_val and float(desc_val) > 0:
                    if float(desc_val) not in facturas_dict[fi_id]["descuentos"]:
                        facturas_dict[fi_id]["descuentos"].append(float(desc_val))

        # Agregar item (si existe)
        if row["fid_id"]:
            # Parsear linea_snapshot si es string
            linea_snapshot = row.get("linea_snapshot", {})
            if isinstance(linea_snapshot, str):
                try:
                    linea_snapshot = json.loads(linea_snapshot)
                except:
                    linea_snapshot = {}

            item = {
                "fid_id": int(row["fid_id"]),
                "ppd_id": int(row["ppd_id"]) if row["ppd_id"] else None,
                "sku": row["sku"] or "N/A",
                "linea_codigo": row["linea_codigo"] or linea_snapshot.get("linea_codigo", "N/A"),
                "ref_codigo": row["ref_codigo"] or linea_snapshot.get("ref_codigo", "N/A"),
                "nombre": row["material_nombre"] or linea_snapshot.get("material_nombre", "Sin material"),
                "imagen_url": row["imagen_url"] or linea_snapshot.get("imagen_url"),
                "color_nombre": row["color_nombre"] or linea_snapshot.get("color_nombre", "Sin color"),
                "gradas": row["gradas"],
                "gradas_fmt": linea_snapshot.get("gradas_fmt") or _formatear_gradas(row["gradas"]),
                "cajas": int(row["cajas"]) if row["cajas"] else 0,
                "pares": int(row["pares"]) if row["pares"] else 0,
                "precio_unit": float(row["precio_unit"] or 0),
                "precio_neto": float(row["precio_neto"] or 0),
                "subtotal": float(row["subtotal"] or 0)
            }

            facturas_dict[fi_id]["items"].append(item)

            # Acumular totales (subtotal = suma de subtotales de items)
            facturas_dict[fi_id]["subtotal"] += Decimal(str(row["subtotal"] or 0))

    # Calcular total_neto aplicando descuentos en cascada
    for fi in facturas_dict.values():
        subtotal = fi["subtotal"]
        total_neto = subtotal

        # Aplicar descuentos en cascada
        for desc_pct in fi["descuentos"]:
            total_neto = total_neto * (1 - Decimal(str(desc_pct)) / 100)

        fi["total_neto"] = float(total_neto)
        fi["descuentos_aplicados"] = float(subtotal - total_neto)
        fi["subtotal"] = float(subtotal)

    return list(facturas_dict.values())


def generar_pdf_factura_interna(pedido_id: int) -> Optional[bytes]:
    """
    Genera el PDF completo de Factura Interna para un pedido.

    Args:
        pedido_id: ID del pedido_venta_rimec

    Returns:
        bytes del PDF o None si hay error

    Raises:
        ValueError: Si el pedido no existe o no tiene facturas
    """
    # 1. Obtener metadatos del pedido
    metadata = _obtener_metadata_pedido(pedido_id)
    if not metadata:
        raise ValueError(f"Pedido ID {pedido_id} no encontrado")

    # 2. Obtener facturas agrupadas
    facturas = _obtener_facturas_del_pedido(pedido_id)
    if not facturas:
        raise ValueError(f"Pedido ID {pedido_id} no tiene facturas internas")

    # 3. Calcular totales generales
    total_general = sum(f["total_neto"] for f in facturas)
    total_pares_general = sum(
        sum(item["pares"] for item in f["items"])
        for f in facturas
    )

    # 4. Preparar contexto para el template
    context = {
        "report_title": f"Factura Interna — {metadata['nro_pedido']}",
        "nro_pedido": metadata["nro_pedido"],
        "cliente_codigo": metadata["cliente_codigo"],
        "cliente_nombre": metadata["cliente_nombre"],
        "vendedor_nombre": metadata["vendedor_nombre"],
        "plazo_nombre": metadata["plazo_nombre"],
        "lista_nombre": metadata["lista_nombre"],
        "facturas": facturas,
        "total_general": total_general,
        "total_pares_general": total_pares_general,
    }

    # 5. Generar PDF
    try:
        pdf_bytes = PDFEngine.generate(
            template_name="facturas/factura_interna",
            context=context,
            base_layout="main_layout"
        )
        return pdf_bytes

    except Exception as e:
        raise ValueError(f"Error al generar PDF: {e}")


def obtener_metadata_para_email(pedido_id: int) -> Optional[Dict]:
    """
    Obtiene metadatos necesarios para enviar email de confirmación.

    Args:
        pedido_id: ID del pedido_venta_rimec

    Returns:
        Dict con:
        {
            "pedido_id": 123,
            "nro_pedido": "PV-2026-0123",
            "cliente_nombre": "Cliente SA",
            "vendedor_nombre": "Juan Pérez",
            "vendedor_email": "vendedor@rimec.com",
            "supervisor_email": "supervisor@rimec.com",
            "total_general": 10000000,
            "total_pares": 500
        }
    """
    # Obtener metadatos base
    metadata = _obtener_metadata_pedido(pedido_id)
    if not metadata:
        return None

    # Obtener facturas para calcular totales
    facturas = _obtener_facturas_del_pedido(pedido_id)
    if not facturas:
        return None

    total_general = sum(f["total_neto"] for f in facturas)
    total_pares = sum(
        sum(item["pares"] for item in f["items"])
        for f in facturas
    )

    # Obtener emails (vendedor y supervisor)
    query_emails = """
        SELECT
            v.email as vendedor_email,
            s.email as supervisor_email
        FROM public.pedido_venta_rimec pvr
        LEFT JOIN public.usuario_v2 v ON v.id_usuario = pvr.vendedor_id
        LEFT JOIN public.usuario_v2 s ON s.id_usuario = v.supervisor_id
        WHERE pvr.id = :pedido_id
        LIMIT 1
    """

    df_emails = get_dataframe(query_emails, {"pedido_id": pedido_id})

    vendedor_email = None
    supervisor_email = None

    if df_emails is not None and not df_emails.empty:
        vendedor_email = df_emails.iloc[0]["vendedor_email"]
        supervisor_email = df_emails.iloc[0]["supervisor_email"]

    return {
        "pedido_id": metadata["pedido_id"],
        "nro_pedido": metadata["nro_pedido"],
        "cliente_nombre": metadata["cliente_nombre"],
        "vendedor_nombre": metadata["vendedor_nombre"],
        "vendedor_email": vendedor_email,
        "supervisor_email": supervisor_email,
        "total_general": total_general,
        "total_pares": total_pares
    }


# [EXECUTION-CONFIRMED] v1.0.0 - Factura Interna PDF Generator
