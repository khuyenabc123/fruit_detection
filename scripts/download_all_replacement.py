#!/usr/bin/env python3
"""Orchestrate all replacement public dataset downloads for Maturity V2.

This script replaces the old dependency on mango_dataset.zip / dragonfruit_dataset.zip
with legitimate public datasets, as required by Task A and B.

It calls:
- download_public_datasets.sh two-stage-curated (MangoYOLO, mango_on_tree)
- download_mango_datasets.py (Mendeley growth 5snwpzdtzs + ripening mm8g66d7rc)
- download_dragon_maturity.py (Mendeley 2jpzbx8tm6, unripe/ripe)
- download_orchard_datasets.py (orchard backgrounds, detector only)
- download_dragon_black_rot.py (rotten, CC BY 4.0)
- download_negatives.py (Roboflow negatives, if ROBOFLOW_API_KEY set) + download_negative_public.py (Wikimedia fallback)

All archives are cached on Drive (PUBLIC_DATA_RAW_DIR) and extracted to local fast storage.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def run(cmd, env=None, cwd=REPO):
    print(f"\n>>> {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True, env=env, cwd=cwd)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("data/external/extracted"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/external/raw"))
    parser.add_argument("--orchard-cache", type=Path, default=None, help="Separate cache for orchard/black_rot (e.g., Drive orchard_cache)")
    parser.add_argument("--skip-negatives", action="store_true", help="Skip negative images")
    args = parser.parse_args()

    output_root = args.output_root.resolve()
    cache_dir = args.cache_dir.resolve()
    orchard_cache = args.orchard_cache.resolve() if args.orchard_cache else cache_dir

    output_root.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    orchard_cache.mkdir(parents=True, exist_ok=True)

    # Install deps for RAR
    try:
        import rarfile  # noqa
    except ImportError:
        print("[setup] Installing rarfile, patool, requests, Pillow")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "rarfile", "patool", "requests", "Pillow"], check=True)

    # 1. Public YOLO datasets
    print("\n=== 1/6 Public YOLO datasets (two-stage-curated) ===")
    env = os.environ.copy()
    env["PUBLIC_DATA_RAW_DIR"] = str(cache_dir)
    env["PUBLIC_DATA_EXTRACTED_DIR"] = str(output_root)
    run(["bash", str(REPO / "scripts/download_public_datasets.sh"), "two-stage-curated"], env=env)

    # 2. Mango replacement
    print("\n=== 2/6 Mango growth + ripening (replacement for mango_dataset.zip) ===")
    run([sys.executable, str(REPO / "scripts/download_mango_datasets.py"),
         "--output-root", str(output_root),
         "--cache-dir", str(cache_dir)])

    # 3. Dragon maturity
    print("\n=== 3/6 Dragon maturity (unripe/ripe) ===")
    run([sys.executable, str(REPO / "scripts/download_dragon_maturity.py"),
         "--output-root", str(output_root),
         "--cache-dir", str(cache_dir)])

    # 4. Orchard
    print("\n=== 4/6 Orchard datasets (detector only) ===")
    run([sys.executable, str(REPO / "scripts/download_orchard_datasets.py"),
         "--output-root", str(output_root),
         "--cache-dir", str(orchard_cache)])

    # 5. Black rot (rotten)
    print("\n=== 5/6 Black rot (rotten) ===")
    run([sys.executable, str(REPO / "scripts/download_dragon_black_rot.py"),
         "--output-root", str(output_root),
         "--cache-dir", str(orchard_cache)])

    # 6. Negatives
    if not args.skip_negatives:
        print("\n=== 6/6 Negative images (other fruit + flowers) ===")
        # Try Roboflow
        try:
            run([sys.executable, str(REPO / "scripts/download_negatives.py"),
                 "--output-root", str(output_root),
                 "--skip-if-no-key"])
        except subprocess.CalledProcessError as e:
            print(f"[warn] Roboflow negatives failed: {e}")
        # Public fallback
        try:
            run([sys.executable, str(REPO / "scripts/download_negative_public.py"),
                 "--output-root", str(output_root),
                 "--cache-dir", str(cache_dir)])
        except subprocess.CalledProcessError as e:
            print(f"[warn] Public negatives failed: {e}, continuing with orchard backgrounds")

    print("\n=== All downloads complete ===")
    for p in sorted(output_root.rglob("import_report.json")):
        print(p)
    for p in sorted(output_root.rglob("*.import_report.json")):
        print(p)

if __name__ == "__main__":
    main()
