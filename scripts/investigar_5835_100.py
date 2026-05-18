"""
I2: SQL investigacion caso 5835-100 (pilar vs ppd vs vista)
"""
import psycopg2
import json

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("=" * 80)
print("INVESTIGACION CASO 5835-100: Pilar vs Consumidores")
print("=" * 80)
print()

# 1. Datos pilar linea
print("[1] PILAR: linea (marca + genero)")
print("-" * 80)
cur.execute("""
    SELECT l.id, l.codigo_proveedor, l.marca_id, mv.descp_marca,
           l.genero_id, g.descripcion AS descp_genero
    FROM linea l
    LEFT JOIN marca_v2 mv ON mv.id_marca = l.marca_id
    LEFT JOIN genero g ON g.id = l.genero_id
    WHERE l.codigo_proveedor::text = '5835'
""")
linea_row = cur.fetchone()

if linea_row:
    linea_id, cod_prov, marca_id, marca_descp, genero_id, genero_descp = linea_row
    print(f"  linea.id: {linea_id}")
    print(f"  linea.codigo_proveedor: {cod_prov}")
    print(f"  linea.marca_id: {marca_id} -> {marca_descp}")
    print(f"  linea.genero_id: {genero_id} -> {genero_descp}")
else:
    print("  [ERROR] Linea 5835 no encontrada en pilar")
    linea_id = None

print()

# 2. Datos pilar linea_referencia
if linea_id:
    print("[2] PILAR: linea_referencia (estilo + tipo1)")
    print("-" * 80)
    cur.execute("""
        SELECT lr.id, lr.linea_id, lr.referencia_id,
               lr.grupo_estilo_id, ge.descp_grupo_estilo, lr.descp_grupo_estilo AS lr_descp_estilo,
               lr.tipo_1_id, t1.descp_tipo_1, lr.descp_tipo_1 AS lr_descp_tipo1,
               r.codigo_proveedor AS ref_codigo
        FROM linea_referencia lr
        LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = lr.grupo_estilo_id
        LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
        LEFT JOIN referencia r ON r.id = lr.referencia_id
        WHERE lr.linea_id = %s
          AND lr.referencia_id = (
              SELECT id FROM referencia
              WHERE codigo_proveedor::text = '100' AND linea_id = %s
          )
    """, (linea_id, linea_id))
    lr_row = cur.fetchone()

    if lr_row:
        lr_id, lr_linea_id, lr_ref_id, ge_id, ge_descp, lr_ge_descp, t1_id, t1_descp, lr_t1_descp, ref_cod = lr_row
        print(f"  linea_referencia.id: {lr_id}")
        print(f"  linea_referencia.referencia_id: {lr_ref_id} (codigo: {ref_cod})")
        print(f"  linea_referencia.grupo_estilo_id: {ge_id} -> maestro: '{ge_descp}', lr.descp: '{lr_ge_descp}'")
        if ge_descp != lr_ge_descp:
            print(f"    !! DESVIO: descp_grupo_estilo en lr desactualizada")
        print(f"  linea_referencia.tipo_1_id: {t1_id} -> maestro: '{t1_descp}', lr.descp: '{lr_t1_descp}'")
        if t1_descp != lr_t1_descp:
            print(f"    !! DESVIO: descp_tipo_1 en lr desactualizada")
    else:
        print("  [ERROR] linea_referencia no encontrada para 5835-100")
        lr_id = None

print()

# 3. Datos en pedido_proveedor_detalle
print("[3] CONSUMIDOR: pedido_proveedor_detalle (marca)")
print("-" * 80)
cur.execute("""
    SELECT ppd.id, ppd.linea, ppd.referencia, ppd.id_marca, mv.descp_marca
    FROM pedido_proveedor_detalle ppd
    LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
    WHERE ppd.linea = '5835' AND ppd.referencia = '100'
    LIMIT 5
""")
ppd_rows = cur.fetchall()

if ppd_rows:
    print(f"  Filas encontradas: {len(ppd_rows)}")
    for ppd in ppd_rows:
        ppd_id, ppd_linea, ppd_ref, ppd_marca_id, ppd_marca_descp = ppd
        print(f"  ppd.id={ppd_id}: ppd.id_marca={ppd_marca_id} -> '{ppd_marca_descp}'")

        # Comparar con pilar
        if linea_row and ppd_marca_id != linea_row[2]:
            print(f"    !! DESVIO: ppd.id_marca ({ppd_marca_id}) != linea.marca_id ({linea_row[2]})")
else:
    print("  [INFO] No hay filas en ppd para 5835-100")

print()

# 4. Vista v_stock_rimec
print("[4] CONSUMIDOR: v_stock_rimec")
print("-" * 80)
cur.execute("""
    SELECT linea_codigo, referencia_codigo, marca_id, descp_marca,
           grupo_estilo_id, descp_grupo_estilo, tipo_1_id, descp_tipo_1
    FROM v_stock_rimec
    WHERE linea_codigo = '5835' AND referencia_codigo = '100'
    LIMIT 1
""")
vista_row = cur.fetchone()

if vista_row:
    v_linea, v_ref, v_marca_id, v_marca_descp, v_ge_id, v_ge_descp, v_t1_id, v_t1_descp = vista_row
    print(f"  v_stock_rimec.marca_id: {v_marca_id} -> '{v_marca_descp}'")
    print(f"  v_stock_rimec.grupo_estilo_id: {v_ge_id} -> '{v_ge_descp}'")
    print(f"  v_stock_rimec.tipo_1_id: {v_t1_id} -> '{v_t1_descp}'")

    # Comparar con pilar
    if linea_row and v_marca_id != linea_row[2]:
        print(f"    !! DESVIO CRITICO: vista.marca_id ({v_marca_id}) != linea.marca_id ({linea_row[2]})")
    if lr_row and v_ge_id != lr_row[3]:
        print(f"    !! DESVIO: vista.grupo_estilo_id ({v_ge_id}) != lr.grupo_estilo_id ({lr_row[3]})")
else:
    print("  [INFO] No hay filas en v_stock_rimec para 5835-100")

print()
print("=" * 80)
print("CONCLUSION")
print("=" * 80)

# Generar JSON diagnostico
diagnostico = {
    "caso": "5835-100",
    "pilar": {
        "linea_id": linea_id if linea_row else None,
        "marca_id": linea_row[2] if linea_row else None,
        "marca_descp": linea_row[3] if linea_row else None,
        "genero_id": linea_row[4] if linea_row else None,
    },
    "pilar_linea_referencia": {
        "lr_id": lr_id if lr_row else None,
        "grupo_estilo_id": lr_row[3] if lr_row else None,
        "grupo_estilo_descp_maestro": lr_row[4] if lr_row else None,
        "grupo_estilo_descp_lr": lr_row[5] if lr_row else None,
        "tipo_1_id": lr_row[6] if lr_row else None,
    },
    "ppd": {
        "count": len(ppd_rows),
        "marca_id_primera_fila": ppd_rows[0][3] if ppd_rows else None,
    },
    "v_stock_rimec": {
        "marca_id": vista_row[2] if vista_row else None,
        "grupo_estilo_id": vista_row[4] if vista_row else None,
    },
    "desvios": []
}

if linea_row and ppd_rows and ppd_rows[0][3] != linea_row[2]:
    diagnostico["desvios"].append({
        "tipo": "CRITICO",
        "componente": "ppd",
        "atributo": "marca_id",
        "valor_ppd": ppd_rows[0][3],
        "valor_pilar": linea_row[2],
        "hipotesis": "H1 - Consumidor lee ppd.id_marca en lugar de linea.marca_id"
    })

if linea_row and vista_row and vista_row[2] != linea_row[2]:
    diagnostico["desvios"].append({
        "tipo": "CRITICO",
        "componente": "v_stock_rimec",
        "atributo": "marca_id",
        "valor_vista": vista_row[2],
        "valor_pilar": linea_row[2],
        "hipotesis": "H1 - Vista lee ppd.id_marca en lugar de linea.marca_id"
    })

if lr_row and lr_row[4] != lr_row[5]:
    diagnostico["desvios"].append({
        "tipo": "MEDIO",
        "componente": "linea_referencia",
        "atributo": "descp_grupo_estilo",
        "valor_lr": lr_row[5],
        "valor_maestro": lr_row[4],
        "hipotesis": "H2 - UI no refresca descp al guardar FK"
    })

if diagnostico["desvios"]:
    print(f"[DESVIOS ENCONTRADOS] {len(diagnostico['desvios'])} desvíos:")
    for d in diagnostico["desvios"]:
        print(f"  - {d['tipo']}: {d['componente']}.{d['atributo']}")
        print(f"    Hipótesis: {d['hipotesis']}")
else:
    print("[OK] Sin desvíos detectados entre pilar y consumidores")

print()
print(f"Diagnóstico JSON guardado para evidencia")

# Guardar JSON
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
output_path = ROOT / "scripts" / "investigacion_5835_100_resultado.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(diagnostico, f, indent=2, ensure_ascii=False)

print(f"  -> {output_path}")

cur.close()
conn.close()
