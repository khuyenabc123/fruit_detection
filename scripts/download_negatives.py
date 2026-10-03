#!/usr/bin/env python3
"""Download negative (background) images: other fruit and dragon-fruit flowers.

Each Roboflow export is fetched, reduced to one copy per original upload, sampled
to a fixed size with a fixed seed, and copied as images only (labels discarded)
to data/external/extracted/negatives/<source>/. The detector then learns these
are not mango or dragon fruit. API key handling as in download_roboflow_detection.
"""

from __future__ import annotations

import argparse
import io
import json
import random
import shutil
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from download_roboflow_detection import api_key, get_json

# source -> (workspace, project, version, sample size or None for all, licence, content)
SOURCES = {
    "neg_litchi_orchard": ("11111-ssxwo", "litchi-ctsui", 2, 300, "CC BY 4.0", "lychee clusters on trees"),
    "neg_lychee_vn": ("vnu-jozz8", "lychee-p5qlv", 1, 200, "CC BY 4.0", "Vietnamese lychee orchards"),
    "neg_litchi_green": ("south-china-agriculture-university-yiovr", "litchi_seg_2", 3, 100, "CC BY 4.0", "green/half-red litchi on trees"),
    "neg_rambutan": ("n-a-0tjsb", "rambutan-ripeness-detection", 1, 200, "MIT", "rambutan on trees"),
    "neg_pomegranate": ("flower-icte3", "pomegranate-00y7c", 1, 150, "CC BY 4.0", "pomegranate on trees"),
    "neg_apple_orchard": ("nust2", "apple-hyrte", 1, 150, "CC BY 4.0", "trellised apple rows"),
    "neg_tomato": ("fruit-dsna0", "tomato-5yhlt", 4, 100, "CC BY 4.0", "greenhouse tomatoes"),
    "neg_pitaya_flower_night": ("pitaya-ubgq5", "pitaya-xxtg8", 2, None, "CC BY 4.0", "dragon-fruit flowers/buds, plantation at night"),
    "neg_pitaya_flower_close": ("dragon-hf4db", "dragon-9gcmh", 1, None, "CC BY 4.0", "dragon-fruit flower close-ups"),
    "neg_pitaya_flower_web": ("pitaya-vogjz", "pitaya_keypoints", 1, None, "CC BY 4.0", "dragon-fruit flowers and buds"),
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def export_zip(workspace: str, project: str, version: int, key: str) -> bytes:
    query = urllib.parse.urlencode({"api_key": key})
    for _ in range(60):
        export = get_json(f"https://api.roboflow.com/{workspace}/{project}/{version}/yolov8?{query}")
        link = export.get("export", {}).get("link")
        if link:
            with urllib.request.urlopen(link, timeout=600) as response:
                return response.read()
        time.sleep(10)
    raise RuntimeError(f"{workspace}/{project}/{version}: export not ready after 10 minutes")


def fetch(source: str, output_root: Path, key: str) -> dict:
    workspace, project, version, sample, licence, content = SOURCES[source]
    payload = export_zip(workspace, project, version, key)
    destination = output_root / "negatives" / source
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as scratch:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(scratch)
        originals: dict[str, Path] = {}
        # Prefer the train split's first copy; augmented copies share the name before ".rf.".
        for path in sorted(Path(scratch).rglob("*")):
            if path.suffix.lower() in IMAGE_SUFFIXES and path.parent.name == "images":
                originals.setdefault(path.stem.split(".rf.", maxsplit=1)[0], path)
        chosen = sorted(originals)
        if sample is not None and len(chosen) > sample:
            chosen = sorted(random.Random(f"negatives:{source}").sample(chosen, sample))
        for stem in chosen:
            shutil.copy2(originals[stem], destination / originals[stem].name)
    report = {
        "source": source,
        "url": f"https://universe.roboflow.com/{workspace}/{project}/dataset/{version}",
        "licence": licence,
        "content": content,
        "unique_originals": len(originals),
        "images_kept": len(chosen),
        "note": "Negative images: labels discarded; used with empty detector labels.",
    }
    (destination.parent / f"{source}.import_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("data/external/extracted"))
    parser.add_argument("sources", nargs="*", default=list(SOURCES))
    args = parser.parse_args()
    key = api_key()
    for source in args.sources:
        print(json.dumps(fetch(source, args.output_root, key)), flush=True)


if __name__ == "__main__":
    main()
