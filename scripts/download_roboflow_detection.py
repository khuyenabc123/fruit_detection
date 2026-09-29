#!/usr/bin/env python3
"""Download the Roboflow Universe detection exports used for wide whole-tree shots.

The API key is read from $ROBOFLOW_API_KEY or ~/.roboflow_key and is never
written to disk or printed. Each export lands in
data/external/extracted/<source>/ with an import_report.json recording the
project, version, licence and image count.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

# source name -> (workspace, project, version, species)
SOURCES = {
    "rf_mango_tree": ("jerng-mi", "mango-tree-rya7c", 1, "mango"),
    "rf_pitaya_orchard": ("pitaya-2jhyv", "goodgoodgood", 8, "dragonfruit"),
    "rf_ripe_dragon_plants": ("training-dwctq", "ripe-dragon-fruits", 1, "dragonfruit"),
}


def api_key() -> str:
    key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    path = Path.home() / ".roboflow_key"
    if not key and path.is_file():
        key = path.read_text().strip()
    if not key:
        raise SystemExit("No Roboflow API key: set ROBOFLOW_API_KEY or write it to ~/.roboflow_key")
    return key


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.load(response)


def download(source: str, output_root: Path, key: str) -> dict:
    workspace, project, version, species = SOURCES[source]
    query = urllib.parse.urlencode({"api_key": key})
    info = get_json(f"https://api.roboflow.com/{workspace}/{project}?{query}")
    export = get_json(f"https://api.roboflow.com/{workspace}/{project}/{version}/yolov8?{query}")
    link = export.get("export", {}).get("link")
    if not link:
        raise RuntimeError(f"{source}: export not ready or not permitted: {list(export)}")
    with urllib.request.urlopen(link, timeout=600) as response:
        payload = response.read()
    destination = output_root / source
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(destination)
    images = [p for p in destination.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    project_info = info.get("project", {})
    report = {
        "source": source,
        "species": species,
        "url": f"https://universe.roboflow.com/{workspace}/{project}/dataset/{version}",
        "licence": project_info.get("license"),
        "classes": project_info.get("classes"),
        "images_in_export": len(images),
        "note": "Detector boxes only; every class maps to the species box. Augmented copies are dropped per original during preparation.",
    }
    (destination / "import_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("data/external/extracted"))
    parser.add_argument("sources", nargs="*", default=list(SOURCES))
    args = parser.parse_args()
    key = api_key()
    for source in args.sources:
        report = download(source, args.output_root, key)
        print(json.dumps(report))


if __name__ == "__main__":
    main()
