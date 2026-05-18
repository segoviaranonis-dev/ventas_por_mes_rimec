"""
Script temporal para ejecutar migraciones del motor de precios en Supabase
"""
import psycopg2
from pathlib import Path

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

MIGRACIONES = [
    "migrations/037_caso_comercial_por_evento.sql",
    "migrations/038_null_linea_caso_id_legacy.sql",
    "migrations/039_reset_formal_motor_precios.sql",
    "migrations/040_vaciar_biblioteca_casos_legacy.sql",
    "migrations/041_fix_reset_sin_tocar_pilares.sql",
]

def ejecutar_migracion(conn, archivo):
    """Ejecuta una migración SQL"""
    path = Path(archivo)
    if not path.exists():
        print(f"[!] Archivo no encontrado: {archivo}")
        return False

    print(f"\n[*] Ejecutando: {archivo}")
    sql = path.read_text(encoding='utf-8')

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print(f"[OK] Completado: {archivo}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {archivo}: {e}")
        return False

def main():
    print("=" * 60)
    print("EJECUTANDO MIGRACIONES DEL MOTOR DE PRECIOS")
    print("=" * 60)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("[OK] Conectado a Supabase\n")

        exitos = 0
        for migracion in MIGRACIONES:
            if ejecutar_migracion(conn, migracion):
                exitos += 1

        conn.close()

        print("\n" + "=" * 60)
        print(f"RESUMEN: {exitos}/{len(MIGRACIONES)} migraciones exitosas")
        print("=" * 60)

    except Exception as e:
        print(f"[ERROR] Conexion: {e}")
        return 1

    return 0 if exitos == len(MIGRACIONES) else 1

if __name__ == "__main__":
    exit(main())
