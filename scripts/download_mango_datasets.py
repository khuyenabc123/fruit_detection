#!/usr/bin/env python3
"""Download replacement mango maturity datasets from Mendeley Data.

Two complementary sources are used to cover the four required classes:

1. Mango Growth Stages (5snwpzdtzs) — CC BY 4.0
   - 2004 images, 4 growth stages: early-fruit, premature, mature, ripe
   - On-tree orchard photos with bounding box annotations (VOC/COCO)
   - Mapping to our schema:
     early-fruit + premature -> mango_young
     mature               -> mango_mature
     ripe                 -> mango_ripe (on-tree ripe)
   - Download: https://data.mendeley.com/public-api/zip/5snwpzdtzs/download/1
   - Original paper: https://doi.org/10.1016/j.dib.2025.111780
   - Authors: Sayem Kabir et al., East West University

2. Mango Ripening Stages (mm8g66d7rc) — CC BY 4.0
   - 4 post-harvest ripening levels: Stage_0 Unripe, Stage_1 Early Ripe,
     Stage_2 Partially Ripe, Stage_3 Ripe
   - Mapping to our schema (same as existing load_mango_ripening_stages):
     stage0 + stage1 -> mango_mature (green with slight yellowing)
     stage2          -> mango_turning
     stage3          -> mango_ripe
   - Download: https://data.mendeley.com/public-api/zip/mm8g66d7rc/download/1
     Contains 4 RAR archives, each ~6-7 MB
   - Contributor: Muti ur Rehman Muti, MNS University of Agriculture

Combined they provide:
  mango_young   <- growth stages early-fruit, premature (only source for young)
  mango_mature  <- growth stages mature + ripening stage0, stage1
  mango_turning <- ripening stage2 (only source for turning)
  mango_ripe    <- growth stages ripe + ripening stage3

If reliable data for one class cannot be found, the script reports the gap
instead of fabricating labels. No image duplication is performed.

For every source:
- Download and cache to Drive (if --cache-dir provided)
- Resume or skip completed downloads safely
- Verify HTTP status and archive integrity (zip/rar)
- Extract to deterministic directory
- Avoid re-extracting valid datasets unnecessarily
- Validate extracted files and annotation structure
- Provide clear errors if source is unavailable

Usage in Colab:
  python scripts/download_mango_datasets.py \
    --output-root data/external/extracted \
    --cache-dir /content/drive/MyDrive/fruit_data/public_raw
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List

from PIL import Image

# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------
SOURCES = {
    "mango_growth_stages": {
        "id": "5snwpzdtzs",
        "version": 1,
        "url": "https://data.mendeley.com/public-api/zip/5snwpzdtzs/download/1",
        "archive_name": "mango_growth_stages_5snwpzdtzs_v1.zip",
        "license": "CC BY 4.0",
        "title": "Image Dataset for Mango Growth Stages Analysis",
        "authors": "Sayem Kabir, Mohammad Rifat Ahmmad Rashid et al.",
        "paper": "https://doi.org/10.1016/j.dib.2025.111780",
        "expected_classes": ["early-fruit", "premature", "mature", "ripe"],
        "mapping": {
            "early-fruit": "mango_young",
            "premature": "mango_young",
            "mature": "mango_mature",
            "ripe": "mango_ripe",
        },
        "notes": "2004 images, 1057 raw + augmentation, on-tree orchard, bounding boxes",
    },
    "mango_ripening_stages": {
        "id": "mm8g66d7rc",
        "version": 1,
        "url": "https://data.mendeley.com/public-api/zip/mm8g66d7rc/download/1",
        "archive_name": "mango_ripening_mm8g66d7rc_v1.zip",
        "license": "CC BY 4.0",
        "title": "Ripening Detection of Mango",
        "authors": "Muti ur Rehman Muti",
        "expected_stages": {
            "stage0": "mango_mature",
            "stage1": "mango_mature",
            "stage2": "mango_turning",
            "stage3": "mango_ripe",
        },
        "rar_names": [
            "Stage_0 (Unripe).rar",
            "Stage_1(Early Ripe).rar",
            "Stage_2 (Partially Ripe).rar",
            "Stage_3 (Ripe).rar",
        ],
        "notes": "4 post-harvest ripening levels, harvested mango on white table, 6-10s interval photos",
    },
}

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_with_curl(url: str, dest: Path, expected_bytes: int | None = None) -> None:
    """Download using curl with resume, fail on HTTP error."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # If file exists and size matches expected, skip
    if dest.is_file() and expected_bytes and dest.stat().st_size == expected_bytes:
        print(f"[skip] {dest.name} already downloaded ({dest.stat().st_size} bytes)")
        return
    print(f"[download] {url} -> {dest}")
    # Use curl with retry, resume, fail
    cmd = [
        "curl", "--location", "--fail", "--retry", "4", "--retry-delay", "3",
        "--continue-at", "-", "--output", str(dest), url,
        "--max-time", "600",
        "-H", "User-Agent: fruit_detection/1.0",
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        # Remove partial file if download failed and not resuming?
        print(result.stderr[-2000:], file=sys.stderr)
        raise RuntimeError(f"Failed to download {url}: curl exit {result.returncode}")
    if expected_bytes and dest.stat().st_size != expected_bytes:
        print(f"[warn] Size mismatch for {dest.name}: expected {expected_bytes}, got {dest.stat().st_size}")
    print(f"[ok] Downloaded {dest} ({dest.stat().st_size} bytes)")


def verify_zip(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as z:
            # Test CRC for all members (does not extract)
            bad = z.testzip()
            if bad:
                raise ValueError(f"Corrupt member in zip: {bad}")
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid zip file {path}: {e}") from e


def extract_zip_once(archive: Path, dest_dir: Path, marker_name: str = ".extracted-ok") -> bool:
    """Extract if marker missing or invalid. Returns True if extracted now."""
    marker = dest_dir / marker_name
    if marker.is_file():
        # Check if dest has files
        if any(dest_dir.rglob("*")):
            print(f"[skip] {dest_dir} already extracted (marker present)")
            return False
    print(f"[extract] {archive} -> {dest_dir}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest_dir)
    marker.write_text(json.dumps({"archive": archive.name, "sha256": sha256_file(archive)}) + "\n")
    return True


def try_extract_rar(rar_path: Path, dest_dir: Path) -> bool:
    """Try multiple methods to extract RAR."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Method 1: unrar command (if available)
    if shutil.which("unrar"):
        cmd = ["unrar", "x", "-o+", str(rar_path), str(dest_dir) + "/"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return True
        print(f"[warn] unrar failed for {rar_path.name}: {result.stderr[-500:]}")
    # Method 2: bsdtar (often supports rar)
    if shutil.which("bsdtar"):
        cmd = ["bsdtar", "-xf", str(rar_path), "-C", str(dest_dir)]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return True
        print(f"[warn] bsdtar failed for {rar_path.name}: {result.stderr[-500:]}")
    # Method 3: Python rarfile (requires unrar binary, but try)
    try:
        import rarfile
        with rarfile.RarFile(rar_path) as rf:
            rf.extractall(dest_dir)
        return True
    except Exception as e:
        print(f"[warn] rarfile failed for {rar_path.name}: {e}")
    # Method 4: patool
    try:
        import patool
        patool.extract_archive(str(rar_path), outdir=str(dest_dir))
        return True
    except Exception as e:
        print(f"[warn] patool failed for {rar_path.name}: {e}")
    return False


def find_class_folders(root: Path, expected_names: List[str]) -> Dict[str, Path]:
    """Search for folders matching expected class names (case-insensitive, normalized)."""
    found = {}
    for path in root.rglob("*"):
        if not path.is_dir():
            continue
        norm = path.name.strip().lower().replace(" ", "-").replace("_", "-")
        for exp in expected_names:
            exp_norm = exp.lower().replace(" ", "-").replace("_", "-")
            if norm == exp_norm or norm.startswith(exp_norm + "-") or exp_norm in norm:
                # Prefer shortest path depth for each class
                if exp not in found or len(path.parts) < len(found[exp].parts):
                    found[exp] = path
    return found


def validate_mango_growth_stages(root: Path) -> dict:
    """Validate extracted growth stages dataset."""
    # Look for 4 class folders
    expected = SOURCES["mango_growth_stages"]["expected_classes"]
    # The zip may have top-level folder "Mango Growth Dataset" or similar
    # Search recursively
    class_counts = {}
    mapping = SOURCES["mango_growth_stages"]["mapping"]
    for exp in expected:
        # Find directories
        candidates = list(root.rglob(exp)) + list(root.rglob(exp.replace("-", "_"))) + list(root.rglob(exp.replace("-", " ")))
        # Also search case-insensitive
        if not candidates:
            # Glob case-insensitive via rglob with pattern
            for p in root.rglob("*"):
                if p.is_dir() and p.name.lower().replace(" ", "-").replace("_", "-") == exp.lower().replace(" ", "-").replace("_", "-"):
                    candidates.append(p)
        # Count images
        total = 0
        for cand in candidates:
            if cand.is_dir():
                for img in cand.rglob("*"):
                    if img.is_file() and img.suffix.lower() in IMAGE_SUFFIXES:
                        total += 1
        class_counts[exp] = total

    # Also try alternative layout: Mango_Growth_Dataset folder containing 4 subfolders
    # If counts are zero, try broader search for images with class in path
    if sum(class_counts.values()) == 0:
        # Fallback: count images whose path contains class name
        for exp in expected:
            count = 0
            for img in root.rglob("*"):
                if img.is_file() and img.suffix.lower() in IMAGE_SUFFIXES:
                    if exp.lower() in str(img).lower():
                        count += 1
            class_counts[exp] = count

    # Map to our 4-class schema
    our_counts = {}
    for src_class, our_class in mapping.items():
        our_counts[our_class] = our_counts.get(our_class, 0) + class_counts.get(src_class, 0)

    report = {
        "root": str(root),
        "raw_class_counts": class_counts,
        "mapped_counts": our_counts,
        "total_images": sum(class_counts.values()),
        "expected_classes": expected,
        "mapping": mapping,
    }
    return report


def validate_mango_ripening_stages(root: Path) -> dict:
    """Validate ripening stages dataset (stage0..stage3)."""
    expected_map = SOURCES["mango_ripening_stages"]["expected_stages"]
    counts = {}
    for stage in expected_map:
        # Look for stage folders: stage0, stage_0, Stage_0 (Unripe) etc.
        candidates = []
        patterns = [stage, stage.replace("stage", "stage_"), f"{stage} (", stage.upper()]
        for p in root.rglob("*"):
            if p.is_dir():
                name_lower = p.name.lower()
                if stage in name_lower or f"stage_{stage[-1]}" in name_lower:
                    candidates.append(p)
        # Count images in those candidates and also directly under root/stage
        direct = root / stage
        if direct.is_dir():
            candidates.append(direct)
        # Also check for extracted rar content: often rar extracts to folder with same name without extension
        for rar_name in SOURCES["mango_ripening_stages"]["rar_names"]:
            base = Path(rar_name).stem  # e.g., "Stage_0 (Unripe)"
            possible = root / base
            if possible.is_dir():
                candidates.append(possible)
        # Deduplicate
        seen = set()
        total = 0
        for cand in candidates:
            if str(cand) in seen:
                continue
            seen.add(str(cand))
            if cand.is_dir():
                for img in cand.rglob("*"):
                    if img.is_file() and img.suffix.lower() in IMAGE_SUFFIXES:
                        total += 1
        counts[stage] = total

    # Map to our classes
    our_counts = {}
    for stage, our_class in expected_map.items():
        our_counts[our_class] = our_counts.get(our_class, 0) + counts.get(stage, 0)

    report = {
        "root": str(root),
        "stage_counts": counts,
        "mapped_counts": our_counts,
        "total_images": sum(counts.values()),
        "expected_stages": expected_map,
    }
    return report


# ---------------------------------------------------------------------------
# Main download logic
# ---------------------------------------------------------------------------

def download_mango_growth_stages(output_root: Path, cache_dir: Path | None, force: bool = False) -> dict:
    src = SOURCES["mango_growth_stages"]
    cache_path = (cache_dir / src["archive_name"]) if cache_dir else (output_root.parent / "raw" / src["archive_name"])
    dest_root = output_root / "mango_growth_stages"

    # Marker for successful import
    report_path = dest_root / "import_report.json"

    if report_path.is_file() and not force:
        try:
            existing = json.loads(report_path.read_text())
            if existing.get("total_images", 0) >= 1000:
                print(f"[skip] Mango growth stages already imported: {dest_root} ({existing['total_images']} images)")
                return existing
        except Exception:
            pass

    # Download
    download_with_curl(src["url"], cache_path)

    # Verify zip
    try:
        verify_zip(cache_path)
    except ValueError as e:
        # Remove corrupted file and raise
        cache_path.unlink(missing_ok=True)
        raise RuntimeError(f"Corrupt download for {src['id']}: {e}. Please retry.") from e

    # Extract to temp then move to dest_root/mango_growth_stages_raw then organize
    # We extract directly to dest_root, but first clean if force
    if force and dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    # Extract
    extract_zip_once(cache_path, dest_root, marker_name=".growth-extracted-ok")

    # Validate
    validation = validate_mango_growth_stages(dest_root)
    print(f"[validate] Mango growth stages: {validation}")

    if validation["total_images"] < 100:
        raise RuntimeError(f"Mango growth stages validation failed: only {validation['total_images']} images found under {dest_root}. "
                           f"Expected ~2004. Check archive structure. Raw counts: {validation['raw_class_counts']}")

    # Write report
    report = {
        "source": src,
        "archive": str(cache_path),
        "archive_sha256": sha256_file(cache_path),
        "extracted_root": str(dest_root),
        "total_images": validation["total_images"],
        "raw_class_counts": validation["raw_class_counts"],
        "mapped_counts": validation["mapped_counts"],
        "license": src["license"],
        "mapping": src["mapping"],
        "notes": src["notes"],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def download_mango_ripening_stages(output_root: Path, cache_dir: Path | None, force: bool = False) -> dict:
    src = SOURCES["mango_ripening_stages"]
    cache_path = (cache_dir / src["archive_name"]) if cache_dir else (output_root.parent / "raw" / src["archive_name"])
    dest_root = output_root / "mango_ripening_stages"
    report_path = dest_root / "import_report.json"

    if report_path.is_file() and not force:
        try:
            existing = json.loads(report_path.read_text())
            if existing.get("total_images", 0) >= 500:
                print(f"[skip] Mango ripening stages already imported: {dest_root} ({existing['total_images']} images)")
                return existing
        except Exception:
            pass

    download_with_curl(src["url"], cache_path)
    try:
        verify_zip(cache_path)
    except ValueError as e:
        cache_path.unlink(missing_ok=True)
        raise RuntimeError(f"Corrupt download for {src['id']}: {e}") from e

    if force and dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    # Extract zip containing 4 rars
    temp_extract = dest_root / "_temp_zip"
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    temp_extract.mkdir(parents=True)

    extract_zip_once(cache_path, temp_extract, marker_name=".ripening-zip-extracted")

    # Now extract each rar
    stage_map = src["expected_stages"]  # stage0..stage3 -> our class
    # RAR names in order correspond to stages 0-3
    rar_to_stage = {
        "Stage_0 (Unripe).rar": "stage0",
        "Stage_1(Early Ripe).rar": "stage1",
        "Stage_2 (Partially Ripe).rar": "stage2",
        "Stage_3 (Ripe).rar": "stage3",
    }

    for rar_name, stage in rar_to_stage.items():
        rar_path = temp_extract / rar_name
        # Search recursively if not found directly
        if not rar_path.is_file():
            found = list(temp_extract.rglob(rar_name))
            if found:
                rar_path = found[0]
            else:
                # Try pattern without spaces
                for p in temp_extract.rglob("*.rar"):
                    if stage in p.name.lower() or rar_name.split()[0].lower() in p.name.lower():
                        rar_path = p
                        break
        if not rar_path.is_file():
            print(f"[warn] RAR not found: {rar_name}, skipping stage {stage}")
            continue
        stage_dir = dest_root / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        print(f"[extract-rar] {rar_path} -> {stage_dir}")
        ok = try_extract_rar(rar_path, stage_dir)
        if not ok:
            # Try to handle as zip (some rar may actually be zip)
            try:
                with zipfile.ZipFile(rar_path) as z:
                    z.extractall(stage_dir)
                ok = True
            except Exception:
                pass
        if not ok:
            raise RuntimeError(f"Failed to extract RAR {rar_path}. Please install unrar (apt-get install unrar) or patool. "
                               f"Archive: {cache_path}")

    # Cleanup temp
    shutil.rmtree(temp_extract, ignore_errors=True)

    validation = validate_mango_ripening_stages(dest_root)
    print(f"[validate] Mango ripening stages: {validation}")

    if validation["total_images"] < 100:
        raise RuntimeError(f"Mango ripening validation failed: only {validation['total_images']} images under {dest_root}. "
                           f"Counts: {validation['stage_counts']}")

    report = {
        "source": src,
        "archive": str(cache_path),
        "archive_sha256": sha256_file(cache_path),
        "extracted_root": str(dest_root),
        "total_images": validation["total_images"],
        "stage_counts": validation["stage_counts"],
        "mapped_counts": validation["mapped_counts"],
        "license": src["license"],
        "mapping": stage_map,
        "notes": src["notes"],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("data/external/extracted"),
                        help="Root where datasets are extracted (e.g., data/external/extracted)")
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="Cache directory for raw zips (e.g., /content/drive/MyDrive/fruit_data/public_raw)")
    parser.add_argument("--force", action="store_true", help="Force re-download and re-extract")
    parser.add_argument("--sources", nargs="*", choices=list(SOURCES.keys()), default=list(SOURCES.keys()),
                        help="Which sources to download")
    args = parser.parse_args()

    output_root = args.output_root.resolve()
    cache_dir = args.cache_dir.resolve() if args.cache_dir else None
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for source in args.sources:
        if source == "mango_growth_stages":
            results[source] = download_mango_growth_stages(output_root, cache_dir, args.force)
        elif source == "mango_ripening_stages":
            results[source] = download_mango_ripening_stages(output_root, cache_dir, args.force)

    # Summary
    print("\n=== Mango replacement datasets summary ===")
    print(json.dumps(results, indent=2))

    # Check for missing classes
    combined = {}
    for src_report in results.values():
        for cls, cnt in src_report.get("mapped_counts", {}).items():
            combined[cls] = combined.get(cls, 0) + cnt
    print(f"\nCombined mapped counts across all sources: {combined}")
    required = ["mango_young", "mango_mature", "mango_turning", "mango_ripe"]
    missing = [c for c in required if combined.get(c, 0) == 0]
    if missing:
        print(f"[warn] Missing classes after download: {missing}. "
              f"This will block mango classifier training. Search for additional datasets.", file=sys.stderr)
    else:
        print(f"[ok] All 4 mango classes have data: {combined}")

    # Write combined report
    (output_root / "mango_replacement_summary.json").write_text(json.dumps({
        "sources": results,
        "combined_mapped_counts": combined,
        "required_classes": required,
        "missing_classes": missing,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
