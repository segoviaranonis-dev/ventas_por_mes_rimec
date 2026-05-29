# Script de prueba de autenticación
# Simula el proceso de login para diagnosticar el problema

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*60)
print("TEST DE AUTENTICACION - Simulacion del proceso de login")
print("="*60 + "\n")

# Simular el mismo query que hace AuthManager.login
usuario_test = "DIRECTOR"
password_test = input("Ingresa la password que estas usando para DIRECTOR: ")

print(f"\nIntentando autenticar con:")
print(f"  Usuario: '{usuario_test}'")
print(f"  Password: {'*' * len(password_test)} (longitud: {len(password_test)})\n")

query = """
    SELECT id_usuario, descp_usuario, categoria, password
    FROM usuario_v2
    WHERE descp_usuario = :usuario
    AND password = :pass
    LIMIT 1
"""
params = {"usuario": usuario_test, "pass": password_test}

try:
    df = get_dataframe(query, params=params)

    if df is None or df.empty:
        print("[FALLO] Autenticacion rechazada - Credenciales invalidas\n")

        # Intentar buscar solo por usuario para ver si existe
        query2 = """
            SELECT descp_usuario, categoria,
                   LENGTH(password) as long_pass,
                   LEFT(password, 3) as inicio_pass
            FROM usuario_v2
            WHERE descp_usuario = :usuario
            LIMIT 1
        """
        params2 = {"usuario": usuario_test}
        df2 = get_dataframe(query2, params=params2)

        if df2 is not None and not df2.empty:
            print("[INFO] El usuario SI existe, pero la password NO coincide")
            print(f"\nDatos del usuario en DB:")
            print(f"  Usuario: {df2.iloc[0]['descp_usuario']}")
            print(f"  Categoria: {df2.iloc[0]['categoria']}")
            print(f"  Longitud password en DB: {df2.iloc[0]['long_pass']}")
            print(f"  Primeros 3 caracteres: {df2.iloc[0]['inicio_pass']}...")
            print(f"\nLa password que ingresaste tiene {len(password_test)} caracteres")
            print("Verifica que la password sea exactamente la correcta (case-sensitive)")
        else:
            print("[INFO] El usuario NO existe en la base de datos")
    else:
        print("[EXITO] Autenticacion correcta!\n")
        user_data = df.iloc[0]
        print(f"  ID Usuario: {user_data['id_usuario']}")
        print(f"  Nombre: {user_data['descp_usuario']}")
        print(f"  Categoria: {user_data['categoria']}")
        print("\nEl sistema de login deberia funcionar con estas credenciales.")

except Exception as e:
    print(f"[ERROR] Error durante la prueba: {str(e)}")

print("\n" + "="*60)
