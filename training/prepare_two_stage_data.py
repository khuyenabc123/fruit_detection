#!/usr/bin/env python3
"""Build leak-resistant datasets for the two-stage fruit pipeline.

Outputs:
  detector/            YOLO detection dataset with classes mango/dragonfruit
  mango_classifier/    ImageFolder dataset with four visible mango ripeness stages
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
from maturity_data import REVISION, audit_prepared_classifier, curate_dragon, rebalance_classification_groups


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
DETECTOR_NAMES = {0: "mango", 1: "dragonfruit"}
# Stages are defined by what a photo shows. The Roboflow export's premature and
# early-fruit labels are fruit-age stages that look identical, so both are young.
MANGO_CLASS_NAMES = ["mango_young", "mango_mature", "mango_turning", "mango_ripe"]
DRAGON_CLASS_NAMES = ["dragonfruit_unripe", "dragonfruit_ripe", "dragonfruit_rotten"]
ORCHARD_SOURCES = {"dragon_fruit_orchard": 1, "mango_orchard_daylight": 0}

MANGO_RF_MAP = {
    "premature": "mango_young",
    "early-fruit": "mango_young",
    "early_fruit": "mango_young",
    "early": "mango_young",
    "mature": "mango_mature",
    "ripe": "mango_ripe",
}
# Mendeley mm8g66d7rc post-harvest ripening stages. Stage 1 "Early Ripe" is still
# green with barely visible yellowing, indistinguishable from Stage 0 in review.
MANGO_RIPENING_STAGE_MAP = {
    "stage0": "mango_mature",
    "stage1": "mango_mature",
    "stage2": "mango_turning",
    "stage3": "mango_ripe",
}
MANGO_FARFIELD_SUBSETS = ("Far_Field", "Proximal", "Single")
# Consecutively numbered far-field photos often show the same tree.
MANGO_FARFIELD_GROUP_SIZE = 10
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
    # The dragon Roboflow export includes resized copies of Mendeley originals.
    # Share a group ID across both sources so they cannot land in different splits.
    if prefix == "rf_dragonfruit" and re.fullmatch(
        r"(?:Immature|Mature)_Dragon_Original_Data\d+_jpg", original
    ):
        return f"dragon_maturity:{original[:-4]}"
    return f"{prefix}:{original}"


def read_yolo_boxes(label_path: Path) -> list[tuple[int, float, float, float, float]]:
    """Read YOLO boxes and convert YOLO segmentation polygons to enclosing boxes."""
    boxes = []
    if not label_path.is_file():
        return boxes
    for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 5 and (len(parts) < 7 or len(parts) % 2 == 0):
            raise ValueError(f"Invalid YOLO label shape at {label_path}:{line_number}")
        try:
            class_id = int(float(parts[0]))
            values = list(map(float, parts[1:]))
        except ValueError as exc:
            raise ValueError(f"Invalid YOLO label at {label_path}:{line_number}") from exc
        if not all(0.0 <= value <= 1.0 for value in values):
            raise ValueError(f"YOLO coordinates outside [0, 1] at {label_path}:{line_number}")
        if len(parts) == 5:
            x, y, w, h = values
        else:
            xs, ys = values[::2], values[1::2]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            x, y = (xmin + xmax) / 2, (ymin + ymax) / 2
            w, h = xmax - xmin, ymax - ymin
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


def load_mango_farfield(external_root: Path) -> list[DetectionExample]:
    """Mendeley gcgrjvwmm2 on-tree mango photos, including distant small fruit."""
    root = external_root / "mango_farfield" / "Mango_Dataset"
    examples = []
    for subset in MANGO_FARFIELD_SUBSETS:
        image_dir = root / subset / "images"
        if not image_dir.is_dir():
            continue
        for image_path in sorted(image_dir.iterdir()):
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            label_path = root / subset / "labels" / f"{image_path.stem}.txt"
            if not label_path.is_file():
                continue
            boxes = read_yolo_boxes(label_path)
            if any(box[0] != 0 for box in boxes):
                raise ValueError(f"Expected only mango boxes in {label_path}")
            number = re.search(r"(\d+)$", image_path.stem)
            block = int(number.group(1)) // MANGO_FARFIELD_GROUP_SIZE if number else image_path.stem
            examples.append(
                DetectionExample(
                    image=image_path,
                    boxes=tuple(boxes),
                    source="mango_farfield",
                    group=f"mango_farfield:{block}",
                    content_hash=sha256_file(image_path),
                )
            )
    return examples


def load_extra_rf_detection(dataset_dir: Path, species: str, source: str) -> list[DetectionExample]:
    """Additional Roboflow detection export: every box becomes the species box.

    Offline-augmented copies share the name before `.rf.`; keep one per original
    so augmentation cannot inflate validation/test or leak across splits.
    """
    detector_class = 0 if species == "mango" else 1
    by_group: dict[str, DetectionExample] = {}
    for image_path, label_path in iter_rf_pairs(dataset_dir):
        group = rf_group_id(image_path, source)
        if group in by_group:
            continue
        boxes = tuple((detector_class, *box[1:]) for box in read_yolo_boxes(label_path))
        by_group[group] = DetectionExample(image_path, boxes, source, group, sha256_file(image_path))
    return list(by_group.values())


def load_negative_images(directory: Path, source: str) -> list[DetectionExample]:
    """Background images of other fruit/flowers: empty labels teach "not mango/dragon"."""
    by_group: dict[str, DetectionExample] = {}
    for image_path in sorted(directory.rglob("*")):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        group = rf_group_id(image_path, source)
        if group not in by_group:
            by_group[group] = DetectionExample(image_path, (), source, group, sha256_file(image_path))
    return list(by_group.values())


def drop_cross_source_copies(sources: list[list[DetectionExample]]) -> tuple[list[DetectionExample], dict[str, int]]:
    """Roboflow projects re-upload each other's photos. Keep the first copy seen,
    matched by original upload name or a near-identical visual hash, so one photo
    cannot appear in two sources and straddle splits."""
    import numpy as np

    from maturity_data import fingerprint

    kept: list[DetectionExample] = []
    dropped: Counter = Counter()
    seen_stems: set[str] = set()
    seen_hashes = np.zeros(0, dtype=np.uint64)
    for examples in sources:
        new_hashes = []
        for example in examples:
            stem = example.image.stem.split(".rf.", maxsplit=1)[0]
            with Image.open(example.image) as image:
                bits = np.uint64(fingerprint(image.convert("RGB"))[0])
            near = seen_hashes.size and int(
                (np.unpackbits((seen_hashes ^ bits).view(np.uint8)).reshape(-1, 64).sum(axis=1) <= 4).any()
            )
            if stem in seen_stems or near:
                dropped[example.source] += 1
                continue
            seen_stems.add(stem)
            new_hashes.append(bits)
            kept.append(example)
        seen_hashes = np.concatenate([seen_hashes, np.array(new_hashes, dtype=np.uint64)])
    return kept, dict(dropped)


def load_orchard_detection(external_root: Path, required: bool = False) -> list[DetectionExample]:
    """Load only completed, checked imports; pose labels have already become boxes."""
    examples = []
    for source, species_id in ORCHARD_SOURCES.items():
        root = external_root / source
        if not root.exists() and not required:
            continue
        report_path, manifest_path = root / "import_report.json", root / "import_manifest.jsonl"
        if not report_path.is_file() or not manifest_path.is_file():
            raise ValueError(f"Incomplete orchard import: {root}. Run scripts/download_orchard_datasets.py first.")
        report = json.loads(report_path.read_text())
        records = [json.loads(line) for line in manifest_path.read_text().splitlines()]
        if len(records) != report["selected_images"] or not records:
            raise ValueError(f"Orchard manifest count mismatch: {root}")
        if len({record["source_image"] for record in records}) != len(records):
            raise ValueError(f"Duplicate orchard manifest entries: {root}")
        count = 0
        for record in records:
            image, label = root / record["image"], root / record["label"]
            if not image.is_file() or not label.is_file() or sha256_file(image) != record["sha256"]:
                raise ValueError(f"Missing or changed orchard file: {image}")
            # Require exactly five values: never reinterpret pose keypoints as polygons.
            if any(len(line.split()) != 5 for line in label.read_text().splitlines() if line.strip()):
                raise ValueError(f"Expected normalized detector boxes: {label}")
            boxes = read_yolo_boxes(label)
            if (any(box[0] != species_id for box in boxes)
                    or len(boxes) != len(record["boxes"])
                    or any(abs(a - b) > 1e-7 for box, saved in zip(boxes, record["boxes"]) for a, b in zip(box, saved))):
                raise ValueError(f"Changed orchard annotations: {label}")
            if not record["group"].startswith(source + ":"):
                raise ValueError(f"Invalid orchard group: {record['group']}")
            examples.append(DetectionExample(image, tuple(boxes), source, record["group"], record["sha256"]))
            count += len(boxes)
        if count != report["boxes"]:
            raise ValueError(f"Orchard annotation count mismatch: {root}")
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
            if xmax - xmin < 64 or ymax - ymin < 64:
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
                    group=f"dragon_maturity:{image_path.stem}",
                    content_hash=content_hash,
                )
            )
    return examples


def load_mango_ripening_stages(external_root: Path) -> list[ClassificationExample]:
    """Mendeley mm8g66d7rc: one harvested mango per photo, four ripening stages."""
    root = external_root / "mango_ripening_stages"
    examples = []
    for stage, class_name in MANGO_RIPENING_STAGE_MAP.items():
        if not (root / stage).is_dir():
            continue
        for image_path in sorted((root / stage).rglob("*")):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            # Photos were shot every 6-10 s on the same white table; neither timestamps
            # nor visual hashes separate repeat views of one fruit from different fruit
            # (reviewed 2026-09-29), so each photo is its own group. Repeat views may
            # cross splits, making this source's test accuracy somewhat optimistic.
            examples.append(
                ClassificationExample(
                    image=image_path,
                    class_name=class_name,
                    source="mendeley_mango_ripening",
                    group=f"mango_ripening:{stage}:{image_path.stem}",
                    content_hash=sha256_file(image_path),
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
        if not classification and stratum[0] == "dragon_fruit_orchard":
            # Recording lengths differ greatly (23 to 505 frames). Counting
            # groups equally can leave validation with just the shortest clip.
            # Allocate larger recordings first to the largest frame deficit.
            total_images = sum(len(group_examples[group]) for group in groups)
            assigned_images = Counter()
            split_order = list(split_ratios)
            rng.shuffle(split_order)
            for group in sorted(groups, key=lambda item: len(group_examples[item]), reverse=True):
                split_name = max(
                    split_order,
                    key=lambda split: total_images * split_ratios[split] - assigned_images[split],
                )
                assignments[group] = split_name
                assigned_images[split_name] += len(group_examples[group])
            continue
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
    if classification:
        return rebalance_classification_groups(group_examples, assignments)
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

    # Keep one image per original group outside training. Prefer the unmodified
    # Mendeley original over a Roboflow resize or augmentation of the same image.
    canonical_nontrain_image = {}
    image_classes = defaultdict(set)
    for example in examples:
        image_classes[example.image].add(example.class_name)
    for example in examples:
        if assignments[example.group] != "train":
            current = canonical_nontrain_image.get(example.group)
            candidate = (
                0 if example.source == "mendeley_dragon_maturity_original" else 1,
                -len(image_classes[example.image]),
                example.image.as_posix(),
            )
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
        if canonical is not None and example.image.as_posix() != canonical[-1]:
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
    detection_examples.extend(load_orchard_detection(args.external_root, getattr(args, "require_orchard_data", False)))
    detection_examples.extend(load_mango_farfield(args.external_root))
    extra_sources = []
    for spec in getattr(args, "extra_detection", None) or []:
        species, source, directory = spec.split(":", 2)
        if species not in ("mango", "dragonfruit"):
            raise SystemExit(f"--extra-detection species must be mango or dragonfruit: {spec}")
        extra_sources.append(load_extra_rf_detection(Path(directory), species, source))
    for spec in getattr(args, "negative", None) or []:
        source, directory = spec.split(":", 1)
        extra_sources.append(load_negative_images(Path(directory), source))
    extra_examples, cross_source_copies = drop_cross_source_copies(extra_sources)
    detection_examples.extend(extra_examples)
    mango_classifier_examples = load_mango_ripening_stages(args.external_root)
    dragon_classifier_examples = []
    dragon_curation = None

    if args.mango_rf:
        detection_examples.extend(load_rf_detection(args.mango_rf, "mango"))
        mango_classifier_examples.extend(load_rf_classifier(args.mango_rf, "mango", args.crop_padding))
    if args.dragon_rf:
        black_rot_root = getattr(args, "dragon_black_rot", None) or args.external_root / "dragon_fruit_black_rot"
        curated, detector_boxes, dragon_curation = curate_dragon(
            list(iter_rf_pairs(args.dragon_rf)), load_yaml_names(args.dragon_rf), read_yolo_boxes,
            black_rot_root, output / "maturity_audit", args.crop_padding,
        )
        image_hashes = {row["image"]: row["sha256"] for row in curated}
        for image_name, boxes in detector_boxes.items():
            image_path = Path(image_name)
            detection_examples.append(DetectionExample(
                image_path, tuple((1, *box[1:]) for box in boxes), "rf_dragonfruit_curated",
                rf_group_id(image_path, "rf_dragonfruit"), image_hashes.get(image_name) or sha256_file(image_path),
            ))
        dragon_classifier_examples = [ClassificationExample(
            image=Path(row["image"]), class_name=row["class_name"], source=row["source"],
            group=row["group"], content_hash=row["sha256"],
            crop_xyxy=tuple(row["crop_xyxy"]) if row["crop_xyxy"] else None,
            crop_index=row["crop_index"],
        ) for row in curated]

    detection_examples, detector_duplicates = deduplicate_detection(detection_examples)
    mango_classifier_examples, mango_duplicates = deduplicate_classification(mango_classifier_examples)
    dragon_classifier_examples, dragon_duplicates = deduplicate_classification(dragon_classifier_examples)

    report = {
        "data_revision": REVISION,
        "seed": args.seed,
        "detector_source_images": dict(sorted(Counter(example.source for example in detection_examples).items())),
        "mango_classifier_source_images": dict(sorted(Counter(example.source for example in mango_classifier_examples).items())),
        "rules": {
            "detector_classes": DETECTOR_NAMES,
            "mango_classifier_classes": MANGO_CLASS_NAMES,
            "dragon_classifier_classes": DRAGON_CLASS_NAMES,
            "standalone_dragon_quality_archive_used": False,
            "unreviewed_quality_labels_used_for_maturity": False,
            "classifier_minimum_crop_edge": 64,
            "dragon_classifier_uses_only_curated_subjects": True,
            "mendeley_augmented_images_used": False,
            "orchard_imports_detector_only": True,
            "dragon_orchard_recordings_balanced_by_frame_count": True,
            "mango_stage_mapping": {"rf_mango": MANGO_RF_MAP, "mendeley_mango_ripening": MANGO_RIPENING_STAGE_MAP},
            "mango_ripening_grouping": "per photo; repeat views of one fruit cannot be identified and may cross splits",
        },
        "dragon_curation": dragon_curation,
        "deduplication": {
            "detector_exact_duplicates_removed": detector_duplicates,
            "extra_source_cross_copies_removed": cross_source_copies,
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
    readiness = {"data_revision": REVISION, "stages": {
        "mango_classifier": audit_prepared_classifier(output / "mango_classifier", MANGO_CLASS_NAMES),
        "dragon_classifier": audit_prepared_classifier(output / "dragon_classifier", DRAGON_CLASS_NAMES),
    }, "field_evaluation": "Pending evaluation on independently collected target-orchard photos; automatic checks cannot certify all labels."}
    for stage in readiness["stages"]:
        manifest = output / stage / "manifest.csv"
        readiness["stages"][stage]["manifest_sha256"] = sha256_file(manifest) if manifest.is_file() else None
    (output / "data_readiness.json").write_text(json.dumps(readiness, indent=2) + "\n")
    report["maturity_ready_for_training_trial"] = {stage: audit["ready_for_training_trial"] for stage, audit in readiness["stages"].items()}
    (output / "preparation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-root", type=Path, default=Path("data/external/extracted"))
    parser.add_argument("--mango-rf", type=Path, help="Extracted mango Roboflow dataset directory")
    parser.add_argument("--dragon-rf", type=Path, help="Extracted dragon-fruit Roboflow dataset directory")
    parser.add_argument("--dragon-black-rot", type=Path, help="Checked original DF-MOD Black_Rot import")
    parser.add_argument("--output", type=Path, default=Path("data/prepared/two_stage"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--crop-padding", type=float, default=0.10)
    parser.add_argument("--mode", choices=("copy", "hardlink", "symlink"), default="copy")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--require-orchard-data", action="store_true", help="Require both checked orchard imports")
    parser.add_argument(
        "--extra-detection", action="append", metavar="SPECIES:SOURCE:DIR",
        help="Extra Roboflow YOLO export used only for detector boxes, e.g. dragonfruit:rf_pitaya_orchard:/path",
    )
    parser.add_argument(
        "--negative", action="append", metavar="SOURCE:DIR",
        help="Folder of images with no mango/dragon fruit (other fruit, flowers); added to the detector with empty labels",
    )
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    result = prepare(parsed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
