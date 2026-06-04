# =============================================================================
# SISTEMA: RIMEC Business Intelligence
# MODULO: core/csv_utils.py
# VERSION: 1.0.0 — COMUNICACIÓN CON "EL ENEMIGO"
# DESCRIPCIÓN: Generación centralizada de CSV para intercambio con sistema legacy
#              Similar a pdf_utils.py pero para exports CSV
# =============================================================================

import csv
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from core.database import get_dataframe

# ═════════════════════════════════════════════════════════════════════════════
# FORMATEADORES COMPARTIDOS
# ═════════════════════════════════════════════════════════════════════════════

def _grades_json_a_compacto(grades_json: dict) -> str:
    """
    Convierte grades_json (dict) a formato compacto para CSV.

    Args:
        grades_json: {'27': 1, '28': 1, '31': 2, '32': 2, '36': 1}

    Returns:
        "27(1 1 2 2 1)36"

    Proceso:
        JSON dict → formato intermedio → formato compacto
    """
    if not grades_json or not isinstance(grades_json, dict):
        return 'N/A'

    try:
        # Convertir dict a lista ordenada por talla
        items = sorted(grades_json.items(), key=lambda x: int(x[0]))

        if not items:
            return 'N/A'

        # Construir formato intermedio "27:1 · 28:1 · 31:2"
        partes = [f"{talla}:{cant}" for talla, cant in items]
        intermedio = ' · '.join(partes)

        # Usar función existente para convertir a compacto
        return _formatear_gradas_compacto(intermedio)

    except Exception:
        return 'N/A'


def _formatear_gradas_compacto(gradas_fmt: str) -> str:
    """
    Convierte gradas de formato largo a compacto para CSV.

    REUTILIZADO de pdf_factura_individual.py

    Args:
        gradas_fmt: "30:2 · 31:2 · 32:2 · 33:1 · 34:1"

    Returns:
        "30(2 2 2 1 1)34"

    Nota:
        - Separador ESPACIO (no guion)
        - Formato caja cerrada (no atómico)
        - Ver: reference_formato_grada.md en memoria
    """
    if not gradas_fmt or gradas_fmt.strip() == '':
        return ''

    try:
        # Parsear formato "30:2 · 31:2 · 32:2"
        pares = [p.strip() for p in gradas_fmt.split('·')]
        tallas = []
        cantidades = []

        for par in pares:
            if ':' in par:
                talla, cant = par.split(':')
                tallas.append(talla.strip())
                cantidades.append(cant.strip())

        if not tallas:
            return gradas_fmt  # Retornar original si no se puede parsear

        # Formato compacto: "30(2 2 2 1 1)34"
        talla_min = tallas[0]
        talla_max = tallas[-1]
        cant_str = ' '.join(cantidades)  # ESPACIO como separador

        return f"{talla_min}({cant_str}){talla_max}"

    except Exception:
        # Si falla, retornar original
        return gradas_fmt


# ═════════════════════════════════════════════════════════════════════════════
# GENERADOR CSV — RESUMEN VENTAS POR PEDIDO PROVEEDOR
# ═════════════════════════════════════════════════════════════════════════════

def generar_csv_resumen_ventas_pp(
    pp_id: int,
    output_dir: Optional[str] = None
) -> str:
    """
    Genera CSV de resumen de ventas de un Pedido Proveedor.

    PROTOCOLO DE COMUNICACIÓN CON "EL ENEMIGO" (sistema legacy)

    Args:
        pp_id: ID del pedido proveedor
        output_dir: Directorio de salida (default: temp/)

    Returns:
        Path al archivo CSV generado

    Formato:
        21 columnas según especificación legacy

    DEUDA TÉCNICA:
        - GRUPO (Caso): extrae de donde esté disponible hoy
          → REFACTORING PENDIENTE: Segundo Corazón (próximo fin de semana)
        - Biblioteca de casos: no bien estructurada actualmente
    """
    # Configurar directorio de salida
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')

    os.makedirs(output_dir, exist_ok=True)

    # Nombre archivo: PP-YYYY-NNNN_ventas_YYYYMMDD_HHMMSS.csv
    pp_data = get_dataframe(
        "SELECT numero_registro FROM pedido_proveedor WHERE id = :pp_id",
        {"pp_id": pp_id}
    )

    if pp_data.empty:
        raise ValueError(f"Pedido Proveedor {pp_id} no encontrado")

    pp_nro = pp_data.iloc[0]['numero_registro']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{pp_nro}_ventas_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)

    # Obtener datos de facturas internas (ventas)
    filas = _obtener_datos_ventas_pp(pp_id)

    # Si no hay ventas, generar CSV con solo headers (válido para PP en preparación)
    # No es error — PP puede estar ENVIADO pero sin facturas aún

    # Escribir CSV
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)

        # Header (21 columnas)
        writer.writerow([
            'C. cliente',      # 1
            'C. Art. Prov',    # 2 (STYLE)
            'Marca',           # 3
            'C. Mat',          # 4
            'Descrip Mat',     # 5
            'C. Cor',          # 6
            'Descrip Cor',     # 7
            'C. Grada',        # 8
            'GRUPO',           # 9 (Caso)
            'GRUPO2',          # 10 (grupo_estilo)
            'Tipo de IMG',     # 11
            'C. Prov',         # 12
            'Cantidad',        # 13
            'Plazo',           # 14
            'Lista',           # 15
            'Desc1',           # 16
            'Desc2',           # 17
            'Desc3',           # 18
            'Desc4',           # 19
            'Vendedor',        # 20
            'Cobrador',        # 21
        ])

        # Datos
        for fila in filas:
            writer.writerow([
                fila['cliente_id'],           # 1: SHOP
                fila['style'],                # 2: linea.referencia
                fila['marca'],                # 3
                fila['material_code'],        # 4
                fila['material_desc'],        # 5
                fila['color_code'],           # 6
                fila['color_desc'],           # 7
                fila['grada_compacta'],       # 8: 27(1 1 1 2 2)36
                fila['caso'],                 # 9: GRUPO (Caso) — DEUDA TÉCNICA
                fila['grupo_estilo'],         # 10
                'M',                          # 11: FOTO (hardcoded)
                654,                          # 12: PROV (hardcoded)
                fila['cantidad'],             # 13
                fila['plazo'],                # 14
                fila['lista'],                # 15
                fila['desc1'],                # 16
                fila['desc2'],                # 17
                fila['desc3'],                # 18
                fila['desc4'],                # 19
                fila['vendedor'],             # 20
                90,                           # 21: Cobrador (hardcoded)
            ])

    return filepath


def _obtener_datos_ventas_pp(pp_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene datos de ventas (facturas internas) de un PP.

    FUENTE DE LA VERDAD: factura_interna + factura_interna_detalle

    Returns:
        Lista de diccionarios con datos de cada línea vendida
    """
    # Query compleja: JOIN entre factura_interna, factura_interna_detalle,
    # pedido_proveedor_detalle, y tablas relacionadas

    query = """
        SELECT
            -- Cliente
            fi.cliente_id,

            -- Producto (de pedido_proveedor_detalle)
            ppd.linea || '.' || ppd.referencia AS style,
            mv.descp_marca AS marca,
            ppd.material_code,
            ppd.descp_material AS material_desc,
            ppd.color_code,
            ppd.descp_color AS color_desc,
            ppd.grades_json,

            -- Grupo estilo
            COALESCE(lr.grupo_estilo_id, 0) AS grupo_estilo,

            -- Cantidad vendida
            fid.pares AS cantidad,

            -- Datos de factura
            COALESCE(plz.descp_plazo, 'N/A') AS plazo,
            fi.descuento_1 AS desc1,
            fi.descuento_2 AS desc2,
            fi.descuento_3 AS desc3,
            fi.descuento_4 AS desc4,

            -- Vendedor (de usuario_v2)
            COALESCE(u.descp_usuario, 'N/A') AS vendedor,

            -- CASO: desde precio_lista.nombre_caso_aplicado
            -- (mismo JOIN que v_stock_rimec)
            pl.nombre_caso_aplicado AS caso,

            -- Lista (DEUDA TÉCNICA: por ahora hardcoded o de factura)
            'LPN' AS lista

        FROM factura_interna fi
        JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
        JOIN pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
        LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
        LEFT JOIN plazo_v2 plz ON plz.id_plazo = fi.plazo_id
        LEFT JOIN usuario_v2 u ON u.id_usuario = fi.vendedor_id
        LEFT JOIN linea l ON l.codigo_proveedor::text = ppd.linea
        LEFT JOIN referencia ref ON ref.codigo_proveedor::text = ppd.referencia
            AND ref.linea_id = l.id
        LEFT JOIN linea_referencia lr ON lr.linea_id = l.id
            AND lr.referencia_id = ref.id

        -- JOIN para obtener CASO (precio_lista.nombre_caso_aplicado)
        -- Mismo patrón que v_stock_rimec
        LEFT JOIN material m ON m.codigo_proveedor::text = ppd.material_code
        LEFT JOIN LATERAL (
            SELECT icp2.precio_evento_id
            FROM intencion_compra_pedido icp2
            JOIN intencion_compra ic2 ON ic2.id = icp2.intencion_compra_id
            WHERE icp2.pedido_proveedor_id = fi.pp_id
              AND icp2.precio_evento_id IS NOT NULL
              AND (ppd.id_marca IS NULL OR ic2.id_marca = ppd.id_marca::bigint)
            ORDER BY (
                CASE
                    WHEN ppd.id_marca IS NOT NULL
                         AND ic2.id_marca = ppd.id_marca::bigint THEN 0
                    ELSE 1
                END
            ), icp2.id
            LIMIT 1
        ) ev ON true
        LEFT JOIN LATERAL (
            SELECT pl2.nombre_caso_aplicado
            FROM precio_lista pl2
            WHERE pl2.evento_id = ev.precio_evento_id
              AND pl2.linea_id = COALESCE(l.id, ref.linea_id)
              AND pl2.referencia_id = ref.id
              AND pl2.material_id = m.id
            LIMIT 1
        ) pl ON true

        WHERE fi.pp_id = :pp_id
          AND fi.estado = 'CONFIRMADA'

        ORDER BY fid.id
    """

    df = get_dataframe(query, {"pp_id": pp_id})

    if df.empty:
        return []

    # Procesar filas
    filas = []
    for _, row in df.iterrows():
        # Convertir grades_json a formato compacto
        grades_json = row['grades_json']

        # Si viene como string (representación Python dict o JSON), convertir a dict
        if isinstance(grades_json, str):
            import json
            import ast
            try:
                # Intentar parsear como JSON primero
                grades_json = json.loads(grades_json)
            except:
                try:
                    # Si falla, intentar como literal Python (comillas simples)
                    grades_json = ast.literal_eval(grades_json)
                except:
                    grades_json = None

        grada_compacta = _grades_json_a_compacto(grades_json)

        filas.append({
            'cliente_id': row['cliente_id'],
            'style': row['style'],
            'marca': row['marca'],
            'material_code': row['material_code'],
            'material_desc': row['material_desc'],
            'color_code': row['color_code'],
            'color_desc': row['color_desc'],
            'grada_compacta': grada_compacta,
            'caso': row['caso'],
            'grupo_estilo': row['grupo_estilo'],
            'cantidad': row['cantidad'],
            'plazo': row['plazo'],
            'lista': row['lista'],
            'desc1': row['desc1'],
            'desc2': row['desc2'],
            'desc3': row['desc3'],
            'desc4': row['desc4'],
            'vendedor': row['vendedor'],
        })

    return filas


# ═════════════════════════════════════════════════════════════════════════════
# DEUDA TÉCNICA — DOCUMENTACIÓN
# ═════════════════════════════════════════════════════════════════════════════

"""
DEUDA TÉCNICA CRÍTICA — Refactoring pendiente próximo fin de semana:

1. SEGUNDO CORAZÓN (Motor de Precios):
   - Actualmente: vestigios de lógica simple anterior
   - Confusión: Diccionario Web vs Motor de Precios
   - Debería ser: Biblioteca de Casos → llamada desde Motor de Precios
   - Estado: NO GOZA DE BUENA SALUD pero FUNCIONA

2. GRUPO (Caso):
   - Extracción actual: desde donde esté disponible (feo pero funcional)
   - Necesita: nombre del caso + biblioteca a la que pertenece
   - Crítico para: análisis de estrategias de precios

3. Lista de Precios:
   - Actualmente: hardcoded "LPN" o extraído de factura
   - Debería: venir de definición de usuario en pedido (Segundo Corazón)

4. GRADA (grades_json → compacto):
   - Implementación parcial
   - Necesita: conversión completa de JSON a formato intermedio

Ver: CONTEXTO_PPT.md sección "Biblioteca de Casos" (cuando se documente)
"""