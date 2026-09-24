#!/usr/bin/env python3
"""Build leak-resistant datasets for the two-stage fruit pipeline.

Outputs:
  detector/            YOLO detection dataset with classes mango/dragonfruit
  mango_classifier/    ImageFolder dataset with four mango maturity classes
  dragon_classifier/   ImageFolder dataset with three dragon-fruit classes

Public datasets without maturity labels are used only for localization. Existing
Roboflow datasets can be supplied to add dragon-fruit boxes and crop-level
maturity labels. Splits are assigned by source-image group, never by crop/file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml
from PIL import Image


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
DETECTOR_NAMES = {0: "mango", 1: "dragonfruit"}
MANGO_CLASS_NAMES = ["mango_premature", "mango_early", "mango_mature", "mango_ripe"]
DRAGON_CLASS_NAMES = ["dragonfruit_unripe", "dragonfruit_ripe", "dragonfruit_rotten"]

MANGO_RF_MAP = {
    "premature": "mango_premature",
    "early-fruit": "mango_early",
    "early_fruit": "mango_early",
    "early": "mango_early",
    "mature": "mango_mature",
    "ripe": "mango_ripe",
}
DRAGON_RF_MAP = {
    "unripe": "dragonfruit_unripe",
    "immature": "dragonfruit_unripe",
    "ripe": "dragonfruit_ripe",
    "mature": "dragonfruit_ripe",
    "rotten": "dragonfruit_rotten",
}


@dataclass(frozen=True)
class DetectionExample:
    image: Path
    boxes: tuple[tuple[int, float, float, float, float], ...]
    source: str
    group: str
    content_hash: str


@dataclass(frozen=True)
class ClassificationExample:
    image: Path
    class_name: str
    source: str
    group: str
    content_hash: str
    crop_xyxy: tuple[int, int, int, int] | None = None
    crop_index: int = 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()


def load_yaml_names(dataset_dir: Path) -> dict[int, str]:
    yaml_path = dataset_dir / "data.yaml"
    if not yaml_path.is_file():
        raise FileNotFoundError(f"Missing Roboflow data.yaml: {yaml_path}")
    payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    names = payload.get("names")
    if isinstance(names, list):
        return {index: str(name) for index, name in enumerate(names)}
    if isinstance(names, dict):
        return {int(index): str(name) for index, name in names.items()}
    raise ValueError(f"Invalid names field in {yaml_path}")


def iter_rf_pairs(dataset_dir: Path) -> Iterable[tuple[Path, Path]]:
    seen: set[Path] = set()
    for split in ("train", "valid", "val", "test"):
        image_dir = dataset_dir / split / "images"
        label_dir = dataset_dir / split / "labels"
        if not image_dir.is_dir():
            continue
        for image_path in sorted(image_dir.iterdir()):
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            resolved = image_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield image_path, label_dir / f"{image_path.stem}.txt"


def rf_group_id(image_path: Path, prefix: str) -> str:
    original = image_path.stem.split(".rf.", maxsplit=1)[0]
    return f"{prefix}:{original}"


def read_yolo_boxes(label_path: Path) -> list[tuple[int, float, float, float, float]]:
    boxes = []
    if not label_path.is_file():
        return boxes
    for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            class_id = int(float(parts[0]))
            x, y, w, h = map(float, parts[1:5])
        except ValueError as exc:
            raise ValueError(f"Invalid YOLO label at {label_path}:{line_number}") from exc
        if w <= 0 or h <= 0:
            continue
        boxes.append((class_id, x, y, w, h))
    return boxes


def load_mango_yolo(external_root: Path) -> list[DetectionExample]:
    voc_root = external_root / "mango_yolo" / "VOCDevkit" / "VOC2007"
    image_dir = voc_root / "JPEGImages"
    annotation_dir = voc_root / "Annotations"
    examples = []
    for annotation_path in sorted(annotation_dir.glob("*.xml")):
        image_path = image_dir / f"{annotation_path.stem}.jpg"
        if not image_path.is_file():
            candidates = [path for path in image_dir.glob(f"{annotation_path.stem}.*") if path.suffix.lower() in IMAGE_SUFFIXES]
            if not candidates:
                continue
            image_path = candidates[0]
        tree = ET.parse(annotation_path)
        width = float(tree.findtext("size/width", default="0"))
        height = float(tree.findtext("size/height", default="0"))
        if width <= 0 or height <= 0:
            with Image.open(image_path) as image:
                width, height = image.size
        boxes = []
        for obj in tree.findall("object"):
            bbox = obj.find("bndbox")
            if bbox is None:
                continue
            xmin = max(0.0, float(bbox.findtext("xmin", default="0")))
            ymin = max(0.0, float(bbox.findtext("ymin", default="0")))
            xmax = min(width, float(bbox.findtext("xmax", default="0")))
            ymax = min(height, float(bbox.findtext("ymax", default="0")))
            box_w, box_h = xmax - xmin, ymax - ymin
            if box_w <= 1 or box_h <= 1:
                continue
            boxes.append((0, (xmin + xmax) / (2 * width), (ymin + ymax) / (2 * height), box_w / width, box_h / height))
        identity = re.sub(r"_\d+_\d+$", "", annotation_path.stem)
        examples.append(
            DetectionExample(
                image=image_path,
                boxes=tuple(boxes),
                source="mango_yolo",
                group=f"mango_yolo:{identity}",
                content_hash=sha256_file(image_path),
            )
        )
    return examples


def load_mango_coco_tiles(external_root: Path) -> list[DetectionExample]:
    tiled_root = (
        external_root
        / "mango_on_tree_segmentation"
        / "mango-segmentation-dataset"
        / "tiled-images"
    )
    examples = []
    for split in ("train", "test"):
        annotation_path = tiled_root / split / f"{split}.json"
        if not annotation_path.is_file():
            continue
        payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        annotations = defaultdict(list)
        for annotation in payload.get("annotations", []):
            annotations[int(annotation["image_id"])].append(annotation)
        for image_info in payload.get("images", []):
            image_path = tiled_root / split / image_info["file_name"]
            if not image_path.is_file():
                continue
            width, height = float(image_info["width"]), float(image_info["height"])
            boxes = []
            for annotation in annotations[int(image_info["id"])]:
                x, y, box_w, box_h = map(float, annotation["bbox"])
                if box_w <= 1 or box_h <= 1:
                    continue
                boxes.append((0, (x + box_w / 2) / width, (y + box_h / 2) / height, box_w / width, box_h / height))
            examples.append(
                DetectionExample(
                    image=image_path,
                    boxes=tuple(boxes),
                    source="mango_on_tree",
                    group=f"mango_on_tree:{image_path.stem}",
                    content_hash=sha256_file(image_path),
                )
            )
    return examples


def load_rf_detection(dataset_dir: Path, species: str) -> list[DetectionExample]:
    id_to_name = load_yaml_names(dataset_dir)
    detector_class = 0 if species == "mango" else 1
    class_map = MANGO_RF_MAP if species == "mango" else DRAGON_RF_MAP
    examples = []
    for image_path, label_path in iter_rf_pairs(dataset_dir):
        boxes = []
        for source_id, x, y, w, h in read_yolo_boxes(label_path):
            source_name = normalized_name(id_to_name.get(source_id, ""))
            if source_name in class_map:
                boxes.append((detector_class, x, y, w, h))
        examples.append(
            DetectionExample(
                image=image_path,
                boxes=tuple(boxes),
                source=f"rf_{species}",
                group=rf_group_id(image_path, f"rf_{species}"),
                content_hash=sha256_file(image_path),
            )
        )
    return examples


def load_rf_classifier(dataset_dir: Path, species: str, crop_padding: float) -> list[ClassificationExample]:
    id_to_name = load_yaml_names(dataset_dir)
    class_map = MANGO_RF_MAP if species == "mango" else DRAGON_RF_MAP
    examples = []
    for image_path, label_path in iter_rf_pairs(dataset_dir):
        with Image.open(image_path) as image:
            width, height = image.size
        content_hash = sha256_file(image_path)
        group = rf_group_id(image_path, f"rf_{species}")
        for box_index, (source_id, x, y, w, h) in enumerate(read_yolo_boxes(label_path)):
            class_name = class_map.get(normalized_name(id_to_name.get(source_id, "")))
            if class_name is None:
                continue
            pad_w, pad_h = width * w * crop_padding, height * h * crop_padding
            xmin = max(0, round(width * (x - w / 2) - pad_w))
            ymin = max(0, round(height * (y - h / 2) - pad_h))
            xmax = min(width, round(width * (x + w / 2) + pad_w))
            ymax = min(height, round(height * (y + h / 2) + pad_h))
            if xmax - xmin < 8 or ymax - ymin < 8:
                continue
            examples.append(
                ClassificationExample(
                    image=image_path,
                    class_name=class_name,
                    source=f"rf_{species}",
                    group=group,
                    content_hash=content_hash,
                    crop_xyxy=(xmin, ymin, xmax, ymax),
                    crop_index=box_index,
                )
            )
    return examples


def load_dragon_mendeley_originals(external_root: Path) -> list[ClassificationExample]:
    original_root = (
        external_root
        / "dragon_fruit_maturity"
        / "Dragon Fruit Maturity Detection Dataset"
        / "Original Dataset"
    )
    folder_map = {
        "Immature Dragon Fruit": "dragonfruit_unripe",
        "Mature Dragon Fruit": "dragonfruit_ripe",
    }
    examples = []
    for folder_name, class_name in folder_map.items():
        for image_path in sorted((original_root / folder_name).iterdir()):
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            content_hash = sha256_file(image_path)
            examples.append(
                ClassificationExample(
                    image=image_path,
                    class_name=class_name,
                    source="mendeley_dragon_maturity_original",
                    group=f"mendeley:{content_hash}",
                    content_hash=content_hash,
                )
            )
    return examples


def deduplicate_detection(examples: list[DetectionExample]) -> tuple[list[DetectionExample], int]:
    by_hash: dict[str, DetectionExample] = {}
    duplicates = 0
    for example in examples:
        existing = by_hash.get(example.content_hash)
        if existing is None:
            by_hash[example.content_hash] = example
            continue
        duplicates += 1
        # Prefer the annotation with more visible objects for byte-identical images.
        if len(example.boxes) > len(existing.boxes):
            by_hash[example.content_hash] = example
    return list(by_hash.values()), duplicates


def deduplicate_classification(examples: list[ClassificationExample]) -> tuple[list[ClassificationExample], int]:
    seen: set[tuple[str, str, tuple[int, int, int, int] | None]] = set()
    output = []
    duplicates = 0
    for example in examples:
        key = (example.content_hash, example.class_name, example.crop_xyxy)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        output.append(example)
    return output, duplicates


def assign_group_splits(
    examples: list[DetectionExample] | list[ClassificationExample],
    split_ratios: dict[str, float],
    seed: int,
    classification: bool,
) -> dict[str, str]:
    group_examples = defaultdict(list)
    for example in examples:
        group_examples[example.group].append(example)

    strata = defaultdict(list)
    for group, members in group_examples.items():
        if classification:
            signature = tuple(sorted({member.class_name for member in members}))
        else:
            signature = tuple(sorted({box[0] for member in members for box in member.boxes}))
        strata[(members[0].source, signature)].append(group)

    assignments = {}
    for stratum, groups in sorted(strata.items(), key=lambda item: str(item[0])):
        rng = random.Random(f"{seed}:{stratum}")
        rng.shuffle(groups)
        total = len(groups)
        cursor = 0
        split_names = list(split_ratios)
        for split_index, split_name in enumerate(split_names):
            if split_index == len(split_names) - 1:
                selected = groups[cursor:]
            else:
                end = round(total * sum(list(split_ratios.values())[: split_index + 1]))
                selected = groups[cursor:end]
                cursor = end
            for group in selected:
                assignments[group] = split_name
    return assignments


def materialize_file(source: Path, destination: Path, mode: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if mode == "copy":
        shutil.copy2(source, destination)
    elif mode == "hardlink":
        try:
            os.link(source, destination)
        except OSError:
            shutil.copy2(source, destination)
    elif mode == "symlink":
        destination.symlink_to(source.resolve())
    else:
        raise ValueError(f"Unsupported materialization mode: {mode}")


def write_detector(
    examples: list[DetectionExample], output_dir: Path, seed: int, mode: str
) -> dict:
    assignments = assign_group_splits(
        examples,
        {"train": 0.70, "val": 0.15, "test": 0.15},
        seed,
        classification=False,
    )
    rows = []
    stats = Counter()
    for example in sorted(examples, key=lambda item: (item.source, item.image.as_posix())):
        split = assignments[example.group]
        stem = f"{safe_slug(example.source)}_{example.content_hash[:16]}"
        image_destination = output_dir / "images" / split / f"{stem}{example.image.suffix.lower()}"
        label_destination = output_dir / "labels" / split / f"{stem}.txt"
        materialize_file(example.image, image_destination, mode)
        label_destination.parent.mkdir(parents=True, exist_ok=True)
        label_destination.write_text(
            "".join(
                f"{class_id} {x:.8f} {y:.8f} {w:.8f} {h:.8f}\n"
                for class_id, x, y, w, h in example.boxes
            ),
            encoding="utf-8",
        )
        stats[f"images_{split}"] += 1
        stats[f"boxes_{split}"] += len(example.boxes)
        for class_id, *_ in example.boxes:
            stats[f"boxes_{split}_{DETECTOR_NAMES[class_id]}"] += 1
        rows.append(
            {
                "split": split,
                "source": example.source,
                "source_image": example.image.as_posix(),
                "group": example.group,
                "sha256": example.content_hash,
                "output_image": image_destination.relative_to(output_dir).as_posix(),
                "box_count": len(example.boxes),
            }
        )

    yaml_payload = {
        "path": str(output_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": DETECTOR_NAMES,
        "nc": len(DETECTOR_NAMES),
    }
    (output_dir / "data.yaml").write_text(
        yaml.safe_dump(yaml_payload, sort_keys=False), encoding="utf-8"
    )
    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["split"])
        writer.writeheader()
        writer.writerows(rows)
    return dict(sorted(stats.items()))


def materialize_classifier(
    examples: list[ClassificationExample],
    output_dir: Path,
    class_names: list[str],
    seed: int,
    mode: str,
) -> dict:
    if not examples:
        return {"warning": "No source examples were available."}
    assignments = assign_group_splits(
        examples,
        {"train": 0.65, "val": 0.15, "calib": 0.10, "test": 0.10},
        seed,
        classification=True,
    )

    # Offline Roboflow augmentation variants remain useful for training, but one
    # variant per original group is enough for validation/calibration/test.
    canonical_nontrain_image = {}
    for example in examples:
        if assignments[example.group] != "train" and example.source.startswith("rf_"):
            current = canonical_nontrain_image.get(example.group)
            candidate = example.image.as_posix()
            if current is None or candidate < current:
                canonical_nontrain_image[example.group] = candidate

    rows = []
    stats = Counter()
    for example in sorted(
        examples,
        key=lambda item: (item.source, item.image.as_posix(), item.crop_index),
    ):
        split = assignments[example.group]
        canonical = canonical_nontrain_image.get(example.group)
        if canonical is not None and example.image.as_posix() != canonical:
            stats["skipped_nontrain_augmented_variants"] += 1
            continue
        stem = f"{safe_slug(example.source)}_{example.content_hash[:16]}_{example.crop_index:03d}"
        destination = output_dir / split / example.class_name / f"{stem}.jpg"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if example.crop_xyxy is None and example.image.suffix.lower() in {".jpg", ".jpeg"}:
            materialize_file(example.image, destination, mode)
        else:
            with Image.open(example.image) as image:
                rgb = image.convert("RGB")
                if example.crop_xyxy is not None:
                    rgb = rgb.crop(example.crop_xyxy)
                rgb.save(destination, format="JPEG", quality=95)
        stats[f"images_{split}"] += 1
        stats[f"images_{split}_{example.class_name}"] += 1
        rows.append(
            {
                "split": split,
                "class_name": example.class_name,
                "source": example.source,
                "source_image": example.image.as_posix(),
                "group": example.group,
                "sha256": example.content_hash,
                "output_image": destination.relative_to(output_dir).as_posix(),
            }
        )

    (output_dir / "classes.json").write_text(
        json.dumps({"names": class_names}, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["split"])
        writer.writeheader()
        writer.writerows(rows)
    return dict(sorted(stats.items()))


def assert_no_group_leakage(manifest_path: Path) -> None:
    groups = defaultdict(set)
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            groups[row["group"]].add(row["split"])
    leaking = {group: splits for group, splits in groups.items() if len(splits) > 1}
    if leaking:
        sample = list(leaking.items())[:5]
        raise RuntimeError(f"Group leakage detected in {manifest_path}: {sample}")


def prepare(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        if not args.overwrite:
            raise SystemExit(f"Output is not empty: {output}. Use --overwrite to replace it.")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    detection_examples = load_mango_yolo(args.external_root)
    detection_examples.extend(load_mango_coco_tiles(args.external_root))
    mango_classifier_examples = []
    dragon_classifier_examples = load_dragon_mendeley_originals(args.external_root)

    if args.mango_rf:
        detection_examples.extend(load_rf_detection(args.mango_rf, "mango"))
        mango_classifier_examples.extend(load_rf_classifier(args.mango_rf, "mango", args.crop_padding))
    if args.dragon_rf:
        detection_examples.extend(load_rf_detection(args.dragon_rf, "dragonfruit"))
        dragon_classifier_examples.extend(load_rf_classifier(args.dragon_rf, "dragonfruit", args.crop_padding))

    detection_examples, detector_duplicates = deduplicate_detection(detection_examples)
    mango_classifier_examples, mango_duplicates = deduplicate_classification(mango_classifier_examples)
    dragon_classifier_examples, dragon_duplicates = deduplicate_classification(dragon_classifier_examples)

    report = {
        "seed": args.seed,
        "rules": {
            "detector_classes": DETECTOR_NAMES,
            "mango_classifier_classes": MANGO_CLASS_NAMES,
            "dragon_classifier_classes": DRAGON_CLASS_NAMES,
            "dragon_quality_dataset_used": False,
            "reason": "fresh/defect is not equivalent to ripe/rotten",
            "mendeley_augmented_images_used": False,
        },
        "deduplication": {
            "detector_exact_duplicates_removed": detector_duplicates,
            "mango_classifier_duplicates_removed": mango_duplicates,
            "dragon_classifier_duplicates_removed": dragon_duplicates,
        },
    }
    report["detector"] = write_detector(
        detection_examples, output / "detector", args.seed, args.mode
    )
    report["mango_classifier"] = materialize_classifier(
        mango_classifier_examples,
        output / "mango_classifier",
        MANGO_CLASS_NAMES,
        args.seed,
        args.mode,
    )
    report["dragon_classifier"] = materialize_classifier(
        dragon_classifier_examples,
        output / "dragon_classifier",
        DRAGON_CLASS_NAMES,
        args.seed,
        args.mode,
    )

    for manifest in output.rglob("manifest.csv"):
        assert_no_group_leakage(manifest)
    (output / "preparation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-root", type=Path, default=Path("data/external/extracted"))
    parser.add_argument("--mango-rf", type=Path, help="Extracted mango Roboflow dataset directory")
    parser.add_argument("--dragon-rf", type=Path, help="Extracted dragon-fruit Roboflow dataset directory")
    parser.add_argument("--output", type=Path, default=Path("data/prepared/two_stage"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--crop-padding", type=float, default=0.10)
    parser.add_argument("--mode", choices=("copy", "hardlink", "symlink"), default="copy")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    result = prepare(parsed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
