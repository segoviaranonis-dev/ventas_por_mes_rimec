# Script para listar usuarios de forma segura

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*60)
print("LISTADO DE USUARIOS EN usuario_v2")
print("="*60 + "\n")

# Consultar usuarios (sin mostrar password completo)
query = """
    SELECT
        id_usuario,
        descp_usuario,
        categoria,
        rol_id,
        CASE
            WHEN password IS NOT NULL AND LENGTH(TRIM(password)) > 0
            THEN 'SI (longitud: ' || LENGTH(password) || ')'
            ELSE 'NO'
        END as tiene_password
    FROM public.usuario_v2
    ORDER BY id_usuario
    LIMIT 50
"""

try:
    df = get_dataframe(query)

    if df is not None and not df.empty:
        print(f"Total usuarios: {len(df)}\n")
        print(df.to_string(index=False))

        # Buscar DIRECTOR
        print("\n" + "="*60)
        director = df[df['descp_usuario'].str.upper() == 'DIRECTOR']
        if not director.empty:
            print("\n[OK] Usuario DIRECTOR encontrado:")
            print(director.to_string(index=False))
        else:
            print("\n[!] Usuario 'DIRECTOR' NO encontrado")
            print("\nUsuarios disponibles:")
            for usuario in df['descp_usuario'].values:
                print(f"  - {usuario}")
    else:
        print("[!] La tabla esta vacia - no hay usuarios registrados")

except Exception as e:
    print(f"[ERROR] {str(e)}")

print("\n" + "="*60)
