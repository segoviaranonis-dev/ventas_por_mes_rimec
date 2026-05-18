"""
R5: Resincronizar descripciones denormalizadas en linea_referencia
desde tablas maestras grupo_estilo_v2 y tipo_1.
"""
import psycopg2

DATABASE_URL = "postgres://postgres.extrlcvcgypwazxipvqm:IJoFJbT8Qj0Q0w5m@aws-1-sa-east-1.pooler.supabase.com:6543/postgres"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("=" * 80)
print("R5: RESYNC DESCRIPCIONES linea_referencia")
print("=" * 80)
print()

# Query: find rows where denormalized descp != master descp
print("[1] Identificando desvíos...")
cur.execute("""
    SELECT
        lr.id AS lr_id,
        l.codigo_proveedor AS linea_cod,
        r.codigo_proveedor AS ref_cod,
        lr.grupo_estilo_id,
        lr.descp_grupo_estilo AS lr_descp_estilo,
        ge.descp_grupo_estilo AS master_descp_estilo,
        lr.tipo_1_id,
        lr.descp_tipo_1 AS lr_descp_tipo1,
        t1.descp_tipo_1 AS master_descp_tipo1
    FROM linea_referencia lr
    JOIN linea l ON l.id = lr.linea_id
    JOIN referencia r ON r.id = lr.referencia_id
    LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = lr.grupo_estilo_id
    LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
    WHERE (
        lr.descp_grupo_estilo != ge.descp_grupo_estilo
        OR lr.descp_tipo_1 != t1.descp_tipo_1
    )
    ORDER BY l.codigo_proveedor, r.codigo_proveedor
""")

desvios = cur.fetchall()

if not desvios:
    print("[OK] Sin desvíos: todas las descripciones están sincronizadas.")
    print()
    cur.close()
    conn.close()
    exit(0)

print(f"[!!] {len(desvios)} filas con descripción obsoleta:")
print()

for row in desvios[:10]:  # Show first 10
    lr_id, linea_cod, ref_cod, ge_id, lr_ge, master_ge, t1_id, lr_t1, master_t1 = row
    print(f"  {linea_cod}/{ref_cod} (lr.id={lr_id}):")
    if lr_ge != master_ge:
        print(f"    Estilo: '{lr_ge}' -> '{master_ge}'")
    if lr_t1 != master_t1:
        print(f"    Tipo1:  '{lr_t1}' -> '{master_t1}'")

if len(desvios) > 10:
    print(f"  ... ({len(desvios) - 10} más)")

print()
print("[2] Aplicando corrección...")

# UPDATE: refresh descp from master tables
cur.execute("""
    UPDATE linea_referencia lr
    SET descp_grupo_estilo = COALESCE(ge.descp_grupo_estilo, lr.descp_grupo_estilo),
        descp_tipo_1 = COALESCE(t1.descp_tipo_1, lr.descp_tipo_1)
    FROM grupo_estilo_v2 ge, tipo_1 t1
    WHERE ge.id_grupo_estilo = lr.grupo_estilo_id
      AND t1.id_tipo_1 = lr.tipo_1_id
      AND (
          lr.descp_grupo_estilo != ge.descp_grupo_estilo
          OR lr.descp_tipo_1 != t1.descp_tipo_1
      )
""")

filas_actualizadas = cur.rowcount
conn.commit()

print(f"[OK] {filas_actualizadas} filas actualizadas")
print()

# Verify case 5835-100
print("[3] Verificando caso 5835-100 (R6)...")
cur.execute("""
    SELECT
        lr.descp_grupo_estilo,
        ge.descp_grupo_estilo AS master_descp,
        lr.descp_tipo_1,
        t1.descp_tipo_1 AS master_tipo1
    FROM linea_referencia lr
    JOIN linea l ON l.id = lr.linea_id
    JOIN referencia r ON r.id = lr.referencia_id
    LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = lr.grupo_estilo_id
    LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
    WHERE l.codigo_proveedor::text = '5835'
      AND r.codigo_proveedor::text = '100'
    LIMIT 1
""")

caso_row = cur.fetchone()

if caso_row:
    lr_estilo, master_estilo, lr_tipo1, master_tipo1 = caso_row
    print(f"  lr.descp_grupo_estilo: '{lr_estilo}'")
    print(f"  master descp_grupo_estilo: '{master_estilo}'")
    if lr_estilo == master_estilo:
        print(f"  [OK] 5835-100 estilo sincronizado: {lr_estilo}")
    else:
        print(f"  [!!] DESVIO persiste: lr='{lr_estilo}', master='{master_estilo}'")
else:
    print(f"  [INFO] Caso 5835-100 no encontrado en linea_referencia")

print()
print("=" * 80)
print("R5 COMPLETADO")
print(f"Filas resincronizadas: {filas_actualizadas}")
print("=" * 80)

cur.close()
conn.close()
