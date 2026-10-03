#!/usr/bin/env python3
"""Bundle the reviewed training helpers so the notebook works before a Git push."""
import base64
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "training/prepare_two_stage_data.py", "training/train_two_stage.py",
    "training/maturity_data.py", "training/requirements.txt",
    "scripts/download_public_datasets.sh", "scripts/download_orchard_datasets.py",
    "scripts/download_dragon_black_rot.py",
]


def main():
    payload = json.dumps({name: (ROOT / name).read_text() for name in FILES}, sort_keys=True).encode()
    encoded = base64.b64encode(gzip.compress(payload, mtime=0)).decode()
    checksum = hashlib.sha256(payload).hexdigest()
    code = f'''# STEP 1 — Restore the included training code and install dependencies
import base64, gzip, hashlib, json, os, subprocess, sys
from pathlib import Path
REPO = '/content/fruit_detection_maturity_v2'
EMBEDDED_HELPERS_B64 = {encoded!r}
HELPERS_SHA256 = {checksum!r}
payload = gzip.decompress(base64.b64decode(EMBEDDED_HELPERS_B64))
assert hashlib.sha256(payload).hexdigest() == HELPERS_SHA256, 'Training helper bundle checksum failed'
for filename, contents in json.loads(payload).items():
    destination = Path(REPO) / filename
    assert destination.resolve().is_relative_to(Path(REPO).resolve()), filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(contents, encoding='utf-8')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-r', f'{{REPO}}/training/requirements.txt'], check=True)
import torch
assert torch.cuda.is_available(), 'Hãy bật Runtime > Change runtime type > T4 GPU'
print(torch.cuda.get_device_name(0))
print('Included maturity_v2 training helpers restored; no GitHub sync required.')
'''
    path = ROOT / "training/train_two_stage_colab.ipynb"
    notebook = json.loads(path.read_text())
    cell = next(cell for cell in notebook["cells"] if "".join(cell["source"]).startswith("# STEP 1"))
    cell["source"] = code.splitlines(keepends=True)
    cell["outputs"] = []
    cell["execution_count"] = None
    path.write_text(json.dumps(notebook, indent=2, ensure_ascii=False) + "\n")
    print(f"Embedded {len(FILES)} reviewed helper files ({len(encoded)} base64 characters).")


if __name__ == "__main__":
    main()
