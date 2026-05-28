"""
Aplicar migración 099: Sistema de notificaciones
"""
from core.database import engine
from sqlalchemy import text as sqlt

print("Aplicando migración 099: Sistema de notificaciones...")

with open("migrations/099_sistema_notificaciones.sql", "r", encoding="utf-8") as f:
    sql = f.read()

try:
    with engine.begin() as conn:
        conn.execute(sqlt(sql))
    print("[OK] Migracion 099 aplicada exitosamente")
    print("   - Tabla notificaciones creada")
    print("   - Triggers configurados")
    print("   - RLS activo")
except Exception as e:
    print(f"[ERROR] Error aplicando migracion: {e}")
