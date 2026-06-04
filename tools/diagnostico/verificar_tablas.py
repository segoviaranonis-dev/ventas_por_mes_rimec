# Script para verificar tablas de usuarios en la base de datos

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*60)
print("VERIFICACION: Tablas de usuarios en la base de datos")
print("="*60 + "\n")

# Buscar todas las tablas que contienen 'usuario' o 'user' en el nombre
query = """
    SELECT
        table_schema,
        table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
        AND (table_name LIKE '%usuario%' OR table_name LIKE '%user%' OR table_name LIKE '%vendedor%')
    ORDER BY table_name
"""

try:
    df = get_dataframe(query)

    if df is None or df.empty:
        print("[!] NO se encontraron tablas relacionadas con usuarios")
    else:
        print(f"[OK] Se encontraron {len(df)} tabla(s) relacionada(s) con usuarios:\n")
        for idx, row in df.iterrows():
            print(f"  - {row['table_schema']}.{row['table_name']}")

        print("\n" + "="*60)

        # Verificar si existe usuario_v2 específicamente
        if 'usuario_v2' in df['table_name'].values:
            print("\n[OK] La tabla 'usuario_v2' EXISTE")
        else:
            print("\n[CRITICO] La tabla 'usuario_v2' NO EXISTE")
            print("\nPosibles causas:")
            print("1. La migracion 066 no se ha ejecutado")
            print("2. La tabla tiene otro nombre")

except Exception as e:
    print(f"[ERROR] Error al consultar: {str(e)}")

print("\n" + "="*60)
