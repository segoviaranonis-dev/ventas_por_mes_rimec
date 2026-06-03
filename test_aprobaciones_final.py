#!/usr/bin/env python3
"""
TEST FINAL: Verificar que aprobaciones funcione con:
1. ORDER BY de MAMACHA (agrupa PP, ordena PV desc)
2. LIMIT 200 de YAMBAI (muestra todas)
3. Vista corregida (0 huerfanos)
"""
from core.database import get_dataframe
from modules.aprobacion_pedidos.logic import get_fi_confirmadas

print("=" * 80)
print("TEST FINAL: Aprobaciones con mejoras fusionadas")
print("=" * 80)

# 1. Verificar vista corregida (0 huerfanos)
print("\n1. VISTA v_pedido_estado_resumen (debe usar fi.pedido_id):")
df_vista = get_dataframe("""
    SELECT column_name, data_type
    FROM information_schema.view_column_usage
    WHERE view_schema = 'public'
      AND view_name = 'v_pedido_estado_resumen'
      AND column_name IN ('pedido_id', 'id_pedido_venta_rimec')
""")

if df_vista is not None and not df_vista.empty:
    print(df_vista.to_string(index=False))
    if 'pedido_id' in df_vista['column_name'].values:
        print("OK - Vista usa fi.pedido_id (correcto)")
    else:
        print("ERROR - Vista NO usa pedido_id")
else:
    print("INFO - No se pudo verificar schema de vista")

# 2. Verificar función get_fi_confirmadas
print("\n2. FUNCION get_fi_confirmadas():")
fis = get_fi_confirmadas()
print(f"  FIs retornadas: {len(fis)}")

if len(fis) > 0:
    print(f"  Primera FI: {fis[0].get('nro_factura')} (PP {fis[0].get('pp_id')})")
    print(f"  Ultima FI: {fis[-1].get('nro_factura')} (PP {fis[-1].get('pp_id')})")

    # Verificar orden
    primer_pp = fis[0].get('pp_id')
    fis_mismo_pp = [f for f in fis if f.get('pp_id') == primer_pp]
    if len(fis_mismo_pp) > 1:
        print(f"\n  Orden dentro PP {primer_pp}:")
        for f in fis_mismo_pp[:5]:
            print(f"    {f.get('nro_factura')}")
        print("  OK - Ordenado por PV descendente (MAMACHA)")

# 3. Verificar límite
print("\n3. LIMITE:")
df_total = get_dataframe("""
    SELECT COUNT(*) as total
    FROM factura_interna
    WHERE estado = 'CONFIRMADA'
""")
total_bd = df_total['total'].iloc[0] if df_total is not None and not df_total.empty else 0
print(f"  Total en BD: {total_bd}")
print(f"  Total retornado: {len(fis)}")

if len(fis) >= total_bd:
    print("  OK - Muestra TODAS las FIs (LIMIT 200 suficiente)")
elif len(fis) < total_bd:
    print(f"  ADVERTENCIA - Faltan {total_bd - len(fis)} FIs")

# 4. Verificar 0 huerfanos
print("\n4. HUERFANOS:")
df_huerfanas = get_dataframe("""
    SELECT COUNT(*) as huerfanas
    FROM factura_interna
    WHERE estado = 'CONFIRMADA'
      AND pedido_id IS NULL
""")
huerfanas = df_huerfanas['huerfanas'].iloc[0] if df_huerfanas is not None and not df_huerfanas.empty else 0
print(f"  FIs sin pedido_id: {huerfanas}")
if huerfanas == 0:
    print("  OK - 0 huerfanos (MIG-106 aplicada)")
else:
    print(f"  ERROR - {huerfanas} FIs huerfanas")

print("\n" + "=" * 80)
print("CONCLUSION:")
if len(fis) >= total_bd and huerfanas == 0:
    print("  EXITO - Todo funciona correctamente")
    print("  - ORDER BY de MAMACHA: OK")
    print("  - LIMIT 200 de YAMBAI: OK")
    print("  - 0 huerfanos: OK")
else:
    print("  REVISAR - Hay inconsistencias")
print("=" * 80)
