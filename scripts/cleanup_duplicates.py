# =============================================================================
# OT-2026-042  —  Limpieza de imágenes duplicadas en bucket "productos"
# UBICACIÓN: scripts/cleanup_duplicates.py
# DESCRIPCIÓN:
#   Elimina archivos que matchean el patrón ' (N).jpg' (copias duplicadas
#   generadas por uploads repetidos) del bucket Supabase Storage "productos".
#
# USO:
#   python scripts/cleanup_duplicates.py [--dry-run]
#
#   --dry-run  Solo lista los duplicados sin eliminarlos (default: elimina).
#
# REQUISITOS:
#   - En .streamlit/secrets.toml agregar la sección:
#       [supabase]
#       service_role_key = "eyJ..."
# =============================================================================

import re
import sys
import tomllib
from pathlib import Path

import httpx

# Fix Windows cp1252 console encoding for emoji output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# 1. Configuración
# ---------------------------------------------------------------------------
BUCKET_NAME = "productos"
SUPABASE_URL = "https://extrlcvcgypwazxipvqm.supabase.co"
STORAGE_API  = f"{SUPABASE_URL}/storage/v1"

# Regex: nombre que termina en ' (1).jpg', ' (2).jpg', etc.
DUPLICATE_PATTERN = re.compile(r" \(\d+\)\.jpg$", re.IGNORECASE)

# Supabase Storage DELETE acepta listas de paths
BATCH_SIZE = 100


def load_service_role_key() -> str:
    """Lee la service_role_key desde .streamlit/secrets.toml."""
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        sys.exit(f"❌ No se encontró {secrets_path}")

    with open(secrets_path, "rb") as f:
        secrets = tomllib.load(f)

    key = secrets.get("supabase", {}).get("service_role_key")
    if not key:
        sys.exit(
            "❌ Falta [supabase] service_role_key en .streamlit/secrets.toml.\n"
            "   Agregá la sección:\n"
            "     [supabase]\n"
            '     service_role_key = "eyJ..."'
        )
    return key


def _headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def list_all_files(client: httpx.Client, key: str) -> list[dict]:
    """Lista recursivamente todos los archivos del bucket via REST."""
    all_files: list[dict] = []

    def _list_folder(prefix: str = ""):
        url = f"{STORAGE_API}/object/list/{BUCKET_NAME}"
        body: dict = {"limit": 1000, "offset": 0, "prefix": prefix}

        resp = client.post(url, json=body, headers=_headers(key))
        resp.raise_for_status()
        items = resp.json()

        for item in items:
            name = item.get("name", "")
            item_id = item.get("id")

            if item_id is None:
                # Carpeta virtual → recursión
                sub = f"{prefix}/{name}" if prefix else name
                _list_folder(sub)
            else:
                full_path = f"{prefix}/{name}" if prefix else name
                all_files.append({"name": full_path, **item})

    _list_folder()
    return all_files


def find_duplicates(files: list[dict]) -> list[str]:
    """Filtra archivos cuyo nombre matchea el patrón de duplicado."""
    return [f["name"] for f in files if DUPLICATE_PATTERN.search(f["name"])]


def remove_in_batches(client: httpx.Client, key: str, paths: list[str]) -> int:
    """Elimina archivos en lotes via REST DELETE. Retorna cantidad eliminada."""
    url = f"{STORAGE_API}/object/{BUCKET_NAME}"
    removed = 0

    for i in range(0, len(paths), BATCH_SIZE):
        batch = paths[i : i + BATCH_SIZE]
        resp = client.request(
            "DELETE", url, json={"prefixes": batch}, headers=_headers(key)
        )
        resp.raise_for_status()
        removed += len(batch)
        print(f"   🗑️  Batch {i // BATCH_SIZE + 1}: eliminados {len(batch)} archivos")

    return removed


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    dry_run = "--dry-run" in sys.argv

    # --- Credenciales -------------------------------------------------------
    print("🔑 Cargando credenciales...")
    key = load_service_role_key()
    print("✅ service_role_key cargada")

    with httpx.Client(timeout=30) as client:
        # --- Listado --------------------------------------------------------
        print(f"📂 Listando archivos del bucket '{BUCKET_NAME}'...")
        files = list_all_files(client, key)
        print(f"   Total archivos encontrados: {len(files)}")

        # --- Filtrado -------------------------------------------------------
        duplicates = find_duplicates(files)
        print(f"🔍 Duplicados detectados (patrón ' (N).jpg'): {len(duplicates)}")

        if not duplicates:
            print("✨ No hay duplicados. Nada que hacer.")
            return

        # Mostrar primeros 10 como muestra
        for path in duplicates[:10]:
            print(f"   • {path}")
        if len(duplicates) > 10:
            print(f"   ... y {len(duplicates) - 10} más.")

        # --- Eliminación ----------------------------------------------------
        if dry_run:
            print("\n⚠️  Modo DRY-RUN: no se eliminó nada.")
            print(f"   Se habrían eliminado {len(duplicates)} archivos.")
        else:
            print(f"\n🗑️  Eliminando {len(duplicates)} duplicados...")
            removed = remove_in_batches(client, key, duplicates)
            print(f"\n✅ OT-2026-042 completada: {removed} imágenes duplicadas eliminadas.")


if __name__ == "__main__":
    main()
