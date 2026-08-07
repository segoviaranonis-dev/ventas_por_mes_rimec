#!/usr/bin/env python3
"""
Imagen de portada — mismo protocolo de inserción que producto (flat+sm/md/lg → Supabase),
ruta dedicada productos/portada/ para no mezclar con SKU.

Keyword Director: **imagen de portada**
Ley madre: LEY_UNIVERSAL_IMAGENES_PRODUCTO.md · anexo CHUSAR_IMAGEN_DE_PORTADA

Uso:
  python tools/subir_portadas_marca_batch.py --carpeta "C:\\Users\\hecto\\Nexus_Core\\bazzar-web"
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from PIL import Image

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from subir_miniaturas_supabase import (  # noqa: E402
    BUCKET,
    headers,
    load_local_env,
    read_config,
)

# Anchos máximos (banner panorámico — NO canvas cuadrado)
TIER_MAX_W = {
    "flat": 2400,
    "lg": 1920,
    "md": 1200,
    "sm": 640,
}

# archivo local → stem Storage (sin extensión)
MAPA_ARCHIVOS = {
    "vizzano.png": "vizzano",
    "beira-rio.png": "beira-rio",
    "modare.png": "modare",
    "moleca.png": "moleca",
    "molekinha.png": "molekinha",
    "molekinho.png": "molekinho",
    "activitta.png": "actvitta",
    "br-sport.png": "br-sport",
    # Reserva · Director pasará archivo
    "kyly.png": "kyly",
    "milon.png": "milon",
}


def norm_url(url: str) -> str:
    return url.strip().rstrip("/")


def public_url(base: str, stem: str, tier: str | None) -> str:
    if tier is None or tier == "flat":
        path = f"portada/{stem}.jpg"
    else:
        path = f"portada/{tier}/{stem}.jpg"
    return f"{norm_url(base)}/storage/v1/object/public/{BUCKET}/{path}"


def head_ok(url: str, key: str, retries: int = 3) -> bool:
    import requests

    for attempt in range(retries):
        try:
            r = requests.head(url, headers=headers(key), timeout=30, allow_redirects=True)
            if r.status_code == 200:
                return True
            # algunos buckets responden GET mejor
            r2 = requests.get(url, headers=headers(key), timeout=30, stream=True)
            ok = r2.status_code == 200
            r2.close()
            if ok:
                return True
        except Exception:
            pass
        time.sleep(1.0 * (attempt + 1))
    return False


def resize_banner(img: Image.Image, max_w: int) -> Image.Image:
    rgb = img.convert("RGB")
    if rgb.width <= max_w:
        return rgb
    h = int(round(rgb.height * (max_w / rgb.width)))
    return rgb.resize((max_w, h), Image.Resampling.LANCZOS)


def to_jpeg_bytes(img: Image.Image, quality: int = 85) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def upload_bytes(
    data: bytes,
    object_path: str,
    base: str,
    key: str,
) -> tuple[bool, str | None]:
    import requests

    url = f"{norm_url(base)}/storage/v1/object/{BUCKET}/{quote(object_path, safe='/')}"
    try:
        r = requests.post(
            url,
            headers=headers(key, {"Content-Type": "image/jpeg", "x-upsert": "true"}),
            data=data,
            timeout=180,
        )
        if r.status_code in (200, 201):
            return True, None
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)


def process_one(src: Path, stem: str, base: str, key: str) -> dict:
    raw = Image.open(src)
    result = {
        "stem": stem,
        "source": str(src),
        "src_wh": [raw.width, raw.height],
        "tiers": {},
        "verify": {},
        "ok": True,
    }
    for tier, max_w in TIER_MAX_W.items():
        banner = resize_banner(raw, max_w)
        data = to_jpeg_bytes(banner)
        if tier == "flat":
            object_path = f"portada/{stem}.jpg"
        else:
            object_path = f"portada/{tier}/{stem}.jpg"
        ok, err = upload_bytes(data, object_path, base, key)
        result["tiers"][tier] = {
            "wh": [banner.width, banner.height],
            "bytes": len(data),
            "path": object_path,
            "upload_ok": ok,
            "error": err,
        }
        if not ok:
            result["ok"] = False
        url = public_url(base, stem, None if tier == "flat" else tier)
        v = head_ok(url, key)
        result["verify"][tier] = {"url": url, "head_ok": v}
        if not v:
            result["ok"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--carpeta",
        default=str(Path(r"C:\Users\hecto\Nexus_Core\bazzar-web")),
    )
    args = parser.parse_args()
    carpeta = Path(args.carpeta)
    load_local_env()
    base, key = read_config()

    rows = []
    for fname, stem in MAPA_ARCHIVOS.items():
        src = carpeta / fname
        if not src.exists():
            print(f"SKIP missing {src}", flush=True)
            rows.append({"stem": stem, "ok": False, "error": "missing"})
            continue
        print(f"→ {fname} → portada/{stem}.jpg …", flush=True)
        row = process_one(src, stem, base, key)
        status = "PASS" if row["ok"] else "FAIL"
        print(f"  {status} {stem}", flush=True)
        rows.append(row)

    evid = Path(__file__).resolve().parents[2] / "ot" / "en_curso"
    evid.mkdir(parents=True, exist_ok=True)
    out = evid / f"EVIDENCIA-PORTADAS-MARCA-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    payload = {
        "keyword": "imagen de portada",
        "bucket": BUCKET,
        "prefix": "portada/",
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "pass": sum(1 for r in rows if r.get("ok")),
        "total": len(rows),
        "rows": rows,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Evidencia: {out}", flush=True)
    print(f"Resumen: {payload['pass']}/{payload['total']} PASS", flush=True)
    return 0 if payload["pass"] == payload["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
