#!/usr/bin/env python
"""Verificar PP de 2da Quincena Mayo"""

from core.database import engine
from sqlalchemy import text
import pandas as pd

conn = engine.connect()

# Ver todos los PP de 2da quincena de mayo
df = pd.read_sql(text("""
    SELECT
        id,
        numero_registro,
        estado,
        estado_transito,
        fecha_arribo_estimada
    FROM pedido_proveedor
    WHERE fecha_arribo_estimada >= '2026-05-16'
      AND fecha_arribo_estimada <= '2026-05-31'
    ORDER BY id
"""), conn)

print("=" * 80)
print("PP CON FECHA ARRIBO EN 2DA QUINCENA MAYO (16-31 Mayo)")
print("=" * 80)
print(df.to_string(index=False))
print("\n")
print(f"Total: {len(df)} PPs")

# Contar por estado_transito
print("\nPOR ESTADO_TRANSITO:")
print(df['estado_transito'].value_counts())

conn.close()