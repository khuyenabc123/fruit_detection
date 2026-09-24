#!/usr/bin/env python3
"""Create a lightweight inventory of downloaded public fruit datasets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def audit_dataset(dataset_dir: Path) -> dict:
    files = [path for path in dataset_dir.rglob("*") if path.is_file()]
    images = [path for path in files if path.suffix.lower() in IMAGE_SUFFIXES]
    suffix_counts = Counter(path.suffix.lower() or "[no extension]" for path in files)
    image_parent_counts = Counter(relative(path.parent, dataset_dir) for path in images)

    report = {
        "bytes": sum(path.stat().st_size for path in files),
        "file_count": len(files),
        "image_count": len(images),
        "files_by_extension": dict(sorted(suffix_counts.items())),
        "images_by_directory": dict(sorted(image_parent_counts.items())),
    }

    voc_files = sorted(dataset_dir.rglob("*.xml"))
    if voc_files:
        class_counts: Counter[str] = Counter()
        for annotation_file in voc_files:
            tree = ET.parse(annotation_file)
            class_counts.update(
                obj.findtext("name", default="[missing]")
                for obj in tree.findall(".//object")
            )
        report["pascal_voc"] = {
            "annotation_files": len(voc_files),
            "objects": sum(class_counts.values()),
            "objects_by_class": dict(sorted(class_counts.items())),
        }

    coco_reports = []
    for annotation_file in sorted(dataset_dir.rglob("*.json")):
        try:
            payload = json.loads(annotation_file.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or "images" not in payload or "annotations" not in payload:
            continue
        category_by_id = {
            category.get("id"): category.get("name", "[missing]")
            for category in payload.get("categories", [])
        }
        annotations_by_class = Counter(
            category_by_id.get(annotation.get("category_id"), "[unknown]")
            for annotation in payload.get("annotations", [])
        )
        coco_reports.append(
            {
                "file": relative(annotation_file, dataset_dir),
                "images": len(payload.get("images", [])),
                "annotations": len(payload.get("annotations", [])),
                "annotations_by_class": dict(sorted(annotations_by_class.items())),
            }
        )
    if coco_reports:
        report["coco"] = coco_reports

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/external/extracted"),
        help="Directory containing one extracted directory per dataset.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/external/audit_report.json"),
        help="JSON report path.",
    )
    args = parser.parse_args()

    if not args.root.is_dir():
        raise SystemExit(f"Dataset root does not exist: {args.root}")

    report = {
        "dataset_root": args.root.as_posix(),
        "datasets": {
            dataset_dir.name: audit_dataset(dataset_dir)
            for dataset_dir in sorted(args.root.iterdir())
            if dataset_dir.is_dir()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
