"""
buscador_de_fotos_retail.py

Herramienta auxiliar para poblar Supabase Storage/bucket `productos` desde las
imagenes referenciadas en `registro_st_vt_rc_reposicion` (Retail).

Adaptado de buscador_de_fotos.py para trabajar con datos de RETAIL en lugar de Sales.

Flujo:
1. Lee imagenes unicas de `registro_st_vt_rc_reposicion` (columna `imagen_nombre`).
2. Lista archivos actuales del bucket `productos`.
3. Detecta duplicados tipo "archivo (1).jpg".
4. Calcula faltantes.
5. Pide carpeta origen y carpeta respaldo via ventana.
6. Copia faltantes encontrados a respaldo.
7. Pregunta si subir faltantes a Supabase Storage.

Diferencias con buscador_de_fotos.py:
- Lee de `registro_st_vt_rc_reposicion` (no registro_ventas_general_v2)
- Usa columna `imagen_nombre` (no `imagen`)
- No filtra por `id_tipo` (no existe en retail)
- Mismo flujo de búsqueda/copia/upload

Requisitos:
- Python 3.11+
- requests
- Variables de entorno o .env.local:
  SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY / SERVICE_ROLE_KEY / NEXT_PUBLIC_SUPABASE_ANON_KEY

Uso:
  python tools/buscador_de_fotos_retail.py

Opcional:
  python tools/buscador_de_fotos_retail.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import mimetypes
import os
import re
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import quote

try:
    import requests
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Falta instalar requests. Ejecuta: python -m pip install requests"
    ) from exc

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except Exception:  # pragma: no cover
    tk = None
    filedialog = None
    messagebox = None


BUCKET = "productos"
PAGE_SIZE = 1000
DUPLICATE_RE = re.compile(r"\s\(\d+\)(?=\.[^.]+$)", re.IGNORECASE)


@dataclass
class Config:
    supabase_url: str
    key: str
    dry_run: bool


@dataclass
class FotoPlan:
    imagenes_db: set[str]
    storage_files: set[str]
    storage_duplicates: list[str]
    faltantes_storage: list[str]
    encontrados_local: dict[str, Path]
    faltantes_local: list[str]


def norm_url(url: str) -> str:
    return url.strip().rstrip("/")


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_local_env() -> None:
    cwd = Path.cwd()
    candidates = [
        cwd / ".env.local",
        cwd / ".env",
        cwd.parent / ".env.local",
        cwd.parent / "report" / ".env.local",
        cwd.parent / "rimec-web" / ".env.local",
        cwd.parent / "bazzar-web" / ".env.local",
    ]
    for path in candidates:
        load_dotenv_file(path)


def read_config(dry_run: bool) -> Config:
    load_local_env()
    url = (
        os.getenv("SUPABASE_URL")
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        or ""
    )
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        or ""
    )
    if not url or not key:
        raise SystemExit(
            "No encuentro SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL o una key de Supabase. "
            "Carga .env.local o define variables de entorno."
        )
    return Config(norm_url(url), key, dry_run)


def headers(cfg: Config, extra: dict[str, str] | None = None) -> dict[str, str]:
    out = {
        "apikey": cfg.key,
        "Authorization": f"Bearer {cfg.key}",
    }
    if extra:
        out.update(extra)
    return out


def start_heartbeat(get_msg: Callable[[], str], interval: int = 60):
    stop = threading.Event()
    counter = {"n": 0}

    def run():
        while not stop.wait(interval):
            counter["n"] += 1
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] sigo vivo "
                f"(cada {interval}s, tick {counter['n']}) — {get_msg()}",
                flush=True,
            )

    thread = threading.Thread(target=run, name="buscador-fotos-retail-heartbeat", daemon=True)
    thread.start()
    print(f"Latido activo: mensaje cada {interval}s.", flush=True)
    return stop, thread


def stop_heartbeat(stop: threading.Event, thread: threading.Thread) -> None:
    stop.set()
    thread.join(timeout=2)


def clean_image_name(value: object) -> str | None:
    if value is None:
        return None
    name = str(value).strip().replace("\\", "/").split("/")[-1]
    if not name or name.lower() in {"none", "nan", "null", ""}:
        return None
    if DUPLICATE_RE.search(name):
        # Las imagenes "(1)" no son nombre canonico; se registran como duplicado.
        return name
    return name


def fetch_imagenes_retail_db(cfg: Config) -> set[str]:
    """
    Lee imagenes unicas de registro_st_vt_rc_reposicion.

    Diferencias con version Sales:
    - Tabla: registro_st_vt_rc_reposicion (no registro_ventas_general_v2)
    - Columna: imagen_nombre (no imagen)
    - Sin filtro id_tipo (no existe en retail)
    """
    print(f"Consultando registro_st_vt_rc_reposicion (Retail)...", flush=True)
    url = f"{cfg.supabase_url}/rest/v1/registro_st_vt_rc_reposicion"
    result: set[str] = set()
    offset = 0
    while True:
        params = {
            "select": "imagen_nombre",
            "imagen_nombre": "not.is.null",
            "order": "imagen_nombre.asc",
        }
        h = headers(cfg, {"Range": f"{offset}-{offset + PAGE_SIZE - 1}"})
        res = requests.get(url, params=params, headers=h, timeout=60)
        if res.status_code >= 400:
            raise RuntimeError(f"PostgREST error {res.status_code}: {res.text}")
        rows = res.json()
        for row in rows:
            name = clean_image_name(row.get("imagen_nombre"))
            if name:
                result.add(name)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    print(f"  → {len(result)} imágenes únicas en BD", flush=True)
    return result


def list_storage_page(cfg: Config, prefix: str, offset: int) -> list[dict]:
    url = f"{cfg.supabase_url}/storage/v1/object/list/{BUCKET}"
    body = {
        "prefix": prefix,
        "limit": PAGE_SIZE,
        "offset": offset,
        "sortBy": {"column": "name", "order": "asc"},
    }
    res = requests.post(url, json=body, headers=headers(cfg), timeout=60)
    if res.status_code >= 400:
        raise RuntimeError(f"Storage list error {res.status_code}: {res.text}")
    return res.json()


def fetch_storage_files(cfg: Config) -> set[str]:
    print(f"Listando bucket Storage '{BUCKET}'...", flush=True)
    files: set[str] = set()
    offset = 0
    while True:
        rows = list_storage_page(cfg, "", offset)
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            # Bucket productos es plano en nuestra convencion.
            files.add(str(name).strip())
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    print(f"  → {len(files)} archivos en Storage", flush=True)
    return files


def duplicate_files(storage_files: Iterable[str]) -> list[str]:
    return sorted([f for f in storage_files if DUPLICATE_RE.search(f)])


def ask_folder(title: str) -> Path | None:
    if tk is None or filedialog is None:
        return None
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title=title)
    root.destroy()
    if not folder:
        return None
    return Path(folder)


def ask_yes_no(title: str, message: str) -> bool:
    if tk is None or messagebox is None:
        return False
    root = tk.Tk()
    root.withdraw()
    answer = messagebox.askyesno(title, message)
    root.destroy()
    return answer


def buscar_fotos_local(faltantes: list[str], origen: Path) -> dict[str, Path]:
    """
    Busca archivos faltantes en carpeta origen de forma recursiva.
    Retorna dict{nombre_foto: Path} con las encontradas.
    """
    print(f"Buscando {len(faltantes)} fotos en '{origen}'...", flush=True)
    encontrados: dict[str, Path] = {}
    faltantes_set = set(f.lower() for f in faltantes)

    # Buscar recursivamente
    for root, dirs, files in os.walk(origen):
        for file in files:
            if file.lower() in faltantes_set:
                encontrados[file] = Path(root) / file

    print(f"  → {len(encontrados)} encontradas localmente", flush=True)
    return encontrados


def copiar_respaldo(encontrados: dict[str, Path], destino: Path) -> None:
    """
    Copia archivos encontrados a carpeta respaldo.
    """
    print(f"Copiando {len(encontrados)} fotos a '{destino}'...", flush=True)
    destino.mkdir(parents=True, exist_ok=True)

    for nombre, path_origen in encontrados.items():
        path_destino = destino / nombre
        shutil.copy2(path_origen, path_destino)

    print(f"  ✅ {len(encontrados)} fotos copiadas a respaldo", flush=True)


def subir_storage(cfg: Config, encontrados: dict[str, Path]) -> list[dict]:
    """
    Sube archivos a Supabase Storage bucket 'productos'.
    Retorna lista de resultados {nombre, success, error}.
    """
    print(f"Subiendo {len(encontrados)} fotos a Storage...", flush=True)
    resultados: list[dict] = []

    for i, (nombre, path) in enumerate(encontrados.items(), 1):
        print(f"  [{i}/{len(encontrados)}] Subiendo {nombre}...", flush=True)

        mime_type, _ = mimetypes.guess_type(nombre)
        if not mime_type:
            mime_type = "image/jpeg"

        url = f"{cfg.supabase_url}/storage/v1/object/{BUCKET}/{quote(nombre)}"
        h = headers(cfg, {
            "Content-Type": mime_type,
            "x-upsert": "false",  # No sobreescribir existentes
        })

        try:
            with open(path, "rb") as f:
                data = f.read()

            res = requests.post(url, data=data, headers=h, timeout=120)

            if res.status_code == 200:
                resultados.append({"nombre": nombre, "success": True, "error": None})
                print(f"    ✅ OK", flush=True)
            else:
                error = f"HTTP {res.status_code}: {res.text}"
                resultados.append({"nombre": nombre, "success": False, "error": error})
                print(f"    ❌ {error}", flush=True)

        except Exception as e:
            error = str(e)
            resultados.append({"nombre": nombre, "success": False, "error": error})
            print(f"    ❌ {error}", flush=True)

    exitosos = sum(1 for r in resultados if r["success"])
    print(f"\n  ✅ {exitosos}/{len(encontrados)} fotos subidas exitosamente", flush=True)

    return resultados


def generar_reportes(
    plan: FotoPlan,
    upload_results: list[dict] | None,
    output_dir: Path
) -> None:
    """
    Genera CSVs de auditoría.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nGenerando reportes en '{output_dir}'...", flush=True)

    # 1. Imágenes en BD
    with open(output_dir / "imagenes_db.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["imagen_nombre"])
        for img in sorted(plan.imagenes_db):
            writer.writerow([img])

    # 2. Duplicados en Storage
    with open(output_dir / "storage_duplicados.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["archivo_storage"])
        for dup in plan.storage_duplicates:
            writer.writerow([dup])

    # 3. Faltantes en Storage
    with open(output_dir / "faltantes_storage.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["imagen_faltante"])
        for falt in sorted(plan.faltantes_storage):
            writer.writerow([falt])

    # 4. Encontrados localmente
    with open(output_dir / "encontrados_local.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["imagen", "path_origen"])
        for nombre, path in sorted(plan.encontrados_local.items()):
            writer.writerow([nombre, str(path)])

    # 5. Faltantes localmente
    with open(output_dir / "faltantes_local.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["imagen_no_encontrada"])
        for falt in sorted(plan.faltantes_local):
            writer.writerow([falt])

    # 6. Resultado upload
    if upload_results:
        with open(output_dir / "resultado_upload.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["imagen", "subida", "error"])
            for r in upload_results:
                writer.writerow([r["nombre"], "SI" if r["success"] else "NO", r["error"] or ""])

    print(f"  ✅ Reportes generados", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Buscador de fotos RETAIL")
    parser.add_argument("--dry-run", action="store_true", help="No subir a Storage, solo diagnóstico")
    parser.add_argument("--origen", type=str, default=r"\\10.18.3.1\home\img_art",
                        help="Carpeta origen donde buscar fotos (default: \\\\10.18.3.1\\home\\img_art)")
    parser.add_argument("--respaldo", type=str, default=r"C:\Users\hecto\Documents\Prg_locales\proyectos\imagenes",
                        help="Carpeta respaldo donde copiar fotos (default: C:\\Users\\hecto\\Documents\\Prg_locales\\proyectos\\imagenes)")
    parser.add_argument("--auto", action="store_true", help="Modo automático: usa rutas por defecto sin ventanas")
    args = parser.parse_args()

    print("\n" + "="*70)
    print("BUSCADOR DE FOTOS RETAIL")
    print("Fuente: registro_st_vt_rc_reposicion (columna imagen_nombre)")
    print("Destino: Supabase Storage bucket 'productos'")
    print("="*70 + "\n")

    # 1. Config
    cfg = read_config(dry_run=args.dry_run)

    # 2. Leer imágenes en BD (RETAIL)
    imagenes_db = fetch_imagenes_retail_db(cfg)
    if not imagenes_db:
        print("\n⚠️  No se encontraron imágenes en registro_st_vt_rc_reposicion")
        print("Verifica que la tabla tenga datos y columna 'imagen_nombre' poblada")
        return

    # 3. Listar Storage
    storage_files = fetch_storage_files(cfg)

    # 4. Detectar duplicados
    duplicates = duplicate_files(storage_files)
    if duplicates:
        print(f"\n⚠️  {len(duplicates)} duplicados detectados en Storage (ej: foto (1).jpg)")

    # 5. Calcular faltantes
    faltantes_storage = sorted(imagenes_db - storage_files)
    print(f"\n📊 Resumen:")
    print(f"  - Imágenes en BD: {len(imagenes_db)}")
    print(f"  - Archivos en Storage: {len(storage_files)}")
    print(f"  - Faltantes en Storage: {len(faltantes_storage)}")

    if not faltantes_storage:
        print("\n✅ Todas las imágenes de Retail ya están en Storage!")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path.cwd() / "diagnostico_fotos_retail" / timestamp
        plan = FotoPlan(
            imagenes_db=imagenes_db,
            storage_files=storage_files,
            storage_duplicates=duplicates,
            faltantes_storage=[],
            encontrados_local={},
            faltantes_local=[],
        )
        generar_reportes(plan, None, output_dir)
        return

    # 6. Pedir carpeta origen
    print(f"\n🔍 Buscaré {len(faltantes_storage)} fotos faltantes")

    if args.auto:
        # Modo automático: usar rutas por defecto
        origen = Path(args.origen)
        print(f"Modo AUTO - Carpeta ORIGEN: {origen}")

        if not origen.exists():
            print(f"❌ ERROR: Carpeta origen no existe o no es accesible: {origen}")
            print("Verifica la conexión a la red \\\\10.18.3.1")
            return
    else:
        # Modo interactivo: pedir con ventana
        if tk is None:
            print("\n❌ tkinter no disponible. Usa --auto para modo automático.")
            print("   python tools\\buscador_de_fotos_retail.py --auto")
            return

        print("Seleccioná carpeta ORIGEN donde buscar las fotos...")
        print(f"(Default sugerido: {args.origen})")

        origen = ask_folder("Carpeta ORIGEN - Buscar fotos aquí")
        if not origen:
            print("❌ Cancelado - no se seleccionó carpeta origen")
            return

    # 7. Buscar fotos localmente
    encontrados = buscar_fotos_local(faltantes_storage, origen)
    faltantes_local = sorted(set(faltantes_storage) - set(encontrados.keys()))

    if faltantes_local:
        print(f"\n⚠️  {len(faltantes_local)} fotos NO encontradas localmente")

    if not encontrados:
        print("\n❌ No se encontró ninguna foto faltante en la carpeta origen")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path.cwd() / "diagnostico_fotos_retail" / timestamp
        plan = FotoPlan(
            imagenes_db=imagenes_db,
            storage_files=storage_files,
            storage_duplicates=duplicates,
            faltantes_storage=faltantes_storage,
            encontrados_local={},
            faltantes_local=faltantes_local,
        )
        generar_reportes(plan, None, output_dir)
        return

    # 8. Pedir carpeta respaldo
    print(f"\n📋 Encontré {len(encontrados)} fotos")

    if args.auto:
        # Modo automático: usar ruta por defecto
        respaldo = Path(args.respaldo)
        print(f"Modo AUTO - Carpeta RESPALDO: {respaldo}")

        # Crear si no existe
        respaldo.mkdir(parents=True, exist_ok=True)
    else:
        # Modo interactivo: pedir con ventana
        print("Seleccioná carpeta RESPALDO donde copiarlas antes de subir...")
        print(f"(Default sugerido: {args.respaldo})")

        respaldo = ask_folder("Carpeta RESPALDO - Copiar fotos aquí")
        if not respaldo:
            print("❌ Cancelado - no se seleccionó carpeta respaldo")
            return

    # 9. Copiar a respaldo
    copiar_respaldo(encontrados, respaldo)

    # 10. Preguntar si subir
    upload_results = None
    if not cfg.dry_run:
        if args.auto:
            # Modo automático: NO subir por defecto (solo copiar)
            print("\n⏭️  Modo AUTO: Fotos copiadas a respaldo, NO se suben a Storage")
            print(f"   Para subir, ejecuta sin --auto o usa --dry-run=false")
        else:
            # Modo interactivo: preguntar
            subir = ask_yes_no(
                "Subir a Supabase Storage?",
                f"¿Subir {len(encontrados)} fotos a bucket 'productos'?\n\n"
                f"Ya están respaldadas en:\n{respaldo}"
            )

            if subir:
                upload_results = subir_storage(cfg, encontrados)
            else:
                print("\n⏭️  Upload omitido (usuario canceló)")
    else:
        print("\n⏭️  Modo --dry-run: NO se suben fotos")

    # 11. Generar reportes
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path.cwd() / "diagnostico_fotos_retail" / timestamp

    plan = FotoPlan(
        imagenes_db=imagenes_db,
        storage_files=storage_files,
        storage_duplicates=duplicates,
        faltantes_storage=faltantes_storage,
        encontrados_local=encontrados,
        faltantes_local=faltantes_local,
    )

    generar_reportes(plan, upload_results, output_dir)

    print("\n" + "="*70)
    print("✅ PROCESO COMPLETADO")
    print(f"📁 Reportes en: {output_dir}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
