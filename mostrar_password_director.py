# Script para mostrar la password del usuario DIRECTOR
# ADVERTENCIA: Este script muestra contraseñas en texto plano
# Solo para diagnostico de emergencia

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*60)
print("RECUPERACION DE PASSWORD - Usuario DIRECTOR")
print("="*60 + "\n")

query = """
    SELECT
        id_usuario,
        descp_usuario,
        categoria,
        password,
        rol_id
    FROM public.usuario_v2
    WHERE UPPER(descp_usuario) = 'DIRECTOR'
    LIMIT 1
"""

try:
    df = get_dataframe(query)

    if df is not None and not df.empty:
        user = df.iloc[0]
        print("[OK] Usuario DIRECTOR encontrado:\n")
        print(f"  ID Usuario: {user['id_usuario']}")
        print(f"  Nombre: {user['descp_usuario']}")
        print(f"  Categoria: {user['categoria']}")
        print(f"  Rol ID: {user['rol_id']}")
        print(f"\n  PASSWORD ACTUAL: {user['password']}")
        print(f"  Longitud: {len(user['password'])} caracteres")
        print("\nUsa esta password EXACTAMENTE como esta mostrada (es case-sensitive)")
    else:
        print("[ERROR] Usuario DIRECTOR no encontrado")

except Exception as e:
    print(f"[ERROR] Error al consultar: {str(e)}")

print("\n" + "="*60)
