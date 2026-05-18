"""
BIBLIOTECA COMPARE — OT-519
Comparación Excel vs Biblioteca vs Pilar para flujo rápido (<5 min).
"""

from dataclasses import dataclass
import pandas as pd
from core.database import get_dataframe


@dataclass
class ComparacionBibliotecaExcel:
    """Resultado de comparar Excel cargado vs biblioteca seleccionada vs pilar proveedor."""
    lineas_excel: set[str]           # códigos proveedor únicos del Excel
    lineas_biblioteca: set[str]      # unión de lineas en todos los casos de la biblioteca
    lineas_pilar: set[str]           # códigos en tabla linea del proveedor
    cubiertas: set[str]              # excel ∩ biblioteca (cada línea en ≥1 caso)
    sin_caso: list[str]              # en pilar, en excel, NO en ningún caso de la bib
    no_en_pilar: list[str]           # en excel, NO en linea (proveedor)
    ok: bool                         # sin_caso vacío y no_en_pilar vacío

    def resumen_texto(self) -> str:
        """Mensaje de estado para UI."""
        if self.ok:
            return f"✅ Coincide perfecto: {len(self.cubiertas)} líneas cubiertas por la biblioteca"
        else:
            msg_parts = []
            if self.sin_caso:
                msg_parts.append(f"{len(self.sin_caso)} líneas sin caso")
            if self.no_en_pilar:
                msg_parts.append(f"{len(self.no_en_pilar)} líneas no en pilar")
            return f"⚠️ Faltan: {', '.join(msg_parts)}"


def comparar_excel_vs_biblioteca(
    skus_df: pd.DataFrame,
    proveedor_id: int,
    biblioteca_id: int,
    columna_linea: str = "linea"
) -> ComparacionBibliotecaExcel:
    """
    Compara SKUs del Excel cargado contra biblioteca y pilar.

    Args:
        skus_df: DataFrame con columna de código de línea (ej: re_skus)
        proveedor_id: ID del proveedor
        biblioteca_id: ID de la biblioteca a comparar
        columna_linea: nombre de la columna con código de línea (default "linea")

    Returns:
        ComparacionBibliotecaExcel con sets y listas para UI

    Performance: <3s para listado típico (50-100 SKUs)
    """

    # 1. Extraer líneas del Excel (set único, normalizado a string)
    lineas_excel = set()
    if columna_linea in skus_df.columns:
        for val in skus_df[columna_linea].dropna().unique():
            try:
                cod = str(int(float(val))).strip()
                if cod and cod != "0":
                    lineas_excel.add(cod)
            except (ValueError, TypeError):
                continue

    # 2. Cargar líneas de la biblioteca (unión de todos los casos)
    lineas_biblioteca = set()
    df_bib = get_dataframe(
        """SELECT DISTINCT unnest(lineas) AS linea_cod
           FROM caso_precio_biblioteca
           WHERE biblioteca_id = :bid AND lineas IS NOT NULL""",
        {"bid": biblioteca_id}
    )
    if df_bib is not None and not df_bib.empty:
        for val in df_bib["linea_cod"].dropna():
            lineas_biblioteca.add(str(val).strip())

    # 3. Cargar líneas del pilar (tabla linea del proveedor)
    lineas_pilar = set()
    df_pilar = get_dataframe(
        """SELECT codigo_proveedor
           FROM linea
           WHERE proveedor_id = :pid AND codigo_proveedor IS NOT NULL""",
        {"pid": proveedor_id}
    )
    if df_pilar is not None and not df_pilar.empty:
        for val in df_pilar["codigo_proveedor"].dropna():
            lineas_pilar.add(str(val).strip())

    # 4. Clasificar
    cubiertas = lineas_excel & lineas_biblioteca
    sin_caso_set = lineas_excel - lineas_biblioteca
    sin_caso_en_pilar = sin_caso_set & lineas_pilar
    no_en_pilar = lineas_excel - lineas_pilar

    sin_caso_list = sorted(sin_caso_en_pilar, key=lambda x: int(x) if x.isdigit() else 999999)
    no_en_pilar_list = sorted(no_en_pilar, key=lambda x: int(x) if x.isdigit() else 999999)

    ok = len(sin_caso_list) == 0 and len(no_en_pilar_list) == 0

    return ComparacionBibliotecaExcel(
        lineas_excel=lineas_excel,
        lineas_biblioteca=lineas_biblioteca,
        lineas_pilar=lineas_pilar,
        cubiertas=cubiertas,
        sin_caso=sin_caso_list,
        no_en_pilar=no_en_pilar_list,
        ok=ok
    )


def get_casos_biblioteca(biblioteca_id: int) -> dict[str, int]:
    """
    Devuelve casos de una biblioteca como dict {nombre_caso: caso_id}.
    Para multiselect en UI de resolución de gaps.
    """
    df = get_dataframe(
        """SELECT id, nombre_caso
           FROM caso_precio_biblioteca
           WHERE biblioteca_id = :bid
           ORDER BY nombre_caso""",
        {"bid": biblioteca_id}
    )
    if df is None or df.empty:
        return {}
    return {str(row["nombre_caso"]): int(row["id"]) for _, row in df.iterrows()}
