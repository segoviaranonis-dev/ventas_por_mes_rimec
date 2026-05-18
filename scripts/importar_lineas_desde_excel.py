"""
DEPRECADO para caso_id — Importa FKs en `linea` desde Excel (marca, género).

⚠️  Política 2026-05: el **caso comercial NO vive en linea.caso_id**.
    Asignación caso ↔ líneas: precio_evento + precio_evento_caso + biblioteca.
    Estilo / Tipo 1: linea_referencia (import_pilares_linea_lr_excel.py).

Uso recomendado:
    python scripts/import_pilares_linea_lr_excel.py   # linea + linea_referencia

Uso legacy (solo marca/género en linea):
    python scripts/importar_lineas_desde_excel.py <ruta.xlsx> --only marca_id,genero_id

Uso (caso_id — bloqueado salvo flag explícito):
    python scripts/importar_lineas_desde_excel.py <ruta> --only caso_id --allow-legacy-caso-id

El Excel debe tener (mínimo) columna de código de línea y al menos una FK:

    Variante A) IDs numéricos directos (recomendado):
        LINHA = codigo_proveedor de la línea
        CASO          = caso_id    (FK → caso_precio_biblioteca.id)
        TIPO_MARCA    = marca_id   (FK → marca_v2.id_marca)
        ID DE GENERO  = genero_id  (FK → genero.id)

    Variante B) Por nombre (fallback automático si el ID no matchea):
        DESCRIPCION DE CASO   → caso_precio_biblioteca.nombre_caso
        MARCA                 → marca_v2.descp_marca
        DESCRIPCION DE GENERO → genero.descripcion / genero.codigo

Cada FK se valida contra su tabla maestro antes de aplicar.
Reporta rechazos por columna y por línea.
Idempotente: corré N veces, mismo resultado.

Flags:
    --dry-run   Simula sin escribir
    --only      Comma-separated list: caso_id,marca_id,genero_id (default: todas las 3)
    --sheet     Nombre o índice de hoja (default: primera)
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from sqlalchemy import text

from core.database import engine, get_dataframe

DEFAULT_PROVEEDOR_ID = 654  # BEIRA RIO CALZADOS

# ── Aliases case-insensitive para detección de columnas ─────────────────────
ALIASES_CODIGO = {
    "codigo_proveedor", "linea_codigo", "linea_cod", "codigo",
    "linha", "linea", "cod_linea", "codigo_linea",
}

ALIASES_CASO_ID = {"caso_id", "id_caso", "case_id", "caso"}
ALIASES_CASO_NOMBRE = {
    "caso_nombre", "nombre_caso", "case", "case_name",
    "descp_caso", "case_nombre",
    "descripcion_de_caso", "descripcion de caso", "descripcion_caso",
}

ALIASES_MARCA_ID = {"marca_id", "id_marca", "tipo_marca"}
ALIASES_MARCA_NOMBRE = {"marca", "descp_marca", "nombre_marca", "descripcion_marca"}

ALIASES_GENERO_ID = {"genero_id", "id_genero", "id_de_genero", "id de genero"}
ALIASES_GENERO_NOMBRE = {
    "genero", "descp_genero", "nombre_genero", "descripcion_genero",
    "descripcion_de_genero", "descripcion de genero",
}

FK_CONFIG = {
    "caso_id": {
        "tabla": "caso_precio_biblioteca",
        "id_col": "id",
        "nombre_col": "nombre_caso",
        "scope_proveedor": True,   # se filtra por proveedor_id
        "aliases_id": ALIASES_CASO_ID,
        "aliases_nombre": ALIASES_CASO_NOMBRE,
        "matching_extra_startswith": True,  # "NORMAL BR-VZ..." matchea "NORMAL"
    },
    "marca_id": {
        "tabla": "marca_v2",
        "id_col": "id_marca",
        "nombre_col": "descp_marca",
        "scope_proveedor": False,
        "aliases_id": ALIASES_MARCA_ID,
        "aliases_nombre": ALIASES_MARCA_NOMBRE,
        "matching_extra_startswith": False,
    },
    "genero_id": {
        "tabla": "genero",
        "id_col": "id",
        "nombre_col": "descripcion",  # también acepta codigo
        "scope_proveedor": False,
        "aliases_id": ALIASES_GENERO_ID,
        "aliases_nombre": ALIASES_GENERO_NOMBRE,
        "matching_extra_startswith": False,
    },
}


# ── Helpers ─────────────────────────────────────────────────────────────────
def detectar_columna(df: pd.DataFrame, aliases: set[str]) -> str | None:
    norm = {a.strip().lower().replace(" ", "_") for a in aliases}
    for col in df.columns:
        if str(col).strip().lower().replace(" ", "_") in norm:
            return col
    return None


def normalizar_texto(s: object) -> str:
    return str(s or "").strip().upper()


def safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    if s in ("", "None", "nan", "NaN", "NULL", "<NA>"):
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def cargar_maestro_fk(fk_name: str, proveedor_id: int) -> tuple[dict[int, str], dict[str, int]]:
    """Carga la tabla maestro de una FK. Retorna (por_id, por_nombre)."""
    cfg = FK_CONFIG[fk_name]
    tabla = cfg["tabla"]
    id_col = cfg["id_col"]
    nombre_col = cfg["nombre_col"]

    if cfg["scope_proveedor"]:
        sql = f"SELECT {id_col} AS id, {nombre_col} AS nombre FROM public.{tabla} WHERE proveedor_id = :pid AND activo = true ORDER BY id"
        params = {"pid": proveedor_id}
    else:
        sql = f"SELECT {id_col} AS id, {nombre_col} AS nombre FROM public.{tabla} ORDER BY id"
        params = None

    df = get_dataframe(sql, params)
    if df is None or df.empty:
        return {}, {}

    por_id: dict[int, str] = {int(r["id"]): str(r["nombre"]) for _, r in df.iterrows() if pd.notna(r.get("id"))}
    por_nombre: dict[str, int] = {
        normalizar_texto(r["nombre"]): int(r["id"])
        for _, r in df.iterrows() if pd.notna(r.get("nombre"))
    }

    # Caso especial: género también puede matchearse por código (DAMA, CABALLERO, etc.)
    if fk_name == "genero_id":
        df_extra = get_dataframe("SELECT id, codigo FROM public.genero ORDER BY id")
        if df_extra is not None and not df_extra.empty:
            for _, r in df_extra.iterrows():
                if pd.notna(r.get("codigo")):
                    cod = normalizar_texto(r["codigo"])
                    por_nombre.setdefault(cod, int(r["id"]))

    return por_id, por_nombre


def resolver_fk_valor(
    row: pd.Series,
    col_id: str | None,
    col_nombre: str | None,
    por_id: dict[int, str],
    por_nombre: dict[str, int],
    extra_startswith: bool,
) -> tuple[int | None, str | None]:
    """
    Resuelve el valor objetivo para una FK desde una fila del Excel.
    Devuelve (fk_value, motivo_rechazo).
    motivo_rechazo es None si OK, o "id_invalido" / "nombre_no_match" / "vacio".
    """
    # 1. Intentar por ID
    if col_id is not None:
        candidato = safe_int(row[col_id])
        if candidato is not None:
            if candidato in por_id:
                return candidato, None
            # ID existe pero no matchea → guardar para luego validar por nombre
            id_bad = candidato
        else:
            id_bad = None
    else:
        id_bad = None

    # 2. Intentar por nombre exacto
    if col_nombre is not None and pd.notna(row[col_nombre]):
        nombre_norm = normalizar_texto(row[col_nombre])
        if nombre_norm in por_nombre:
            return por_nombre[nombre_norm], None
        # 3. Fallback: empieza con (ej. "NORMAL BR-VZ..." matchea "NORMAL")
        if extra_startswith:
            for clave, fk_val in por_nombre.items():
                if nombre_norm.startswith(clave + " "):
                    return fk_val, None

    if id_bad is not None:
        return None, "id_invalido"
    if col_nombre is not None and pd.notna(row[col_nombre]):
        return None, "nombre_no_match"
    return None, "vacio"


# ── Main ────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("excel_path", type=pathlib.Path, help="Ruta al .xlsx")
    parser.add_argument("--proveedor-id", type=int, default=DEFAULT_PROVEEDOR_ID)
    parser.add_argument("--sheet", default=0)
    parser.add_argument("--only", default="caso_id,marca_id,genero_id",
                        help="FKs a procesar separadas por coma (default: las 3)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-legacy-caso-id",
        action="store_true",
        help="Permite escribir linea.caso_id (viola política actual; solo migración puntual).",
    )
    args = parser.parse_args()

    if not args.excel_path.exists():
        print(f"ERROR: archivo no encontrado: {args.excel_path}", file=sys.stderr)
        return 2

    fks_solicitadas = [f.strip() for f in args.only.split(",") if f.strip()]
    fks_invalidas = [f for f in fks_solicitadas if f not in FK_CONFIG]
    if fks_invalidas:
        print(f"ERROR: FKs no soportadas: {fks_invalidas}. Validas: {list(FK_CONFIG.keys())}", file=sys.stderr)
        return 2

    if "caso_id" in fks_solicitadas and not args.allow_legacy_caso_id:
        print(
            "ERROR: caso_id en linea está DEPRECADO (independencia caso ↔ línea).\n"
            "  · Asigná casos en Motor de precios / biblioteca (precio_evento_caso).\n"
            "  · Para importar pilares use: scripts/import_pilares_linea_lr_excel.py\n"
            "  · Si es saneamiento puntual: agregá --allow-legacy-caso-id",
            file=sys.stderr,
        )
        return 2

    print(f"== Importar Pilar 1 (linea) desde {args.excel_path.name} ==")
    print(f"   Proveedor: {args.proveedor_id} | FKs a actualizar: {fks_solicitadas}\n")

    df_excel = pd.read_excel(args.excel_path, sheet_name=args.sheet, dtype=object)
    print(f"Excel leído: {len(df_excel):,} filas · columnas: {list(df_excel.columns)}\n")

    # ── 1. Detectar columna de código de línea ─────────────────────────────
    col_cod = detectar_columna(df_excel, ALIASES_CODIGO)
    if col_cod is None:
        print(f"ERROR: no se encontró columna de código de línea. Aceptadas: {sorted(ALIASES_CODIGO)}", file=sys.stderr)
        return 2

    # ── 2. Para cada FK, detectar columnas y cargar maestros ───────────────
    fk_meta: dict[str, dict] = {}
    print("Detección de columnas y maestros:")
    print(f"   Código línea          → '{col_cod}'")
    for fk in fks_solicitadas:
        cfg = FK_CONFIG[fk]
        col_id = detectar_columna(df_excel, cfg["aliases_id"])
        col_nm = detectar_columna(df_excel, cfg["aliases_nombre"])
        por_id, por_nombre = cargar_maestro_fk(fk, args.proveedor_id)
        fk_meta[fk] = {
            "col_id": col_id, "col_nombre": col_nm,
            "por_id": por_id, "por_nombre": por_nombre,
            "extra_startswith": cfg["matching_extra_startswith"],
            "tabla_destino": cfg["tabla"],
        }
        print(f"   {fk:12s}          → col_id='{col_id}' col_nombre='{col_nm}' "
              f"(maestro: {len(por_id)} filas)")
    print()

    # Verificar que al menos UNA columna esté disponible por cada FK
    for fk, m in fk_meta.items():
        if m["col_id"] is None and m["col_nombre"] is None:
            print(f"ERROR: para {fk} no se detectó ni columna de ID ni de nombre en el Excel.", file=sys.stderr)
            return 2

    # ── 3. Cargar líneas activas del proveedor (cache: codigo→(id, valores actuales)) ──
    sql_lineas = """
        SELECT id, codigo_proveedor::text AS codigo,
               caso_id, marca_id, genero_id
        FROM public.linea
        WHERE proveedor_id = :pid AND activo = true
    """
    df_lineas = get_dataframe(sql_lineas, {"pid": args.proveedor_id})
    if df_lineas is None or df_lineas.empty:
        print(f"ERROR: proveedor {args.proveedor_id} sin líneas activas", file=sys.stderr)
        return 2
    print(f"Líneas activas en DB: {len(df_lineas):,}\n")

    linea_index: dict[str, dict] = {}
    for _, r in df_lineas.iterrows():
        linea_index[str(r["codigo"]).strip()] = {
            "id":         int(r["id"]),
            "caso_id":    safe_int(r["caso_id"]),
            "marca_id":   safe_int(r["marca_id"]),
            "genero_id":  safe_int(r["genero_id"]),
        }

    # ── 4. Procesar cada fila del Excel ────────────────────────────────────
    # cambios_por_linea: linea_id → {fk_name: nuevo_valor}
    cambios_por_linea: dict[int, dict[str, int]] = {}
    rechazos_linea: list[str] = []
    rechazos_fk: dict[str, list[tuple[str, str]]] = {fk: [] for fk in fks_solicitadas}
    sin_cambio_por_fk: dict[str, int] = {fk: 0 for fk in fks_solicitadas}
    reemplazos_por_fk: dict[str, int] = {fk: 0 for fk in fks_solicitadas}
    nuevas_por_fk: dict[str, int] = {fk: 0 for fk in fks_solicitadas}

    for _, row in df_excel.iterrows():
        raw_cod = row[col_cod]
        if pd.isna(raw_cod) or str(raw_cod).strip() == "":
            continue
        try:
            cod = str(int(float(str(raw_cod).strip())))
        except (ValueError, TypeError):
            rechazos_linea.append(str(raw_cod))
            continue

        if cod not in linea_index:
            rechazos_linea.append(cod)
            continue
        linea_info = linea_index[cod]

        for fk in fks_solicitadas:
            m = fk_meta[fk]
            objetivo, motivo = resolver_fk_valor(
                row, m["col_id"], m["col_nombre"],
                m["por_id"], m["por_nombre"],
                m["extra_startswith"],
            )
            if objetivo is None:
                if motivo != "vacio":
                    val_dbg = str(row.get(m["col_id"], "") if m["col_id"] else "") or str(row.get(m["col_nombre"], "") if m["col_nombre"] else "")
                    rechazos_fk[fk].append((cod, val_dbg.strip()))
                continue

            actual = linea_info[fk]
            if actual == objetivo:
                sin_cambio_por_fk[fk] += 1
                continue

            if actual is not None and actual != objetivo:
                reemplazos_por_fk[fk] += 1
            else:
                nuevas_por_fk[fk] += 1

            cambios_por_linea.setdefault(linea_info["id"], {})[fk] = objetivo

    # ── 5. Reporte ─────────────────────────────────────────────────────────
    print("─" * 78)
    print(f"Resumen del procesamiento:")
    print(f"   Filas Excel procesadas:           {len(df_excel):>7,}")
    print(f"   Líneas inexistentes en DB:        {len(rechazos_linea):>7,}")
    print()
    for fk in fks_solicitadas:
        n_aplicar = nuevas_por_fk[fk] + reemplazos_por_fk[fk]
        print(f"  [{fk}]")
        print(f"     · aplicar:              {n_aplicar:>5,}  "
              f"(nuevas: {nuevas_por_fk[fk]:,}  reemplazos: {reemplazos_por_fk[fk]:,})")
        print(f"     · sin cambio:           {sin_cambio_por_fk[fk]:>5,}")
        print(f"     · rechazos:             {len(rechazos_fk[fk]):>5,}")
        if rechazos_fk[fk]:
            print(f"        muestra: {rechazos_fk[fk][:5]}")
    print("─" * 78)
    print(f"Líneas a tocar (al menos 1 FK cambia): {len(cambios_por_linea):,}")

    if rechazos_linea:
        print(f"\nMuestra códigos línea inexistentes ({len(rechazos_linea)}): {rechazos_linea[:10]}")

    if not cambios_por_linea:
        print("\nNada para aplicar. Saliendo.")
        return 0

    if args.dry_run:
        print("\n[--dry-run] No se escribió en la DB.")
        return 0

    # ── 6. Aplicar UPDATEs en bloques ──────────────────────────────────────
    from scripts.lib.import_heartbeat import start_import_heartbeat, stop_import_heartbeat

    print(f"\nAplicando UPDATEs en bloques de 500...")
    print("Latido activo: mensaje cada 60s mientras corre.\n")
    items = list(cambios_por_linea.items())  # [(linea_id, {fk: val, ...}), ...]
    BATCH = 500
    n_lineas_tocadas = 0
    estado = {"msg": f"UPDATE linea — 0/{len(items):,}"}
    stop_hb, hb_thread = start_import_heartbeat(lambda: estado["msg"], interval_sec=60)
    try:
        with engine.begin() as conn:
            for i in range(0, len(items), BATCH):
                chunk = items[i:i + BATCH]
                for fk in fks_solicitadas:
                    pairs = [(lid, vals[fk]) for lid, vals in chunk if fk in vals]
                    if not pairs:
                        continue
                    ids = [lid for lid, _ in pairs]
                    mapping = {f"l{j}": lid for j, (lid, _) in enumerate(pairs)}
                    mapping.update({f"v{j}": val for j, (_, val) in enumerate(pairs)})
                    case_when = " ".join(f"WHEN id = :l{j} THEN :v{j}" for j in range(len(pairs)))
                    sql = f"UPDATE public.linea SET {fk} = CASE {case_when} END WHERE id = ANY(:ids)"
                    mapping["ids"] = ids
                    conn.execute(text(sql), mapping)
                n_lineas_tocadas += len(chunk)
                estado["msg"] = f"UPDATE linea — {n_lineas_tocadas:,}/{len(items):,}"
                if i % (BATCH * 5) == 0:
                    print(f"   ... {n_lineas_tocadas:,}/{len(items):,} líneas", flush=True)
    finally:
        stop_import_heartbeat(stop_hb, hb_thread)
    print(f"\n✓ {n_lineas_tocadas:,} líneas actualizadas.")

    # ── 7. Verificación post-update ────────────────────────────────────────
    df_check = get_dataframe(
        """SELECT
              COUNT(*)                                       AS total,
              COUNT(*) FILTER (WHERE marca_id  IS NOT NULL)  AS con_marca,
              COUNT(*) FILTER (WHERE genero_id IS NOT NULL)  AS con_genero,
              COUNT(*) FILTER (WHERE caso_id   IS NOT NULL)  AS con_caso,
              COUNT(*) FILTER (WHERE marca_id IS NULL OR genero_id IS NULL OR caso_id IS NULL) AS incompletas
           FROM public.linea
           WHERE proveedor_id = :pid AND activo = true""",
        {"pid": args.proveedor_id},
    )
    if df_check is not None and not df_check.empty:
        r = df_check.iloc[0]
        print(
            f"\nEstado del Pilar 1 (proveedor {args.proveedor_id}):"
            f"\n   total líneas activas:     {int(r['total']):>7,}"
            f"\n   con marca_id:             {int(r['con_marca']):>7,}"
            f"\n   con genero_id:            {int(r['con_genero']):>7,}"
            f"\n   con caso_id:              {int(r['con_caso']):>7,}"
            f"\n   incompletas (alguna NULL):{int(r['incompletas']):>7,}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
