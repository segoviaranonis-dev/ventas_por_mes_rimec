"""
OT-RESET-TRANSACCIONAL-511-001: Vaciar operativa mayo 2026, conservar pilares + biblioteca + diccionario.

Anti-patrón 039/041: NO usar TRUNCATE CASCADE en caso_precio_biblioteca.
                     NO borrar biblioteca_precio ni biblioteca_caso_linea.
                     NO tocar linea, referencia, material, color, talla.

Uso:
  python scripts/reset_transaccional_etapa_511.py --dry-run
  python scripts/reset_transaccional_etapa_511.py --execute --confirm RESET-511-CONFIRMADO
"""
import argparse
import json
import pathlib
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg2
from scripts.backfill_combinacion_desde_ppd import _db_url


# Tablas a conservar (verificar counts pre=post)
TABLAS_CONSERVAR = [
    # Pilares
    "linea", "referencia", "linea_referencia", "material", "color", "talla",
    # Maestras
    "marca_v2", "genero", "grupo_estilo_v2", "tipo_v2", "categoria_v2",
    "cliente_v2", "vendedor_v2", "plazo_v2", "usuario_v2", "producto_v2",
    "grupo_v2", "comision_v2", "proveedor_importacion", "almacen",
    # Biblioteca casos
    "caso_precio_biblioteca", "biblioteca_precio", "biblioteca_caso_linea",
    # Diccionario Web OT-509
    "caso_precio_web_regla",
    # Sales Report BLINDADO
    "registro_ventas_general_v2",
    # Catálogo LPN canónico
    "listado_precio", "lista_precio",
]

# Tablas operativas a truncar (orden no crítico, multi-tabla atómica OK)
TABLAS_OPERATIVAS = [
    # Intenciones
    "intencion_compra_detalle",  # puede no existir
    "intencion_compra_pedido",
    "intencion_compra",
    # PP
    "snapshot_costos",
    "pedido_proveedor_detalle",
    "pedido_proveedor",
    # FI
    "factura_interna_detalle",
    "factura_interna",
    # CL
    "compra_legal_detalle",
    "compra_legal_pedido",
    "compra_legal",
    # Traspasos
    "traspaso_detalle",
    "traspaso",
    # Movimientos (ALM_WEB_01 + RIMEC)
    "movimiento_detalle",
    "movimiento",
    # Combinaciones derivadas
    "combinacion",
    # Web
    "pedido_web_detalle",
    "pedido_web",
    "pedido_venta_rimec",
    "cliente_web",  # solo prueba
    # Otros
    "venta_transito",
    "flujo_auditoria",
    "retail_multitienda_staging",
]

# Eventos precio (truncar separado DESPUÉS de desvincular FKs)
TABLAS_EVENTOS_PRECIO = [
    "precio_auditoria",
    "precio_evento_linea_excepcion",
    "precio_lista",
    "precio_evento_caso",
    "precio_evento",
]


def get_counts(cur, tablas: list[str]) -> dict[str, int]:
    """Obtener COUNT(*) de cada tabla. Si no existe, retorna None."""
    counts = {}
    for tabla in tablas:
        # Verificar existencia primero con to_regclass (no causa error)
        cur.execute("""
            SELECT to_regclass(%s) IS NOT NULL AS existe
        """, (f"public.{tabla}",))
        existe = cur.fetchone()[0]

        if not existe:
            counts[tabla] = None
            continue

        # Tabla existe, contar filas
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tabla}")
            counts[tabla] = cur.fetchone()[0]
        except Exception as e:
            print(f"[WARN] Error contando {tabla}: {e}")
            counts[tabla] = "ERROR"

    return counts


def desvincular_fks_precio_evento(cur):
    """UPDATE precio_evento_id = NULL en IC/ICP antes de truncar eventos."""
    print("\n[DESVINCULAR] Precio evento de intenciones...")

    # IC
    cur.execute("""
        UPDATE intencion_compra SET precio_evento_id = NULL
        WHERE precio_evento_id IS NOT NULL
    """)
    updated_ic = cur.rowcount
    print(f"  intencion_compra: {updated_ic} filas desvinculadas")

    # ICP
    cur.execute("""
        UPDATE intencion_compra_pedido SET precio_evento_id = NULL
        WHERE precio_evento_id IS NOT NULL
    """)
    updated_icp = cur.rowcount
    print(f"  intencion_compra_pedido: {updated_icp} filas desvinculadas")

    # precio_evento.biblioteca_precio_id (si columna existe)
    try:
        cur.execute("""
            UPDATE precio_evento SET biblioteca_precio_id = NULL
            WHERE biblioteca_precio_id IS NOT NULL
        """)
        updated_pe = cur.rowcount
        print(f"  precio_evento.biblioteca_precio_id: {updated_pe} filas desvinculadas")
    except psycopg2.errors.UndefinedColumn:
        print("  precio_evento.biblioteca_precio_id: columna no existe (OK)")

    return updated_ic + updated_icp


def truncar_tablas(cur, tablas: list[str], label: str):
    """Truncar lista de tablas que existen. Omitir si no existe."""
    print(f"\n[TRUNCATE] {label}...")

    # Filtrar solo tablas que existen
    existentes = []
    for tabla in tablas:
        cur.execute("""
            SELECT to_regclass(%s) IS NOT NULL AS existe
        """, (f"public.{tabla}",))
        if cur.fetchone()[0]:
            existentes.append(tabla)

    if not existentes:
        print(f"  Sin tablas {label} en BD")
        return 0

    print(f"  Truncando: {', '.join(existentes)}")

    # TRUNCATE multi-tabla atómica
    truncate_sql = f"TRUNCATE TABLE {', '.join(existentes)} RESTART IDENTITY CASCADE"
    cur.execute(truncate_sql)

    print(f"  OK - {len(existentes)} tablas truncadas")
    return len(existentes)


def main() -> bool:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Solo reporte, sin ejecutar")
    parser.add_argument("--execute", action="store_true", help="Ejecutar reset")
    parser.add_argument("--confirm", type=str, help="Token confirmación: RESET-511-CONFIRMADO")
    args = parser.parse_args()

    dry_run = args.dry_run or not args.execute

    if args.execute and args.confirm != "RESET-511-CONFIRMADO":
        print("[ERROR] Confirmación inválida. Usar: --execute --confirm RESET-511-CONFIRMADO")
        return False

    db_url = _db_url()
    if not db_url:
        print("[ERROR] Sin DATABASE_URL")
        return False

    print("=" * 80)
    print("OT-RESET-TRANSACCIONAL-511-001")
    print("Vaciar operativa mayo 2026 | Conservar pilares + biblioteca + diccionario")
    print("=" * 80)
    print(f"Modo: {'DRY RUN (solo reporte)' if dry_run else 'EXECUTE (aplicar cambios)'}")
    print()

    conn = psycopg2.connect(db_url)
    conn.autocommit = False  # Transacción explícita
    cur = conn.cursor()

    # ── FASE 1: PRE-SNAPSHOT ──────────────────────────────────────────────────
    print("[FASE 1] PRE-SNAPSHOT: Counts tablas conservar + operativas")
    print()

    todas_tablas = TABLAS_CONSERVAR + TABLAS_OPERATIVAS + TABLAS_EVENTOS_PRECIO
    pre_counts = get_counts(cur, todas_tablas)

    print("Tablas CONSERVAR (deben permanecer igual):")
    for tabla in TABLAS_CONSERVAR:
        count = pre_counts.get(tabla)
        if count is None:
            print(f"  {tabla}: NO EXISTE")
        elif count == "ERROR":
            print(f"  {tabla}: ERROR")
        else:
            print(f"  {tabla}: {count}")

    print()
    print("Tablas OPERATIVAS (a truncar):")
    total_operativas = 0
    for tabla in TABLAS_OPERATIVAS + TABLAS_EVENTOS_PRECIO:
        count = pre_counts.get(tabla)
        if count is None:
            print(f"  {tabla}: NO EXISTE (omitir)")
        elif count == "ERROR":
            print(f"  {tabla}: ERROR")
        elif count > 0:
            print(f"  {tabla}: {count} filas")
            total_operativas += count
        else:
            print(f"  {tabla}: vacía")

    print()
    print(f"Total registros operativos a borrar: {total_operativas}")

    # Verificación crítica: caso_precio_web_regla debe tener 6
    caso_web_count = pre_counts.get("caso_precio_web_regla", 0)
    if caso_web_count != 6:
        print(f"\n[WARN] caso_precio_web_regla tiene {caso_web_count} reglas (esperado: 6)")

    # Verificación crítica: pilares no vacíos
    for pilar in ["linea", "referencia", "material", "color", "talla"]:
        count = pre_counts.get(pilar, 0)
        if count == 0:
            print(f"\n[WARN] {pilar} vacío (esperado > 0)")

    if dry_run:
        print()
        print("=" * 80)
        print("[DRY RUN] No se aplicarán cambios. Ejecutar con:")
        print("  python scripts/reset_transaccional_etapa_511.py --execute --confirm RESET-511-CONFIRMADO")
        print("=" * 80)
        cur.close()
        conn.close()
        return True

    # ── FASE 2: DESVINCULAR FKs PRECIO_EVENTO ─────────────────────────────────
    print()
    print("[FASE 2] DESVINCULAR precio_evento_id de IC/ICP")
    filas_desvinculadas = desvincular_fks_precio_evento(cur)
    print(f"  Total: {filas_desvinculadas} filas desvinculadas")

    # ── FASE 3: TRUNCAR OPERATIVAS ────────────────────────────────────────────
    print()
    print("[FASE 3] TRUNCATE tablas operativas")
    truncadas_op = truncar_tablas(cur, TABLAS_OPERATIVAS, "operativas")

    # ── FASE 4: TRUNCAR EVENTOS PRECIO ────────────────────────────────────────
    print()
    print("[FASE 4] TRUNCATE eventos precio (sin biblioteca)")
    truncadas_evt = truncar_tablas(cur, TABLAS_EVENTOS_PRECIO, "eventos precio")

    # ── FASE 5: POST-SNAPSHOT ─────────────────────────────────────────────────
    print()
    print("[FASE 5] POST-SNAPSHOT: Verificar pilares + biblioteca + diccionario")
    print()

    post_counts = get_counts(cur, todas_tablas)

    # Verificación: tablas conservar deben tener mismo count
    errores = []

    for tabla in TABLAS_CONSERVAR:
        pre = pre_counts.get(tabla)
        post = post_counts.get(tabla)

        if pre is None and post is None:
            continue  # Tabla no existe, OK

        if pre != post:
            errores.append(f"  {tabla}: pre={pre} post={post} (MISMATCH)")
            print(f"  [ERROR] {tabla}: {pre} -> {post}")
        else:
            print(f"  OK {tabla}: {post}")

    # Verificación: tablas operativas deben estar en 0
    print()
    print("Tablas operativas (deben estar vacías):")
    for tabla in TABLAS_OPERATIVAS + TABLAS_EVENTOS_PRECIO:
        post = post_counts.get(tabla)
        if post is None:
            print(f"  {tabla}: NO EXISTE")
        elif post == 0:
            print(f"  OK {tabla}: 0")
        else:
            errores.append(f"  {tabla}: {post} filas (esperado 0)")
            print(f"  [ERROR] {tabla}: {post} (esperado 0)")

    # ── FASE 6: DECISIÓN COMMIT/ROLLBACK ──────────────────────────────────────
    print()
    print("=" * 80)

    if errores:
        print("[FAIL] ERRORES DETECTADOS:")
        for error in errores:
            print(error)
        print()
        print("ROLLBACK - Sin cambios aplicados")
        conn.rollback()
        cur.close()
        conn.close()
        return False

    print("[PASS] Todas las verificaciones OK")
    print()
    print(f"  Tablas operativas truncadas: {truncadas_op}")
    print(f"  Eventos precio truncados: {truncadas_evt}")
    print(f"  Filas desvinculadas: {filas_desvinculadas}")
    print(f"  Pilares conservados: {len([t for t in TABLAS_CONSERVAR if post_counts.get(t) and post_counts[t] > 0])}")
    print()
    print("COMMIT - Cambios aplicados")
    conn.commit()

    # ── FASE 7: EVIDENCIA JSON ────────────────────────────────────────────────
    evidencia = {
        "ot_id": "OT-RESET-TRANSACCIONAL-511-001",
        "fecha_ejecucion": datetime.now().isoformat(),
        "modo": "execute",
        "filas_desvinculadas": filas_desvinculadas,
        "tablas_truncadas_operativas": truncadas_op,
        "tablas_truncadas_eventos": truncadas_evt,
        "pre_counts": {k: v for k, v in pre_counts.items() if v not in [None, "ERROR"]},
        "post_counts": {k: v for k, v in post_counts.items() if v not in [None, "ERROR"]},
        "checks": [
            {
                "id": "C1",
                "pass": post_counts.get("pedido_proveedor", 0) == 0 and post_counts.get("intencion_compra", 0) == 0,
                "expected": "pedido_proveedor=0, intencion_compra=0",
                "actual": f"pp={post_counts.get('pedido_proveedor', 0)}, ic={post_counts.get('intencion_compra', 0)}"
            },
            {
                "id": "C2",
                "pass": post_counts.get("precio_evento", 0) == 0 and post_counts.get("precio_lista", 0) == 0,
                "expected": "precio_evento=0, precio_lista=0",
                "actual": f"pe={post_counts.get('precio_evento', 0)}, pl={post_counts.get('precio_lista', 0)}"
            },
            {
                "id": "C3",
                "pass": post_counts.get("movimiento_detalle", 0) == 0,
                "expected": "movimiento_detalle=0 (depósito web + RIMEC)",
                "actual": f"md={post_counts.get('movimiento_detalle', 0)}"
            },
            {
                "id": "C4",
                "pass": pre_counts.get("linea") == post_counts.get("linea"),
                "expected": f"linea COUNT pre=post",
                "actual": f"pre={pre_counts.get('linea')}, post={post_counts.get('linea')}"
            },
            {
                "id": "C5",
                "pass": pre_counts.get("caso_precio_biblioteca") == post_counts.get("caso_precio_biblioteca"),
                "expected": "caso_precio_biblioteca COUNT pre=post",
                "actual": f"pre={pre_counts.get('caso_precio_biblioteca')}, post={post_counts.get('caso_precio_biblioteca')}"
            },
            {
                "id": "C6",
                "pass": post_counts.get("caso_precio_web_regla", 0) == 6,
                "expected": "caso_precio_web_regla=6",
                "actual": f"{post_counts.get('caso_precio_web_regla', 0)}"
            },
            {
                "id": "C7",
                "pass": pre_counts.get("registro_ventas_general_v2") == post_counts.get("registro_ventas_general_v2"),
                "expected": "registro_ventas_general_v2 sin cambio",
                "actual": f"pre={pre_counts.get('registro_ventas_general_v2')}, post={post_counts.get('registro_ventas_general_v2')}"
            }
        ],
        "observaciones": [
            "Operativa mayo 2026 vaciada exitosamente",
            "Pilares conservados sin cambios",
            "Biblioteca casos intacta",
            "Diccionario Web OT-509 conservado (6 reglas)",
            "Sales Report blindado sin cambios",
            "Sistema listo para nueva carga end-to-end"
        ]
    }

    evidencia_path = ROOT / "OT-RESET-TRANSACCIONAL-511-001-EVIDENCIA.json"
    with open(evidencia_path, "w", encoding="utf-8") as f:
        json.dump(evidencia, f, indent=2, ensure_ascii=False)

    print()
    print(f"Evidencia escrita: {evidencia_path}")
    print()
    print("=" * 80)

    cur.close()
    conn.close()
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
