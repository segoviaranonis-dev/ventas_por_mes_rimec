"""
buscador_de_fotos.py

Herramienta auxiliar para poblar Supabase Storage/bucket `productos` desde las
imagenes referenciadas en `registro_ventas_general_v2`.

No forma parte del runtime Nexus. Es una herramienta de administracion.

Flujo:
1. Lee imagenes unicas de `registro_ventas_general_v2` con `id_tipo = 1`.
2. Lista archivos actuales del bucket `productos`.
3. Detecta duplicados tipo "archivo (1).jpg".
4. Calcula faltantes.
5. Pide carpeta origen y carpeta respaldo via ventana.
6. Copia faltantes encontrados a respaldo.
7. Pregunta si subir faltantes a Supabase Storage.

Requisitos:
- Python 3.11+
- requests
- Variables de entorno o .env.local:
  SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY / SERVICE_ROLE_KEY / NEXT_PUBLIC_SUPABASE_ANON_KEY

Uso:
  python tools/buscador_de_fotos.py

Opcional:
  python tools/buscador_de_fotos.py --dry-run
  python tools/buscador_de_fotos.py --tipo 1
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
DEFAULT_TIPO_ID = 1
PAGE_SIZE = 1000
DUPLICATE_RE = re.compile(r"\s\(\d+\)(?=\.[^.]+$)", re.IGNORECASE)


@dataclass
class Config:
    supabase_url: str
    key: str
    tipo_id: int
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


def read_config(tipo_id: int, dry_run: bool) -> Config:
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
    return Config(norm_url(url), key, tipo_id, dry_run)


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

    thread = threading.Thread(target=run, name="buscador-fotos-heartbeat", daemon=True)
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
    if not name or name.lower() in {"none", "nan", "null"}:
        return None
    if DUPLICATE_RE.search(name):
        # Las imagenes "(1)" no son nombre canonico; se registran como duplicado.
        return name
    return name


def fetch_imagenes_db(cfg: Config) -> set[str]:
    print(f"Consultando registro_ventas_general_v2 id_tipo={cfg.tipo_id}...", flush=True)
    url = f"{cfg.supabase_url}/rest/v1/registro_ventas_general_v2"
    result: set[str] = set()
    offset = 0
    while True:
        params = {
            "select": "imagen",
            "id_tipo": f"eq.{cfg.tipo_id}",
            "imagen": "not.is.null",
            "order": "imagen.asc",
        }
        h = headers(cfg, {"Range": f"{offset}-{offset + PAGE_SIZE - 1}"})
        res = requests.get(url, params=params, headers=h, timeout=60)
        if res.status_code >= 400:
            raise RuntimeError(f"PostgREST error {res.status_code}")  # pragma: allowlist secret
        rows = res.json()
        for row in rows:
            name = clean_image_name(row.get("imagen"))
            if name:
                result.add(name)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
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
        raise RuntimeError(f"Storage list error {res.status_code}")
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
            # Bucket productos es plano en nuestra convencion. Si hay carpetas,
            # quedan fuera de esta primera herramienta auxiliar.
            files.add(str(name).strip())
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return files


def duplicate_files(storage_files: Iterable[str]) -> list[str]:
    return sorted([f for f in storage_files if DUPLICATE_RE.search(f)])


def choose_directory(title: str) -> Path:
    if tk is None or filedialog is None:
        raw = input(f"{title}: pega ruta de carpeta: ").strip().strip('"')
        return Path(raw)
    root = tk.Tk()
    root.withdraw()
    selected = filedialog.askdirectory(title=title)
    root.destroy()
    if not selected:
        raise SystemExit("Operacion cancelada: no se selecciono carpeta.")
    return Path(selected)


def ask_yes_no(title: str, msg: str) -> bool:
    if tk is None or messagebox is None:
        return input(f"{title}: {msg} [s/N] ").strip().lower().startswith("s")
    root = tk.Tk()
    root.withdraw()
    ans = messagebox.askyesno(title, msg)
    root.destroy()
    return bool(ans)


def index_local_images(origin: Path) -> dict[str, list[Path]]:
    print(f"Indexando imagenes en: {origin}", flush=True)
    if not origin.exists() or not origin.is_dir():
        raise SystemExit(f"Carpeta origen invalida: {origin}")
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    index: dict[str, list[Path]] = {}
    for path in origin.rglob("*"):
        if path.is_file() and path.suffix.lower() in exts:
            index.setdefault(path.name, []).append(path)
    return index


def copy_to_backup(found: dict[str, Path], backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name, src in found.items():
        dst = backup_dir / name
        if not dst.exists():
            shutil.copy2(src, dst)


def upload_file(cfg: Config, path: Path, dest_name: str) -> tuple[bool, str]:
    content_type = mimetypes.guess_type(dest_name)[0] or "application/octet-stream"
    encoded = quote(dest_name, safe="")
    url = f"{cfg.supabase_url}/storage/v1/object/{BUCKET}/{encoded}"
    with path.open("rb") as fh:
        res = requests.post(
            url,
            data=fh,
            headers=headers(cfg, {"Content-Type": content_type, "x-upsert": "false"}),
            timeout=90,
        )
    if res.status_code in (200, 201):
        return True, "uploaded"
    if res.status_code == 409:
        return True, "already_exists"
    return False, f"{res.status_code}: {res.text[:300]}"


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Busca y sube fotos faltantes al bucket productos.")
    parser.add_argument("--tipo", type=int, default=DEFAULT_TIPO_ID, help="id_tipo a consultar. Default: 1")
    parser.add_argument("--dry-run", action="store_true", help="No sube archivos; solo genera reportes y respaldo.")
    args = parser.parse_args()

    cfg = read_config(tipo_id=args.tipo, dry_run=args.dry_run)
    status = {"msg": "iniciando"}
    hb_stop, hb_thread = start_heartbeat(lambda: status["msg"])

    try:
        status["msg"] = "leyendo imagenes desde registro_ventas_general_v2"
        imagenes_db = fetch_imagenes_db(cfg)

        status["msg"] = "listando bucket productos"
        storage_files = fetch_storage_files(cfg)
        storage_dups = duplicate_files(storage_files)

        canonical_storage = {f for f in storage_files if not DUPLICATE_RE.search(f)}
        faltantes_storage = sorted([img for img in imagenes_db if img not in canonical_storage])

        print("\nRESUMEN INICIAL", flush=True)
        print(f"- imagenes unicas en ventas id_tipo={cfg.tipo_id}: {len(imagenes_db):,}", flush=True)
        print(f"- archivos en Storage productos: {len(storage_files):,}", flush=True)
        print(f"- duplicados en Storage tipo '(1)': {len(storage_dups):,}", flush=True)
        print(f"- faltantes contra Storage: {len(faltantes_storage):,}", flush=True)

        out_base = Path.cwd() / "diagnostico_fotos"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = out_base / ts
        write_csv(report_dir / "imagenes_db.csv", [{"imagen": x} for x in sorted(imagenes_db)])
        write_csv(report_dir / "storage_duplicados.csv", [{"archivo": x} for x in storage_dups])
        write_csv(report_dir / "faltantes_storage.csv", [{"imagen": x} for x in faltantes_storage])

        if not faltantes_storage:
            print(f"\nNo faltan fotos. Reportes en: {report_dir}", flush=True)
            return 0

        origin_dir = choose_directory("Selecciona carpeta DONDE BUSCAR imagenes faltantes")
        backup_dir = choose_directory("Selecciona carpeta RESPALDO para copiar faltantes encontrados")

        status["msg"] = "indexando carpeta local de imagenes"
        local_index = index_local_images(origin_dir)

        encontrados: dict[str, Path] = {}
        faltantes_local: list[str] = []
        duplicados_local: list[dict] = []
        for name in faltantes_storage:
            matches = local_index.get(name, [])
            if matches:
                encontrados[name] = matches[0]
                if len(matches) > 1:
                    duplicados_local.append({
                        "imagen": name,
                        "cantidad": len(matches),
                        "rutas": " | ".join(str(p) for p in matches[:5]),
                    })
            else:
                faltantes_local.append(name)

        status["msg"] = "copiando respaldo local"
        copy_to_backup(encontrados, backup_dir)

        write_csv(
            report_dir / "encontrados_local.csv",
            [{"imagen": k, "ruta": str(v)} for k, v in sorted(encontrados.items())],
        )
        write_csv(report_dir / "faltantes_local.csv", [{"imagen": x} for x in faltantes_local])
        write_csv(report_dir / "duplicados_local.csv", duplicados_local)

        print("\nRESUMEN LOCAL", flush=True)
        print(f"- encontrados en carpeta origen: {len(encontrados):,}", flush=True)
        print(f"- no encontrados localmente: {len(faltantes_local):,}", flush=True)
        print(f"- respaldo copiado a: {backup_dir}", flush=True)
        print(f"- reportes CSV en: {report_dir}", flush=True)

        if cfg.dry_run:
            print("\nDRY RUN activo: no se suben archivos.", flush=True)
            return 0

        if not ask_yes_no(
            "Subir a Supabase",
            f"Se encontraron {len(encontrados):,} fotos faltantes. ¿Subirlas al bucket '{BUCKET}'?",
        ):
            print("Subida cancelada por usuario. Respaldo y CSV generados.", flush=True)
            return 0

        status["msg"] = "subiendo fotos faltantes a Supabase Storage"
        upload_rows: list[dict] = []
        ok_count = 0
        fail_count = 0
        for idx, (name, path) in enumerate(sorted(encontrados.items()), 1):
            status["msg"] = f"subiendo {idx}/{len(encontrados)}: {name}"
            ok, msg = upload_file(cfg, path, name)
            upload_rows.append({"imagen": name, "ruta": str(path), "ok": ok, "resultado": msg})
            if ok:
                ok_count += 1
            else:
                fail_count += 1
                print(f"[WARN] Fallo subiendo {name}: {msg}", flush=True)

        write_csv(report_dir / "resultado_upload.csv", upload_rows)
        print("\nRESULTADO SUBIDA", flush=True)
        print(f"- subidas/ya existentes OK: {ok_count:,}", flush=True)
        print(f"- fallidas: {fail_count:,}", flush=True)
        print(f"- respaldo: {backup_dir}", flush=True)
        print(f"- reportes: {report_dir}", flush=True)
        return 0 if fail_count == 0 else 2
    finally:
        stop_heartbeat(hb_stop, hb_thread)


if __name__ == "__main__":
    raise SystemExit(main())
