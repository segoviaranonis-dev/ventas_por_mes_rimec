#!/usr/bin/env python
"""
Script CLI para generar PDF de Factura Interna
Uso: python generar_pdf_cli.py <fi_id>
Retorna el PDF por stdout (en bytes)
"""

import sys
import os

# Suprimir warnings y logs de Streamlit y otros módulos
import warnings
warnings.filterwarnings('ignore')
os.environ['STREAMLIT_LOGGER_LEVEL'] = 'error'

# Agregar directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pdf_factura_individual import generar_pdf_fi_individual


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Error: Se requiere fi_id como argumento\n")
        sys.stderr.write("Uso: python generar_pdf_cli.py <fi_id>\n")
        sys.exit(1)

    try:
        fi_id = int(sys.argv[1])
    except ValueError:
        sys.stderr.write(f"Error: fi_id debe ser un número entero, recibido: {sys.argv[1]}\n")
        sys.exit(1)

    # Generar PDF
    try:
        pdf_bytes = generar_pdf_fi_individual(fi_id)

        if pdf_bytes is None:
            sys.stderr.write(f"Error: No se pudo generar PDF para FI {fi_id}\n")
            sys.exit(1)

        # Escribir bytes a stdout (modo binario)
        # En Windows, necesitamos usar binary mode para stdout
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

        sys.stdout.buffer.write(pdf_bytes)
        sys.exit(0)

    except Exception as e:
        sys.stderr.write(f"Error generando PDF: {str(e)}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
