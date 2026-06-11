#!/usr/bin/env python3
"""
Probar query de filtros para depósito
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import get_engine
from sqlalchemy import text

def main():
    engine = get_engine()

    tabla = "deposito_tienda_fernando_adultos"

    print("=" * 70)
    print(f" PROBANDO FILTROS PARA: {tabla}")
    print("=" * 70)

    with engine.connect() as conn:
        # Verificar que la tabla tiene datos
        print("\n1. Verificando datos en tabla...")
        result = conn.execute(text(f"SELECT COUNT(*) as total FROM {tabla}"))
        total = result.fetchone()[0]
        print(f"   Total registros: {total:,}")

        if total == 0:
            print("\n   ⚠️  Tabla vacía - sincroniza primero")
            return

        # Probar query de géneros
        print("\n2. Probando query GÉNERO...")
        try:
            result = conn.execute(text(f"""
                SELECT DISTINCT
                    g.id_genero_v2 AS id,
                    g.descp_genero AS label
                FROM {tabla} d
                INNER JOIN genero_v2 g ON g.id_genero_v2 = d.genero_id
                WHERE g.id_genero_v2 IS NOT NULL
                ORDER BY g.descp_genero
            """))
            generos = list(result)
            print(f"   ✓ Géneros encontrados: {len(generos)}")
            for g in generos:
                print(f"     - {g[1]} (id={g[0]})")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # Probar query de marcas
        print("\n3. Probando query MARCA...")
        try:
            result = conn.execute(text(f"""
                SELECT DISTINCT
                    m.id_marca AS id,
                    m.descp_marca AS label
                FROM {tabla} d
                INNER JOIN marca_v2 m ON m.id_marca = d.marca_id
                WHERE m.id_marca IS NOT NULL
                ORDER BY m.descp_marca
            """))
            marcas = list(result)
            print(f"   ✓ Marcas encontradas: {len(marcas)}")
            for m in marcas[:5]:
                print(f"     - {m[1]} (id={m[0]})")
            if len(marcas) > 5:
                print(f"     ... y {len(marcas) - 5} más")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # Probar query de estilos
        print("\n4. Probando query ESTILO...")
        try:
            result = conn.execute(text(f"""
                SELECT DISTINCT
                    e.id_grupo_estilo AS id,
                    e.descp_grupo_estilo AS label
                FROM {tabla} d
                INNER JOIN grupo_estilo e ON e.id_grupo_estilo = d.grupo_estilo_id
                WHERE e.id_grupo_estilo IS NOT NULL
                ORDER BY e.descp_grupo_estilo
            """))
            estilos = list(result)
            print(f"   ✓ Estilos encontrados: {len(estilos)}")
            for e in estilos[:5]:
                print(f"     - {e[1]} (id={e[0]})")
            if len(estilos) > 5:
                print(f"     ... y {len(estilos) - 5} más")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

        # Probar query de tipo_v2
        print("\n5. Probando query TIPO V2...")
        try:
            result = conn.execute(text(f"""
                SELECT DISTINCT
                    tv.id_tipo AS id,
                    tv.descp_tipo AS label
                FROM {tabla} d
                INNER JOIN tipo_v2 tv ON tv.id_tipo = d.tipo_v2_id
                WHERE tv.id_tipo IS NOT NULL
                ORDER BY tv.descp_tipo
            """))
            tipos = list(result)
            print(f"   ✓ Tipos encontrados: {len(tipos)}")
            for t in tipos:
                print(f"     - {t[1]} (id={t[0]})")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
