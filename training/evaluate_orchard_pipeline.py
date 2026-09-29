#!/usr/bin/env python3
"""Evaluate saved models at the app's thresholds without training or deployment.

Uses deterministic samples from the prepared detector test split and candidate
Mango Branch test images after exact source duplicate exclusion. Ripeness has no ground truth in these orchard
datasets, so only detection and ripeness acceptance rates are reported.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image

from backend.two_stage import TwoStagePipeline, load_calibration


def match_boxes(detections, truth, threshold=0.5):
    """One-to-one, species-aware matches in descending confidence order."""
    used = set()
    matched = []
    for prediction in sorted(detections, key=lambda d: -d["detection_confidence"]):
        a = np.asarray(prediction["bbox"], dtype=float)
        best_iou, best = threshold, None
        for index, target in enumerate(truth):
            if index in used or target["species"] != prediction["species"]:
                continue
            b = np.asarray(target["bbox"], dtype=float)
            intersection = np.maximum(0, np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2])).prod()
            union = np.maximum(0, a[2:] - a[:2]).prod() + np.maximum(0, b[2:] - b[:2]).prod() - intersection
            iou = float(intersection / union) if union else 0
            if iou >= best_iou:
                best_iou, best = iou, index
        if best is not None:
            used.add(best)
            matched.append({"truth_index": best, "iou": best_iou,
                            "candidate_class": prediction["candidate_class"],
                            "uncertain": prediction["uncertain"]})
    return matched


def load_examples(data_root, branch_root, per_source):
    stages = ["detector", "mango_classifier", "dragon_classifier"]
    manifest_rows = []
    for stage in stages:
        with (data_root / stage / "manifest.csv").open() as handle:
            manifest_rows.extend(csv.DictReader(handle))
    seen_hashes = {row["sha256"] for row in manifest_rows}
    by_source = defaultdict(list)
    with (data_root / "detector/manifest.csv").open() as handle:
        for row in csv.DictReader(handle):
            if row["split"] == "test" and row["source"] in {
                "dragon_fruit_orchard", "mango_yolo", "mango_on_tree", "mango_orchard_daylight"
            }:
                by_source[row["source"]].append(row)
    examples = []
    for source, rows in sorted(by_source.items()):
        selected = random.Random(42).sample(sorted(rows, key=lambda r: r["output_image"]), min(per_source, len(rows)))
        for row in selected:
            path = data_root / "detector" / row["output_image"]
            with Image.open(path) as image:
                w, h = image.size
            labels = data_root / "detector/labels/test" / (path.stem + ".txt")
            unique = {tuple(map(float, line.split())) for line in labels.read_text().splitlines() if line.strip()}
            truth = []
            for category, x, y, bw, bh in sorted(unique):
                truth.append({"species": {0: "mango", 1: "dragonfruit"}[int(category)],
                              "bbox": [(x-bw/2)*w, (y-bh/2)*h, (x+bw/2)*w, (y+bh/2)*h]})
            examples.append({"path": str(path), "source": source, "split": "prepared_test_sample", "truth": truth})
    excluded = []
    if branch_root:
        payload = json.loads((branch_root / "labels/coco-json/test/test_mango_only.json").read_text())
        targets = defaultdict(list)
        for obj in payload["annotations"]:
            if obj["category_id"] != 1 or obj.get("iscrowd", 0):
                continue
            x, y, w, h = obj["bbox"]
            targets[obj["image_id"]].append({"species": "mango", "bbox": [x, y, x+w, y+h]})
        for row in payload["images"]:
            path = branch_root / "images/test" / row["file_name"]
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            if checksum in seen_hashes:
                excluded.append(str(path))
                continue
            examples.append({"path": str(path), "source": "mango_branch_external",
                             "split": "publisher_test_unused_source", "truth": targets[row["id"]]})
    return examples, excluded


def run(args):
    import torch
    from ultralytics import YOLO

    torch.set_num_threads(args.threads)
    models = [YOLO(str(args.run_root / stage / "weights/best.pt"))
              for stage in ["detector", "mango_classifier", "dragon_classifier"]]
    pipeline = TwoStagePipeline(*models,
        load_calibration(args.run_root / "mango_classifier/calibration.json"),
        load_calibration(args.run_root / "dragon_classifier/calibration.json"))
    examples, excluded = load_examples(args.data_root, args.branch_root, args.per_source)
    args.output.mkdir(parents=True, exist_ok=True)
    totals = defaultdict(Counter)
    rows = []
    for index, example in enumerate(examples):
        with Image.open(example["path"]) as opened:
            image = opened.convert("RGB")
        predictions, annotated = pipeline.predict(image, args.detection_threshold, args.ripeness_threshold)
        matches = match_boxes(predictions, example["truth"])
        counts = {"images": 1, "ground_truth": len(example["truth"]),
                  "predictions": len(predictions), "matched": len(matches),
                  "accepted_ripeness": sum(not d["uncertain"] for d in predictions),
                  "matched_accepted_ripeness": sum(not d["uncertain"] for d in matches)}
        totals[example["source"]].update(counts)
        if totals[example["source"]]["images"] <= 2:
            annotated.save(args.output / f'{example["source"]}_{totals[example["source"]]["images"]}.jpg')
        rows.append({**example, "counts": counts, "predictions": predictions, "matches": matches})
        if (index+1) % 10 == 0 or index+1 == len(examples):
            print(f"Evaluated {index+1}/{len(examples)} images", flush=True)
    summary = {}
    for source, c in totals.items():
        summary[source] = dict(c, precision=c["matched"]/c["predictions"] if c["predictions"] else None,
                               recall=c["matched"]/c["ground_truth"] if c["ground_truth"] else None,
                               ripeness_acceptance=c["accepted_ripeness"]/c["predictions"] if c["predictions"] else None)
    report = {"detection_threshold": args.detection_threshold, "ripeness_threshold": args.ripeness_threshold,
              "matching_iou": 0.5, "seed": 42, "per_source_sample": args.per_source,
              "excluded_external_exact_source_duplicates": excluded,
              "limitations": ["Ripeness ground truth is unavailable for these orchard images.",
                              "Unused-source exact byte hashes checked; related scenes/near copies are not ruled out.",
                              "Prepared test results are a deterministic sample, not the complete test set.",
                              "These are operating-point precision/recall, not mAP."], "sources": summary}
    (args.output / "orchard_summary.json").write_text(json.dumps(report, indent=2)+"\n")
    (args.output / "orchard_predictions.json").write_text(json.dumps(rows, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/prepared/two_stage_maturity_v2")
    parser.add_argument("--branch-root", type=Path, default=ROOT / "data/external/extracted/mango_branch_segmentation/mango-branch segmentation dataset")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-source", type=int, default=24)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--detection-threshold", type=float, default=0.25)
    parser.add_argument("--ripeness-threshold", type=float, default=0.8)
    run(parser.parse_args())
