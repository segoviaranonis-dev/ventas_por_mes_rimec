#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNÓSTICO: FIs que parecen huérfanas por vista rota (migración 095)

HIPÓTESIS DE YAMBAI:
- Las FIs SÍ tienen pedido_id correcto
- Pero v_pedido_estado_resumen usa columna equivocada (id_pedido_venta_rimec)
- Por eso no aparecen en Aprobaciones

VERIFICACIÓN:
1. Contar FIs con pedido_id NULL (verdaderas huérfanas)
2. Contar FIs con pedido_id NOT NULL (tienen pedido)
3. Verificar si PV000007 tiene pedido_id
"""
from core.database import get_dataframe

print("=" * 80)
print("DIAGNÓSTICO: FIs huérfanas (migración 095 rota)")
print("=" * 80)

# 1. Resumen general
print("\n1. RESUMEN GENERAL:")
df_resumen = get_dataframe("""
    SELECT
        fi.estado,
        COUNT(*) as total_fis,
        COUNT(fi.pedido_id) as con_pedido,
        COUNT(*) - COUNT(fi.pedido_id) as sin_pedido
    FROM factura_interna fi
    GROUP BY fi.estado
    ORDER BY fi.estado
""")

if df_resumen is not None and not df_resumen.empty:
    print(df_resumen.to_string(index=False))
else:
    print("ERROR - no se pudo consultar")

# 2. FIs confirmadas SIN pedido_id (verdaderas huérfanas)
print("\n2. FIs CONFIRMADAS SIN pedido_id (huérfanas REALES):")
df_huerfanas = get_dataframe("""
    SELECT
        fi.id,
        fi.nro_factura,
        fi.pp_id,
        pp.numero_registro as pp_nro,
        fi.total_pares,
        fi.marca,
        fi.caso,
        fi.pedido_id
    FROM factura_interna fi
    LEFT JOIN pedido_proveedor pp ON pp.id = fi.pp_id
    WHERE fi.estado = 'CONFIRMADA'
      AND fi.pedido_id IS NULL
    ORDER BY fi.nro_factura
""")

if df_huerfanas is not None and not df_huerfanas.empty:
    print(f"ENCONTRADAS: {len(df_huerfanas)} FIs sin pedido_id")
    print(df_huerfanas.to_string(index=False))
else:
    print("✅ OK - NO hay FIs confirmadas sin pedido_id")

# 3. Caso específico: PV000007
print("\n3. CASO ESPECÍFICO: PV000007 (del screenshot)")
df_pv7 = get_dataframe("""
    SELECT
        fi.id as fi_id,
        fi.nro_factura,
        fi.pedido_id,
        pvr.nro_pedido,
        pvr.estado as pedido_estado,
        fi.total_pares,
        fi.marca,
        fi.caso
    FROM factura_interna fi
    LEFT JOIN pedido_venta_rimec pvr ON pvr.id = fi.pedido_id
    WHERE fi.nro_factura LIKE '%00007%'
       OR fi.nro_factura LIKE '%PV7%'
    ORDER BY fi.nro_factura
""")

if df_pv7 is not None and not df_pv7.empty:
    print(df_pv7.to_string(index=False))

    if df_pv7['pedido_id'].isna().any():
        print("\n⚠️  PV000007 NO TIENE pedido_id (huérfana real)")
    else:
        print("\n✅ PV000007 SÍ TIENE pedido_id (el problema es la vista)")
else:
    print("⚠️  No se encontró FI PV000007")

# 4. Verificar columna real en BD
print("\n4. VERIFICAR COLUMNA REAL:")
df_schema = get_dataframe("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'factura_interna'
      AND column_name IN ('pedido_id', 'id_pedido_venta_rimec')
    ORDER BY column_name
""")

if df_schema is not None and not df_schema.empty:
    print(df_schema.to_string(index=False))

    if 'id_pedido_venta_rimec' in df_schema['column_name'].values:
        print("\n❌ ERROR - columna id_pedido_venta_rimec existe (inesperado)")
    elif 'pedido_id' in df_schema['column_name'].values:
        print("\n✅ OK - columna pedido_id existe (esperado)")
    else:
        print("\n❌ ERROR - ninguna columna de FK existe")
else:
    print("ERROR - no se pudo consultar schema")

print("\n" + "=" * 80)
print("CONCLUSIÓN:")
print("Si PV000007 tiene pedido_id pero no aparece en Aprobaciones:")
print("  → La vista v_pedido_estado_resumen (migración 095) está ROTA")
print("  → Usa fi.id_pedido_venta_rimec en lugar de fi.pedido_id")
print("  → FIX: Corregir JOIN en migración 095")
print("=" * 80)
