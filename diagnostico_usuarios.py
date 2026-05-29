# Script de diagnóstico de usuarios
# Verifica la tabla usuario_v2 y muestra los usuarios registrados

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*60)
print("DIAGNÓSTICO: Sistema de Usuarios - usuario_v2")
print("="*60 + "\n")

# Consultar todos los usuarios
query = """
    SELECT
        id_usuario,
        descp_usuario,
        categoria,
        rol_id,
        CASE
            WHEN password IS NOT NULL AND password != '' THEN '*** (configurado)'
            ELSE '(SIN CONTRASEÑA)'
        END as estado_password
    FROM usuario_v2
    ORDER BY id_usuario
"""

try:
    df = get_dataframe(query)

    if df is None or df.empty:
        print("⚠️ [ALERTA] NO SE ENCONTRARON USUARIOS EN LA TABLA usuario_v2")
        print("\nEsto significa que:")
        print("1. La tabla no tiene registros")
        print("2. Necesitas crear un usuario DIRECTOR manualmente\n")
    else:
        print(f"✓ Se encontraron {len(df)} usuario(s) registrado(s):\n")
        print(df.to_string(index=False))
        print("\n" + "="*60)

        # Verificar si existe el usuario DIRECTOR
        director_exists = df['descp_usuario'].str.upper().eq('DIRECTOR').any()

        if director_exists:
            director_row = df[df['descp_usuario'].str.upper() == 'DIRECTOR'].iloc[0]
            print(f"\n✓ Usuario DIRECTOR encontrado:")
            print(f"   ID: {director_row['id_usuario']}")
            print(f"   Categoría: {director_row['categoria']}")
            print(f"   Estado password: {director_row['estado_password']}")
        else:
            print("\n⚠️ [CRÍTICO] El usuario 'DIRECTOR' NO EXISTE en la base de datos")
            print("\nSolución: Necesitas crear el usuario DIRECTOR manualmente.")

except Exception as e:
    print(f"❌ [ERROR] Error al consultar la base de datos:")
    print(f"   {str(e)}")
    print("\nVerifica:")
    print("1. Conexión a Supabase en .streamlit/secrets.toml")
    print("2. Que la tabla usuario_v2 exista")

print("\n" + "="*60)
print("Fin del diagnóstico")
print("="*60 + "\n")
