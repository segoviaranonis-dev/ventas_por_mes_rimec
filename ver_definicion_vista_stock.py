#!/usr/bin/env python3
"""Ver definición actual de v_stock_rimec desde la DB"""
from core.database import get_dataframe

# Obtener definición de la vista
df = get_dataframe("""
    SELECT pg_get_viewdef('v_stock_rimec'::regclass, true) as vista_def
""")

if not df.empty:
    print("=== Definición actual de v_stock_rimec ===")
    vista_def = df['vista_def'].iloc[0]
    # Guardar en archivo para fácil edición
    with open('vista_actual_v_stock_rimec.sql', 'w', encoding='utf-8') as f:
        f.write(vista_def)
    print("✓ Guardado en: vista_actual_v_stock_rimec.sql")
else:
    print("No se pudo obtener la definición")
