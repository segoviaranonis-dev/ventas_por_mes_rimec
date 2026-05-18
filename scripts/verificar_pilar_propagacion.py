"""
W4: Verificar propagación de pilar → v_stock_rimec → API estadísticas
Caso de prueba: 5835-100
"""
import psycopg2
import sys
import json

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

def main():
    linea_cod = '5835'
    ref_cod = '100'

    # Parse args
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--linea' and i + 1 < len(sys.argv):
            linea_cod = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--ref' and i + 1 < len(sys.argv):
            ref_cod = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    print("=" * 80)
    print(f"W4: VERIFICACION PILAR PROPAGACION ({linea_cod}/{ref_cod})")
    print("=" * 80)
    print()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    resultado = {
        "caso": f"{linea_cod}-{ref_cod}",
        "pilar": {},
        "v_stock_rimec": {},
        "desvios": []
    }

    # 1. Pilar: linea
    print("[1] PILAR: linea")
    print("-" * 80)
    cur.execute("""
        SELECT
            l.id AS linea_id,
            l.codigo_proveedor,
            l.marca_id,
            mv.descp_marca,
            l.genero_id,
            g.descripcion AS descp_genero
        FROM linea l
        LEFT JOIN marca_v2 mv ON mv.id_marca = l.marca_id
        LEFT JOIN genero g ON g.id = l.genero_id
        WHERE l.codigo_proveedor::text = %s
        LIMIT 1
    """, (linea_cod,))

    linea_row = cur.fetchone()

    if not linea_row:
        print(f"  [ERROR] Linea {linea_cod} no encontrada")
        resultado["pilar"]["error"] = f"Linea {linea_cod} no encontrada"
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        return

    linea_id, cod_prov, marca_id, marca_descp, genero_id, genero_descp = linea_row
    print(f"  linea.id: {linea_id}")
    print(f"  linea.marca_id: {marca_id} -> {marca_descp}")
    print(f"  linea.genero_id: {genero_id} -> {genero_descp}")
    print()

    resultado["pilar"]["linea_id"] = linea_id
    resultado["pilar"]["marca_id"] = marca_id
    resultado["pilar"]["marca_descp"] = marca_descp
    resultado["pilar"]["genero_id"] = genero_id

    # 2. Pilar: linea_referencia
    print("[2] PILAR: linea_referencia")
    print("-" * 80)
    cur.execute("""
        SELECT
            lr.id AS lr_id,
            lr.referencia_id,
            lr.grupo_estilo_id,
            ge.descp_grupo_estilo AS master_descp_estilo,
            lr.descp_grupo_estilo AS lr_descp_estilo,
            lr.tipo_1_id,
            t1.descp_tipo_1 AS master_descp_tipo1,
            lr.descp_tipo_1 AS lr_descp_tipo1
        FROM linea_referencia lr
        LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = lr.grupo_estilo_id
        LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
        WHERE lr.linea_id = %s
          AND lr.referencia_id = (
              SELECT id FROM referencia
              WHERE codigo_proveedor::text = %s AND linea_id = %s
              LIMIT 1
          )
        LIMIT 1
    """, (linea_id, ref_cod, linea_id))

    lr_row = cur.fetchone()

    if lr_row:
        lr_id, ref_id, ge_id, master_ge, lr_ge, t1_id, master_t1, lr_t1 = lr_row
        print(f"  lr.id: {lr_id}, referencia_id: {ref_id}")
        print(f"  lr.grupo_estilo_id: {ge_id}")
        print(f"    master: '{master_ge}'")
        print(f"    lr.descp: '{lr_ge}'")
        if master_ge != lr_ge:
            print(f"    [!!] DESVIO: lr.descp desactualizado")
            resultado["desvios"].append({
                "tipo": "H2",
                "componente": "linea_referencia",
                "atributo": "descp_grupo_estilo",
                "master": master_ge,
                "lr_descp": lr_ge
            })
        print(f"  lr.tipo_1_id: {t1_id} -> '{master_t1}'")

        resultado["pilar"]["grupo_estilo_id"] = ge_id
        resultado["pilar"]["descp_grupo_estilo_master"] = master_ge
        resultado["pilar"]["descp_grupo_estilo_lr"] = lr_ge
        resultado["pilar"]["tipo_1_id"] = t1_id
    else:
        print(f"  [WARN] linea_referencia no encontrada para {linea_cod}-{ref_cod}")

    print()

    # 3. Vista v_stock_rimec
    print("[3] VISTA: v_stock_rimec")
    print("-" * 80)
    cur.execute("""
        SELECT
            marca_id,
            descp_marca,
            grupo_estilo_id,
            descp_grupo_estilo,
            tipo_1_id,
            descp_tipo_1
        FROM v_stock_rimec
        WHERE linea_codigo = %s AND referencia_codigo = %s
        LIMIT 1
    """, (linea_cod, ref_cod))

    vista_row = cur.fetchone()

    if vista_row:
        v_marca_id, v_marca, v_ge_id, v_ge_descp, v_t1_id, v_t1_descp = vista_row
        print(f"  marca_id: {v_marca_id} -> '{v_marca}'")
        print(f"  grupo_estilo_id: {v_ge_id} -> '{v_ge_descp}'")
        print(f"  tipo_1_id: {v_t1_id} -> '{v_t1_descp}'")

        resultado["v_stock_rimec"]["marca_id"] = v_marca_id
        resultado["v_stock_rimec"]["descp_marca"] = v_marca
        resultado["v_stock_rimec"]["grupo_estilo_id"] = v_ge_id
        resultado["v_stock_rimec"]["descp_grupo_estilo"] = v_ge_descp

        # Compare with pilar
        if v_marca_id != marca_id:
            print(f"  [!!] DESVIO CRITICO: vista.marca_id ({v_marca_id}) != linea.marca_id ({marca_id})")
            resultado["desvios"].append({
                "tipo": "H1",
                "componente": "v_stock_rimec",
                "atributo": "marca_id",
                "vista": v_marca_id,
                "pilar": marca_id
            })
        else:
            print(f"  [OK] marca_id alineado con pilar")

        if lr_row and v_ge_descp != master_ge:
            print(f"  [!!] DESVIO: vista.descp_grupo_estilo ('{v_ge_descp}') != master ('{master_ge}')")
            resultado["desvios"].append({
                "tipo": "DESCP",
                "componente": "v_stock_rimec",
                "atributo": "descp_grupo_estilo",
                "vista": v_ge_descp,
                "master": master_ge
            })
        elif lr_row and v_ge_descp == master_ge:
            print(f"  [OK] descp_grupo_estilo alineado con maestro")
    else:
        print(f"  [WARN] No hay filas en v_stock_rimec para {linea_cod}-{ref_cod}")

    print()
    print("=" * 80)
    print("RESULTADO")
    print("=" * 80)

    if resultado["desvios"]:
        print(f"[!!] {len(resultado['desvios'])} desvíos encontrados:")
        for d in resultado["desvios"]:
            print(f"  - {d['tipo']}: {d['componente']}.{d['atributo']}")
    else:
        print("[OK] Sin desvíos: pilar -> vista OK")

    print()
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
