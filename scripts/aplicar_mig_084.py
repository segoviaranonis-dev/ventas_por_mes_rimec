#!/usr/bin/env python3
"""
Aplica MIG-084: Fix carrito_validar para validar precios segun lista_precio_id de cada factura.

Ejecutar desde control_central/:
  python scripts/aplicar_mig_084.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print('[ERROR] Falta DATABASE_URL en .env')
        sys.exit(1)

    import psycopg2

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    print("=" * 72)
    print("APLICAR MIG-084: Fix carrito_validar multi-lista")
    print("=" * 72)

    path = ROOT / "migrations" / "084_fix_carrito_validar_multi_lista.sql"
    sql = path.read_text(encoding="utf-8")
    print("\n>> 084_fix_carrito_validar_multi_lista.sql")
    cur.execute(sql)
    conn.commit()
    print("   OK")

    # Verificar funcion actualizada
    cur.execute("""
        SELECT proname, obj_description(oid, 'pg_proc') AS comment
        FROM pg_proc
        WHERE proname = 'carrito_validar'
          AND pronamespace = 'public'::regnamespace
    """)
    row = cur.fetchone()
    if row:
        print(f"\n  Funcion carrito_validar actualizada OK")
        print(f"  Comment: {row[1]}")
    else:
        print("\n  ERROR: Funcion no encontrada")
        return 1

    conn.close()
    print("\n[EXITO] MIG-084 aplicada correctamente")
    return 0

if __name__ == '__main__':
    sys.exit(main())
