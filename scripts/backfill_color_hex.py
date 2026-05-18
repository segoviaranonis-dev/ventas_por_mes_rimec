"""
Backfill de public.color.hex_web a partir del campo `nombre`.

Aplica un diccionario de patrones (regex) sobre `color.nombre` para asignar
un código HTML hexadecimal. Maneja nombres compuestos del tipo
"BLANCO 99/BLANCO OFF 526/TAN 1080/DORADO" tomando el primer segmento.

Esto convierte el chip del frontend en una representación FIEL del pilar
(consulta directa a BD) en vez de heurística JS.

Reporta:
  · cuántas filas se asignaron
  · cuántas quedaron sin match (NULL) — para corrección manual
  · cuántas no cambiaron

Uso:
    python scripts/backfill_color_hex.py [--proveedor-id 654] [--dry-run] [--solo-nulls]
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pandas as pd
from sqlalchemy import text

from core.database import engine, get_dataframe


# ─────────────────────────────────────────────────────────────────────────────
# Diccionario de colores
# Mismas reglas que el frontend (CatalogoGrid.tsx COLOR_MAP), ampliado.
# El orden importa: los patrones más específicos van primero.
# ─────────────────────────────────────────────────────────────────────────────
COLOR_MAP: list[tuple[str, str]] = [
    # Blancos / off-whites
    (r"\bbranco\b|\bblanco\b|off\s?white|\bivory\b|\bmarfil\b", "#f5f5f0"),
    # Negros
    (r"\bpreto\b|\bnegro\b|\bblack\b",                          "#1a1a1a"),
    # Grises
    (r"\bcinza\b|\bgris\b|\bgrey\b|\bgray\b",                   "#9e9e9e"),
    # Plata
    (r"\bprata\b|\bplata\b|\bplateado\b|\bsilver\b|\bplatino\b","#b0bec5"),
    # Dorado / oro
    (r"\bdourado\b|\bdorado\b|\boro\b|\bgold\b|\bgolden\b",     "#ffd54f"),
    # Marrón / chocolate / cacao
    (r"\bchocolate\b|\bcacao\b|\bcocoa\b",                      "#4e2b0e"),
    (r"\bmarrom\b|\bmarr[oó]n\b|\bbrown\b",                     "#6d4c41"),
    (r"\bcouro\b|\bcuero\b|\bleather\b",                        "#a0785a"),
    (r"\bmoca\b|\bmokka\b|\bmocha\b|\bcoffee\b|\bcaf[eé]\b",    "#5a3d2b"),
    # Beige / nude / camel / tan / capuccino
    (r"\bcaramelo\b|\bcaramel\b",                               "#c19a6b"),
    (r"\bcamel\b",                                              "#c19a6b"),
    (r"\bcapuchino\b|\bcapu[cç]ino\b|\bcappucc?ino\b",          "#b7916a"),
    (r"\btan\b",                                                "#d2a679"),
    (r"\btaupe\b",                                              "#9e8e7e"),
    (r"\bnude\b",                                               "#e8c9a0"),
    (r"\bnatural\b",                                            "#d4b896"),
    (r"\bbege\b|\bbeige\b",                                     "#e8d5b0"),
    (r"\bcreme\b|\bcrema\b|\bcream\b",                          "#f5f0e0"),
    # Azules
    (r"\bmarinha?\b|\bmarino\b|\bnavy\b",                       "#1e3a5f"),
    (r"\bceleste\b|\baqua\b",                                   "#4fc3f7"),
    (r"\bazul\b|\bblue\b",                                      "#1565c0"),
    # Rojos / bordó / vino
    (r"\bvermelho\b|\brojo\b|\bred\b",                          "#c62828"),
    (r"\bbord[oô]\b|\bburdeo\b|\bvino\b|\bwine\b|\bguinda\b",   "#880e4f"),
    # Rosados / pink / coral
    (r"\brosa\b|\bpink\b",                                      "#f48fb1"),
    (r"\bcoral\b",                                              "#ff7043"),
    # Naranjas / amarillos / mostaza
    (r"\blaranja\b|\bnaranja\b|\borange\b",                     "#ef6c00"),
    (r"\bmostarda\b|\bmostaza\b|\bmustard\b",                   "#c8a227"),
    (r"\bamarelo\b|\bamarillo\b|\byellow\b",                    "#f9a825"),
    # Verdes
    (r"\boliva\b|\bolive\b",                                    "#827717"),
    (r"\bverde\b|\bgreen\b",                                    "#2e7d32"),
    # Violetas
    (r"\bvioleta\b|\bvioleth?\b|\bpurple\b",                    "#7b1fa2"),
    (r"\bl[ií]l[aá]s?\b|\blilac\b",                             "#ab47bc"),
    # Turquesa
    (r"\bturquesa\b|\bturquoise\b",                             "#00897b"),
]

COLOR_RES: list[tuple[re.Pattern, str]] = [
    (re.compile(pat, re.IGNORECASE), hex_) for pat, hex_ in COLOR_MAP
]


def hex_desde_nombre(nombre: str) -> str | None:
    """Resuelve el hex de un nombre. Devuelve None si no hay match.

    Para nombres compuestos del tipo "BLANCO 99/BLANCO OFF 526/TAN 1080/DORADO"
    se intenta primero el nombre completo, luego cada segmento separado por "/".
    """
    if not isinstance(nombre, str) or not nombre.strip():
        return None
    candidatos = [nombre] + [s.strip() for s in nombre.split("/") if s.strip()]
    for cand in candidatos:
        for regex, hex_ in COLOR_RES:
            if regex.search(cand):
                return hex_
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill de public.color.hex_web")
    ap.add_argument("--proveedor-id", type=int, default=654)
    ap.add_argument("--dry-run", action="store_true",
                    help="No escribe; solo muestra qué se haría.")
    ap.add_argument("--solo-nulls", action="store_true",
                    help="Solo procesa filas donde hex_web IS NULL.")
    args = ap.parse_args()

    print()
    print("═" * 78)
    print(f"  Backfill public.color.hex_web  ·  proveedor_id = {args.proveedor_id}")
    print(f"  Modo: {'DRY-RUN (no escribe)' if args.dry_run else 'EJECUCIÓN'}"
          f"  ·  Solo NULLs: {args.solo_nulls}")
    print("═" * 78)

    where_extra = "AND hex_web IS NULL" if args.solo_nulls else ""
    df = get_dataframe(f"""
        SELECT id, nombre, hex_web, codigo_proveedor
        FROM public.color
        WHERE proveedor_id = :pid
          AND activo = TRUE
          {where_extra}
        ORDER BY id
    """, {"pid": args.proveedor_id})

    if df is None or df.empty:
        print("  (sin filas para procesar)")
        return 0

    print(f"\nFilas a evaluar: {len(df):,}")

    cambios: list[tuple[int, str, str | None, str]] = []  # (id, nombre, hex_actual, hex_nuevo)
    sin_cambio = 0
    sin_match: list[tuple[int, str]] = []

    for _, row in df.iterrows():
        cid    = int(row["id"])
        nombre = str(row["nombre"] or "")
        actual = row["hex_web"] if pd.notna(row["hex_web"]) else None
        nuevo  = hex_desde_nombre(nombre)

        if nuevo is None:
            sin_match.append((cid, nombre))
            continue

        if (actual or "").lower() == nuevo.lower():
            sin_cambio += 1
            continue

        cambios.append((cid, nombre, actual, nuevo))

    # ── Reporte ──────────────────────────────────────────────────────────────
    print()
    print("─" * 78)
    print("Resumen:")
    print(f"  Cambios a aplicar:        {len(cambios):>6}")
    print(f"  Ya iguales (sin cambio):  {sin_cambio:>6}")
    print(f"  Sin match (quedan NULL):  {len(sin_match):>6}")
    print("─" * 78)

    if cambios:
        print("\nPrimeras 20 asignaciones:")
        for cid, nombre, actual, nuevo in cambios[:20]:
            actual_str = actual or "—"
            print(f"  id={cid:>5}  {nombre[:45]:<45}  {actual_str} → {nuevo}")
        if len(cambios) > 20:
            print(f"  … {len(cambios) - 20} más")

    if sin_match:
        print(f"\n⚠ {len(sin_match)} colores no matchearon ninguna regla (quedan NULL,")
        print(f"   el chip caerá al gris default del frontend):")
        for cid, nombre in sin_match[:20]:
            print(f"  id={cid:>5}  {nombre}")
        if len(sin_match) > 20:
            print(f"  … {len(sin_match) - 20} más")
        print("\n   Para corregir manualmente:")
        print("     UPDATE public.color SET hex_web = '#XXXXXX' WHERE id = N;")

    if args.dry_run:
        print("\n[--dry-run] No se escribió nada en la BD.")
        return 0

    if not cambios:
        print("\nNo hay nada que aplicar.")
        return 0

    # ── Aplicar ──────────────────────────────────────────────────────────────
    print(f"\nAplicando {len(cambios):,} UPDATEs...")
    with engine.begin() as conn:
        for cid, _nombre, _actual, nuevo in cambios:
            conn.execute(
                text("UPDATE public.color SET hex_web = :h WHERE id = :id"),
                {"h": nuevo, "id": cid},
            )
    print(f"\n✓ {len(cambios):,} filas actualizadas.")

    # ── Verificación final ───────────────────────────────────────────────────
    df_final = get_dataframe("""
        SELECT
          COUNT(*) FILTER (WHERE activo)                            AS total_activos,
          COUNT(*) FILTER (WHERE activo AND hex_web IS NOT NULL)    AS con_hex,
          COUNT(*) FILTER (WHERE activo AND hex_web IS NULL)        AS sin_hex
        FROM public.color
        WHERE proveedor_id = :pid
    """, {"pid": args.proveedor_id})
    if df_final is not None and not df_final.empty:
        r = df_final.iloc[0]
        print(f"\nEstado final del pilar `color` (proveedor {args.proveedor_id}):")
        print(f"  total activos:    {int(r['total_activos']):>5}")
        print(f"  con hex_web:      {int(r['con_hex']):>5}")
        print(f"  sin hex_web:      {int(r['sin_hex']):>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
