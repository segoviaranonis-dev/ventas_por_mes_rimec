import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(__file__))

# Intentar importar solo lo necesario
try:
    from sqlalchemy import create_engine, text as sqlt
    import os

    # Leer DATABASE_URL del .env
    from dotenv import load_dotenv
    load_dotenv()

    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL no encontrado en .env")
        sys.exit(1)

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        print("=== VERIFICACIÓN TRASPASO_ID=16 ===\n")

        # 1. Verificar filas en traspaso_detalle
        print("1. Filas en traspaso_detalle para traspaso_id=16:")
        rows_td = conn.execute(sqlt("""
            SELECT id, traspaso_id, combinacion_id, cantidad
            FROM traspaso_detalle
            WHERE traspaso_id = 16
        """)).fetchall()
        print(f"   Total filas: {len(rows_td)}")
        for r in rows_td:
            print(f"   - id={r[0]}, traspaso_id={r[1]}, combinacion_id={r[2]}, cantidad={r[3]}")

        # 2. Verificar si las combinaciones existen
        print("\n2. Verificar combinaciones referenciadas:")
        for r in rows_td:
            comb_id = r[2]
            comb = conn.execute(sqlt("""
                SELECT c.id, c.linea_id, c.referencia_id, c.material_id, c.color_id, c.talla_id
                FROM combinacion c
                WHERE c.id = :cid
            """), {"cid": comb_id}).fetchone()
            if comb:
                print(f"   ✓ combinacion_id={comb_id}: linea_id={comb[1]}, ref_id={comb[2]}, talla_id={comb[5]}")
            else:
                print(f"   ✗ combinacion_id={comb_id}: NO EXISTE en tabla combinacion")

        # 3. Verificar que linea.codigo_proveedor existe
        print("\n3. Verificar columnas en tabla linea:")
        cols_linea = conn.execute(sqlt("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'linea' AND column_name LIKE '%codigo%'
        """)).fetchall()
        print(f"   Columnas con 'codigo': {[c[0] for c in cols_linea]}")

        # 4. Verificar que referencia.codigo_proveedor existe
        print("\n4. Verificar columnas en tabla referencia:")
        cols_ref = conn.execute(sqlt("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'referencia' AND column_name LIKE '%codigo%'
        """)).fetchall()
        print(f"   Columnas con 'codigo': {[c[0] for c in cols_ref]}")

        # 5. Verificar que talla.talla_etiqueta existe
        print("\n5. Verificar columnas en tabla talla:")
        cols_talla = conn.execute(sqlt("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'talla' AND column_name LIKE '%talla%'
        """)).fetchall()
        print(f"   Columnas con 'talla': {[c[0] for c in cols_talla]}")

        # 6. Intentar ejecutar el query completo con traspaso_id=16
        print("\n6. Ejecutar query completo (get_traspaso_detalle_lines) con id=16:")
        try:
            result = conn.execute(sqlt("""
                SELECT
                    td.id,
                    td.combinacion_id,
                    l.codigo_proveedor   AS linea,
                    r.codigo_proveedor   AS referencia,
                    mat.descripcion      AS material,
                    col.nombre           AS color,
                    tl.talla_etiqueta    AS talla,
                    td.cantidad
                FROM traspaso_detalle td
                JOIN combinacion c  ON c.id  = td.combinacion_id
                JOIN linea       l  ON l.id  = c.linea_id
                JOIN referencia  r  ON r.id  = c.referencia_id
                LEFT JOIN material   mat ON mat.id = c.material_id
                LEFT JOIN color      col ON col.id = c.color_id
                JOIN talla       tl ON tl.id = c.talla_id
                WHERE td.traspaso_id = 16
                ORDER BY l.codigo_proveedor, r.codigo_proveedor, tl.talla_etiqueta
            """)).fetchall()
            print(f"   ✓ Query ejecutado exitosamente")
            print(f"   Filas retornadas: {len(result)}")
            for r in result:
                print(f"   - linea={r[2]}, ref={r[3]}, material={r[4]}, color={r[5]}, talla={r[6]}, cant={r[7]}")
        except Exception as e:
            print(f"   ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()

except Exception as e:
    print(f"ERROR GENERAL: {e}")
    import traceback
    traceback.print_exc()
