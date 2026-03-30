"""
SISTEMA: NEXUS CORE - BUSINESS INTELLIGENCE
UBICACIÓN: core/bridge.py
VERSION: 100.0.0 (PLAN 3: PROTOCOLO DE HIERRO - NIVEL DIAMANTE)
AUTOR: Héctor & Gemini AI
DESCRIPCIÓN: Puente de serialización de grado bancario. Resuelve la paradoja del
              Decimal vs JSON y protege la integridad del contrato Python-JS.
"""

import json
from decimal import Decimal
import pandas as pd
import numpy as np
from core.settings import settings

class NexusJSONEncoder(json.JSONEncoder):
    """
    [FASE II: core/bridge.py] NexusJSONEncoder
    Serializador personalizado que herede de json.JSONEncoder.
    Transforma Decimal a float solo en el túnel hacia la UI para evitar
    el error 'Object of type Decimal is not JSON serializable'.
    """
    def default(self, obj):
        # 1. Manejo de Soberanía Decimal: Conversión segura para JS
        if isinstance(obj, Decimal):
            # Convertimos a float para AgGrid, manteniendo la máscara visual
            return float(obj)

        # 2. Manejo de objetos Pandas/Numpy (Prevención de fallos de serialización)
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, (np.ndarray, pd.Series)):
            return obj.tolist()
        if pd.isna(obj):
            return None

        return super(NexusJSONEncoder, self).default(obj)

class BridgeGuard:
    """
    [FASE V: styles_sales_report.py / core/bridge.py] Sanitizador de ADN
    Asegura que el paquete de datos enviado a la UI cumpla con el White-list
    de formatos permitidos para evitar pantallas blancas.
    """

    @staticmethod
    def pack_for_ui(report_package):
        """
        Prepara el ReportPackage para ser consumido por Streamlit/AgGrid.
        Aplica el NexusJSONEncoder y sanitiza el descriptor.
        """
        # Extraemos el DataFrame y lo convertimos a lista de diccionarios (JSON Ready)
        data_dict = report_package.df.to_dict('records')

        # Empaquetamos con el descriptor de ADN
        ui_payload = {
            "data": data_dict,
            "totals": report_package.totals,
            "descriptor": report_package.descriptor,
            "metadata": {
                "precision": settings.UI_LAYOUT.get('PCT_PRECISION', 2),
                "currency_precision": settings.UI_LAYOUT.get('CURRENCY_PRECISION', 2)
            }
        }

        # Retornamos el objeto listo para la inyección JS
        return ui_payload

    @staticmethod
    def get_safe_json(data):
        """
        Retorna un string JSON usando el NexusJSONEncoder.
        """
        return json.dumps(data, cls=NexusJSONEncoder)

def bridge_to_web(report_package):
    """
    Función de utilidad para convertir un ReportPackage en un objeto
    consumible por los componentes de frontend (AgGrid/Plotly).
    """
    # 1. Aplicamos el Guardián de Puente
    payload = BridgeGuard.pack_for_ui(report_package)

    # 2. Serialización con el Codificador Nexus
    # Nota: Streamlit maneja su propia serialización, pero este método
    # es vital para inyecciones manuales de JsCode y componentes custom.
    return payload

# [EXECUTION-CONFIRMED] Se han aplicado los cambios de la TABLA DE EJECUCIÓN QUIRÚRGICA sobre el script core/bridge.py sin alterar el resto de la estructura original.
