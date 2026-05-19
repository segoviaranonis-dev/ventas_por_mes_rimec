"""
Módulo unificado de parsing de pilares desde Excel.

LEY FUNDAMENTAL:
- Línea y Referencia son siempre enteros (códigos proveedor)
- En Excel, columna STYLE puede contener "1184.100" → línea=1184, ref=100
- El punto separa línea (izq) de referencia (der)
- Fuente de verdad: (linea_id, referencia_id, material_id) FK en BD

Usado por: Motor de Precios, Pedido Proveedor (proforma), cualquier import pilar.
"""
from __future__ import annotations


def parsear_linea_referencia(valor_celda) -> tuple[int, int | None]:
    """
    Interpreta el valor de una celda que puede contener línea.referencia.

    Ejemplos:
        '1122.806' → (1122, 806)   línea y referencia juntas
        '1122'     → (1122, None)  solo línea
        1122       → (1122, None)  número entero
        1184.1     → (1184, 1)     float Excel trunca trailing zeros

    Raises:
        ValueError si el valor no es parseable como entero o float con punto.
    """
    valor_str = str(valor_celda).strip()

    if "." in valor_str:
        partes = valor_str.split(".", 1)
        try:
            linea = int(partes[0])
            ref = int(partes[1]) if partes[1] else None
            return (linea, ref)
        except ValueError:
            raise ValueError(
                f"No se pudo parsear '{valor_celda}' como Línea.Referencia"
            )

    try:
        return (int(float(valor_str)), None)
    except ValueError:
        raise ValueError(f"Valor de línea inválido: '{valor_celda}'")


def normalizar_triplete_excel(
    linea_cell,
    ref_cell=None,
    material_cell=None,
) -> dict:
    """
    Normaliza pilares desde Excel con manejo robusto de STYLE compuesto.

    Args:
        linea_cell: Celda línea (puede ser "1184.100" con referencia incluida)
        ref_cell: Celda referencia explícita (columna separada)
        material_cell: Celda material (código entero)

    Returns:
        {
            "linea": int,
            "referencia": int | None,
            "material": int | None,
            "warnings": list[str]
        }

    Política:
        - Si linea_cell contiene "." y ref_cell está vacío/None → split por punto
        - Si ambos tienen valor → linea_cell gana, ref_cell se ignora con warning
        - Material siempre se parsea como entero (0 si vacío)
    """
    resultado = {
        "linea": None,
        "referencia": None,
        "material": None,
        "warnings": [],
    }

    # Parse línea (puede incluir referencia)
    if linea_cell is not None and str(linea_cell).strip():
        try:
            linea_raw, ref_desde_linea = parsear_linea_referencia(linea_cell)
            resultado["linea"] = linea_raw
            if ref_desde_linea is not None:
                resultado["referencia"] = ref_desde_linea
        except ValueError as e:
            resultado["warnings"].append(f"Línea inválida: {e}")

    # Parse referencia explícita
    ref_explicita = None
    if ref_cell is not None and str(ref_cell).strip() not in ("", "nan", "None"):
        try:
            ref_explicita = int(float(str(ref_cell)))
        except (ValueError, TypeError):
            resultado["warnings"].append(f"Referencia no parseable: '{ref_cell}'")

    # Conflicto: linea_cell tenía ref Y ref_cell tiene valor
    if resultado["referencia"] is not None and ref_explicita is not None:
        if resultado["referencia"] != ref_explicita:
            resultado["warnings"].append(
                f"STYLE incluye ref {resultado['referencia']} pero columna Ref={ref_explicita}. "
                f"Se usa STYLE."
            )
    elif ref_explicita is not None:
        resultado["referencia"] = ref_explicita

    # Parse material
    if material_cell is not None and str(material_cell).strip() not in ("", "nan", "None"):
        try:
            resultado["material"] = int(float(str(material_cell)))
        except (ValueError, TypeError):
            resultado["warnings"].append(f"Material no parseable: '{material_cell}'")

    return resultado


def validar_triplete_completo(triplete: dict, strict: bool = False) -> list[str]:
    """
    Valida que un triplete tenga los 3 pilares.

    Args:
        triplete: Dict con claves linea, referencia, material
        strict: Si True, exige que referencia no sea None

    Returns:
        Lista de errores (vacía si OK)
    """
    errores = []
    if triplete.get("linea") is None or triplete["linea"] <= 0:
        errores.append("Línea faltante o inválida")
    if strict and triplete.get("referencia") is None:
        errores.append("Referencia faltante (requerida en modo strict)")
    if triplete.get("referencia") is not None and triplete["referencia"] <= 0:
        errores.append("Referencia inválida (debe ser > 0)")
    if triplete.get("material") is None or triplete["material"] <= 0:
        errores.append("Material faltante o inválido")
    return errores
