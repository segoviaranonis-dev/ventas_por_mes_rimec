#!/usr/bin/env python3
"""
Ejecuta la migración 009: Reestructuración de Facturas Internas (FI)
- Reset de contadores (TRUNCATE factura_interna CASCADE)
- Nomenclatura [PP_ID]-PV[NNN]
- Estado inicial RESERVADA
- Función revertir_stock_fi() mejorada
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.database import engine
from sqlalchemy import text as sqlt


def run_migration():
    migration_path = ROOT / "migrations" / "009_fi_reserva_nomenclatura.sql"
    
    if not migration_path.exists():
        print(f"❌ No se encontró el archivo de migración: {migration_path}")
        return False
    
    print("=" * 60)
    print("MIGRACIÓN 009: Reestructuración Facturas Internas (FI)")
    print("=" * 60)
    print()
    print("⚠️  ADVERTENCIA: Esta migración ejecutará TRUNCATE en factura_interna")
    print("   Todos los datos de prueba serán eliminados.")
    print()
    
    # Leer el SQL
    sql_content = migration_path.read_text(encoding="utf-8")
    
    try:
        with engine.begin() as conn:
            # Ejecutar migración
            conn.execute(sqlt(sql_content))
        
        print("✅ Migración 009 ejecutada exitosamente")
        print()
        print("Cambios aplicados:")
        print("  • TRUNCATE factura_interna CASCADE")
        print("  • Secuencia reiniciada a 1")
        print("  • Columna nro_factura verificada/creada")
        print("  • Estado default = 'RESERVADA'")
        print("  • Función generar_nro_factura_interna(pp_id) creada")
        print("  • Función revertir_stock_fi(fi_id) actualizada")
        print("  • Función crear_factura_interna_reservada() creada")
        print("  • Columna categoria_id agregada")
        print("  • Índice único en nro_factura")
        print()
        print("Nueva nomenclatura: [PP_ID]-PV[NNN]")
        print("  Ejemplo: 15-PV001, 15-PV002, 16-PV001...")
        print()
        return True
        
    except Exception as e:
        print(f"❌ Error ejecutando migración: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
