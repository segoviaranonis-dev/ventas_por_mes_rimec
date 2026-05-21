"""Ejecuta purga y escribe resultado en ot/_ultima_purga.txt"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "ot" / "_ultima_purga.txt"
sys.path.insert(0, str(ROOT))

from modules.rimec_engine.logic import purgar_solo_eventos_precio  # noqa: E402

lines = ["Purga: solo eventos precio (pilares intactos)\n"]
ok, stats = purgar_solo_eventos_precio()
if ok:
    lines.append("OK\n")
    for k, v in stats.items():
        lines.append(f"  {k}: {v}\n")
else:
    lines.append(f"ERROR: {stats}\n")
OUT.write_text("".join(lines), encoding="utf-8")
print("".join(lines))
