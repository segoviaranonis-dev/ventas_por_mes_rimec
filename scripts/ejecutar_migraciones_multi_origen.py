"""
Ejecuta migraciones 057, 058, 059 - Sistema multi-origen tarjetas RIMEC Web
OT: OT-RIMEC-WEB-TARJETAS-MULTI-ORIGEN-001
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.database import engine
from sqlalchemy import text

def ejecutar_migracion(archivo: str):
    """Ejecuta un archivo SQL de migración."""
    ruta = pathlib.Path(__file__).parent.parent / 'migrations' / archivo

    print(f"\n{'='*80}")
    print(f"EJECUTANDO: {archivo}")
    print(f"{'='*80}\n")

    with open(ruta, 'r', encoding='utf-8') as f:
        sql = f.read()

    try:
        with engine.connect() as conn:
            # Ejecutar en transaction
            with conn.begin():
                conn.execute(text(sql))
            print(f"✓ {archivo} ejecutado exitosamente")
            return True
    except Exception as e:
        print(f"✗ ERROR en {archivo}:")
        print(f"  {str(e)}")
        return False

def main():
    """Ejecuta las tres migraciones en orden."""
    migraciones = [
        '057_eta_catalogo.sql',
        '058_clasificacion_deposito.sql',
        '059_v_stock_rimec_origen_tipo.sql',
    ]

    print("\n" + "="*80)
    print("MIGRACIONES MULTI-ORIGEN RIMEC WEB")
    print("OT: OT-RIMEC-WEB-TARJETAS-MULTI-ORIGEN-001")
    print("="*80)

    resultados = []
    for mig in migraciones:
        exito = ejecutar_migracion(mig)
        resultados.append((mig, exito))
        if not exito:
            print(f"\n⚠ Deteniendo ejecución por error en {mig}")
            break

    print("\n" + "="*80)
    print("RESUMEN")
    print("="*80)
    for mig, exito in resultados:
        status = "✓ OK" if exito else "✗ FALLÓ"
        print(f"{status:8} {mig}")

    all_ok = all(r[1] for r in resultados)
    if all_ok:
        print("\n🚀 Todas las migraciones ejecutadas exitosamente")
        print("\nPróximos pasos:")
        print("  1. Frontend ya está listo (catalogoOrigen.ts)")
        print("  2. v_stock_rimec expone origen_tipo, deposito_id, clasificacion_stock_id")
        print("  3. HOY: todo es TRÁNSITO_PP (multi-ETA funcionando)")
        print("  4. FUTURO: cuando exista stock_detalle → UNION con STOCK_LOCAL")
    else:
        print("\n❌ Algunas migraciones fallaron - revisar errores arriba")

    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
