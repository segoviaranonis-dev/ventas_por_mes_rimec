# Test directo del sistema de autenticación
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import get_dataframe

print("\n" + "="*60)
print("TEST DIRECTO DE AUTENTICACION")
print("="*60 + "\n")

# Credenciales correctas
usuario = "DIRECTOR"
password = "rimec_2010"

print(f"Probando autenticacion con:")
print(f"  Usuario: {usuario}")
print(f"  Password: {password}\n")

# Query exacto que usa AuthManager.login
query = """
    SELECT id_usuario, descp_usuario, categoria
    FROM public.usuario_v2
    WHERE descp_usuario = :usuario
    AND password = :pass
    LIMIT 1
"""
params = {"usuario": usuario, "pass": password}

try:
    df = get_dataframe(query, params=params)

    if df is None or df.empty:
        print("[FALLO] La autenticacion FALLO")
        print("Esto NO deberia pasar con las credenciales correctas")
        print("\nPosibles problemas:")
        print("1. Espacios extra en la password en la DB")
        print("2. Problema con el encoding de caracteres")
        print("3. La password cambio recientemente")
    else:
        print("[EXITO] La autenticacion FUNCIONA correctamente!\n")
        user = df.iloc[0]
        print(f"  ID: {user['id_usuario']}")
        print(f"  Usuario: {user['descp_usuario']}")
        print(f"  Categoria: {user['categoria']}")
        print("\nEl sistema de login esta funcionando bien.")
        print("El problema es que el usuario esta usando una password incorrecta.")

except Exception as e:
    print(f"[ERROR] Error: {str(e)}")

print("\n" + "="*60)
