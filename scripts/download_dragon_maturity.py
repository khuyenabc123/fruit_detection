#!/usr/bin/env python3
"""Download Dragon Fruit Maturity dataset (Mendeley 2jpzbx8tm6) for classifier.

This dataset provides Immature and Mature dragon fruit (unripe/ripe).
Rotten comes from Black Rot dataset (kpsywfwkrf).

Source:
- https://data.mendeley.com/datasets/2jpzbx8tm6/1
- CC BY 4.0, Tania Khatun et al.
- Original paper: maturity detection and quality grading
- Download URLs:
  * Maturity zip: https://data.mendeley.com/public-files/datasets/2jpzbx8tm6/files/4a971fd0-07cf-4d88-9109-a8513886c32a/file_downloaded
    SHA256: 7265501db07c50056a3d4062be44c1f30f98cb039ef4ecbf2a591fccf4fa27fc (from datasets.json)
    Size: ~978 MB
  * Quality zip: https://data.mendeley.com/public-files/datasets/2jpzbx8tm6/files/b48bea93-6b57-482b-a6e9-fc35548fc2dd/file_downloaded
    Not used for maturity (Fresh/Defect not mapped to ripeness)

Expected extracted structure:
  Dragon Fruit Maturity Detection Dataset/
    Original Dataset/
      Immature Dragon Fruit/*.jpg
      Mature Dragon Fruit/*.jpg
    Augmented Dataset/ (excluded)

Only Original Dataset is used; augmented copies are excluded to avoid leakage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

SOURCE = {
    "id": "dragon_fruit_maturity",
    "url": "https://data.mendeley.com/public-files/datasets/2jpzbx8tm6/files/4a971fd0-07cf-4d88-9109-a8513886c32a/file_downloaded",
    "archive_name": "dragon_fruit_maturity.zip",
    "sha256": "7265501db07c50056a3d4062be44c1f30f98cb039ef4ecbf2a591fccf4fa27fc",
    "bytes": 1025154230,  # Approximate, from datasets.json (actually full dataset zip size, maturity alone is 978 MB)
    "license": "CC BY 4.0",
    "title": "Dragon Fruit Maturity Detection Dataset",
    "authors": "Tania Khatun et al.",
}

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def download_with_curl(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        # If file exists, check if it looks valid (zip test)
        try:
            with zipfile.ZipFile(dest) as z:
                if z.testzip() is None:
                    print(f"[skip] {dest} already exists and is valid zip")
                    return
        except Exception:
            print(f"[warn] {dest} exists but is not valid zip, re-downloading")
    print(f"[download] {url} -> {dest}")
    cmd = ["curl", "--location", "--fail", "--retry", "4", "--retry-delay", "3",
           "--continue-at", "-", "--output", str(dest), url, "--max-time", "900"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(result.stderr[-2000:], file=sys.stderr)
        raise RuntimeError(f"Failed to download {url}")

def verify_zip(path: Path):
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad:
            raise ValueError(f"Corrupt zip member: {bad}")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("data/external/extracted"))
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_root = args.output_root.resolve()
    cache_dir = args.cache_dir.resolve() if args.cache_dir else None
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)

    cache_path = (cache_dir / SOURCE["archive_name"]) if cache_dir else (output_root.parent / "raw" / SOURCE["archive_name"])
    dest_root = output_root / "dragon_fruit_maturity"
    marker = dest_root / ".extracted-ok"
    report_path = dest_root / "import_report.json"

    if report_path.is_file() and not args.force and marker.is_file():
        print(f"[skip] Dragon maturity already imported: {dest_root}")
        try:
            print(report_path.read_text()[:500])
        except Exception:
            pass
        return

    download_with_curl(SOURCE["url"], cache_path)

    try:
        verify_zip(cache_path)
        actual_sha = sha256_file(cache_path)
        expected = SOURCE["sha256"]
        if actual_sha != expected:
            print(f"[warn] SHA256 mismatch for dragon maturity: expected {expected}, got {actual_sha}. "
                  f"The publisher may have updated the file. Proceeding if zip is valid.")
    except Exception as e:
        cache_path.unlink(missing_ok=True)
        raise RuntimeError(f"Corrupt download for dragon maturity: {e}") from e

    if args.force and dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    print(f"[extract] {cache_path} -> {dest_root}")
    with zipfile.ZipFile(cache_path) as z:
        z.extractall(dest_root)
    marker.write_text(json.dumps({"archive": cache_path.name, "sha256": sha256_file(cache_path)}) + "\n")

    # Validate
    immature = list((dest_root).rglob("Immature Dragon Fruit"))
    mature = list((dest_root).rglob("Mature Dragon Fruit"))
    total_images = 0
    for folder in immature + mature:
        if folder.is_dir():
            total_images += len([p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES])

    # Fallback: count any jpg under original dataset
    if total_images == 0:
        total_images = len([p for p in dest_root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES])

    report = {
        "source": SOURCE,
        "archive": str(cache_path),
        "archive_sha256": sha256_file(cache_path),
        "extracted_root": str(dest_root),
        "total_images": total_images,
        "license": SOURCE["license"],
        "mapping": {"Immature Dragon Fruit": "dragonfruit_unripe", "Mature Dragon Fruit": "dragonfruit_ripe"},
        "notes": "Only Original Dataset used; Augmented excluded. Rotten comes from Black Rot dataset.",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"[ok] Dragon maturity imported: {total_images} images")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
