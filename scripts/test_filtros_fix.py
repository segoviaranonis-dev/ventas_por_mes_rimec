#!/usr/bin/env python3
"""
Probar queries de filtros con nombres correctos
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
    print(" PROBANDO QUERIES DE FILTROS (CORREGIDAS)")
    print("=" * 70)

    with engine.connect() as conn:
        # Género
        print("\n1. GENERO...")
        result = conn.execute(text(f"""
            SELECT DISTINCT
                g.id AS id,
                g.descripcion AS label
            FROM public.{tabla} d
            LEFT JOIN public.genero g ON g.id = d.genero_id
            WHERE g.id IS NOT NULL
            ORDER BY g.descripcion
        """))
        generos = list(result)
        print(f"   {len(generos)} géneros:")
        for g in generos:
            print(f"     - {g[1]}")

        # Marcas
        print("\n2. MARCAS...")
        result = conn.execute(text(f"""
            SELECT DISTINCT
                m.id_marca AS id,
                m.descp_marca AS label
            FROM public.{tabla} d
            LEFT JOIN public.marca_v2 m ON m.id_marca = d.marca_id
            WHERE m.id_marca IS NOT NULL
            ORDER BY m.descp_marca
        """))
        marcas = list(result)
        print(f"   {len(marcas)} marcas:")
        for m in marcas:
            print(f"     - {m[1]}")

        # Estilos
        print("\n3. ESTILOS...")
        result = conn.execute(text(f"""
            SELECT DISTINCT
                e.id_grupo_estilo AS id,
                e.descp_grupo_estilo AS label
            FROM public.{tabla} d
            LEFT JOIN public.grupo_estilo_v2 e ON e.id_grupo_estilo = d.grupo_estilo_id
            WHERE e.id_grupo_estilo IS NOT NULL
            ORDER BY e.descp_grupo_estilo
        """))
        estilos = list(result)
        print(f"   {len(estilos)} estilos:")
        for e in estilos[:10]:
            print(f"     - {e[1]}")
        if len(estilos) > 10:
            print(f"     ... y {len(estilos) - 10} mas")

        # Tipo V2
        print("\n4. TIPO V2...")
        result = conn.execute(text(f"""
            SELECT DISTINCT
                tv.id_tipo AS id,
                tv.descp_tipo AS label
            FROM public.{tabla} d
            LEFT JOIN public.tipo_v2 tv ON tv.id_tipo = d.tipo_v2_id
            WHERE tv.id_tipo IS NOT NULL
            ORDER BY tv.descp_tipo
        """))
        tipos = list(result)
        print(f"   {len(tipos)} tipos:")
        for t in tipos:
            print(f"     - {t[1]}")

    print("\n" + "=" * 70)
    print(" TODAS LAS QUERIES FUNCIONAN CORRECTAMENTE")
    print("=" * 70)

if __name__ == "__main__":
    main()
