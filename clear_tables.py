import psycopg2
import sys
from pathlib import Path

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

TABLAS_A_VACIAR = [
    "precio_auditoria",
    "precio_evento_linea_excepcion",
    "precio_lista",
    "precio_evento_caso",
    "precio_evento",
    "retail_multitienda_staging",
    "flujo_auditoria",
    "venta_transito",
    "cliente_web",
    "pedido_venta_rimec",
    "pedido_web_detalle",
    "pedido_web",
    "movimiento_detalle",
    "movimiento",
    "traspaso_detalle",
    "traspaso",
    "compra_legal_detalle",
    "compra_legal_pedido",
    "compra_legal",
    "factura_interna_detalle",
    "factura_interna",
    "pedido_proveedor_detalle",
    "pedido_proveedor",
    "snapshot_costos",
    "intencion_compra_pedido",
    "intencion_compra",
    "intencion_compra_detalle",
    "combinacion"
]

def clear_tables():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Primero, desvincular FKs de precio_evento a evitar problemas
    try:
        cur.execute("UPDATE intencion_compra SET precio_evento_id = NULL WHERE precio_evento_id IS NOT NULL")
        cur.execute("UPDATE intencion_compra_pedido SET precio_evento_id = NULL WHERE precio_evento_id IS NOT NULL")
        cur.execute("UPDATE precio_evento SET biblioteca_precio_id = NULL WHERE biblioteca_precio_id IS NOT NULL")
        conn.commit()
        print("Desvinculaciones iniciales realizadas.")
    except Exception as e:
        conn.rollback()
        print("Aviso al desvincular:", e)

    tablas = list(TABLAS_A_VACIAR)
    intentos = 0
    max_intentos = len(tablas) * 2

    while tablas and intentos < max_intentos:
        intentos += 1
        tabla = tablas.pop(0)
        try:
            # Verificar si existe la tabla
            cur.execute("SELECT to_regclass(%s)", (f"public.{tabla}",))
            if not cur.fetchone()[0]:
                print(f"Tabla {tabla} no existe. Omitiendo.")
                continue

            cur.execute(f"DELETE FROM {tabla}")
            conn.commit()
            print(f"DELETE FROM {tabla} - OK")
        except Exception as e:
            conn.rollback()
            # Si falló por FK, la ponemos al final de la lista para intentar después
            print(f"DELETE FROM {tabla} - falló (reintentando luego): {type(e).__name__}")
            tablas.append(tabla)

    cur.close()
    conn.close()

    if tablas:
        print("No se pudieron vaciar las siguientes tablas:", tablas)
        return False
    else:
        print("Todas las tablas operativas se vaciaron con éxito.")
        return True

if __name__ == "__main__":
    sys.exit(0 if clear_tables() else 1)
