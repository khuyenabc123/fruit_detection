#!/usr/bin/env python3
"""Train detector + per-species classifiers and calibrate classifier confidence."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
EXPECTED_DETECTOR_CLASSES = {0: "mango", 1: "dragonfruit"}
EXPECTED_CLASSIFIER_CLASSES = {
    "mango": ["mango_premature", "mango_early", "mango_mature", "mango_ripe"],
    "dragon": ["dragonfruit_unripe", "dragonfruit_ripe", "dragonfruit_rotten"],
}


def image_files(path: Path) -> list[Path]:
    return sorted(
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file() and candidate.suffix.lower() in IMAGE_SUFFIXES
    )


def validate_detector_dataset(data_yaml: Path) -> None:
    import yaml

    payload = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    root = Path(payload.get("path", data_yaml.parent))
    if not root.is_absolute():
        root = (data_yaml.parent / root).resolve()
    names = payload.get("names", {})
    if isinstance(names, list):
        names = dict(enumerate(names))
    names = {int(index): name for index, name in names.items()}
    if names != EXPECTED_DETECTOR_CLASSES:
        raise ValueError(f"Detector classes must be {EXPECTED_DETECTOR_CLASSES}, got {names}")

    for split_key in ("train", "val", "test"):
        image_dir = root / payload[split_key]
        label_dir = root / "labels" / ("val" if split_key == "val" else split_key)
        counts = Counter()
        for label_path in label_dir.glob("*.txt"):
            for line in label_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    counts[int(line.split()[0])] += 1
        missing = [name for class_id, name in names.items() if counts[class_id] == 0]
        if missing:
            raise ValueError(
                f"Detector split '{split_key}' has no boxes for {missing}. "
                "Supply the dragon-fruit Roboflow dataset before training."
            )
        print(f"detector/{split_key}: images={len(image_files(image_dir))}, boxes={sum(counts.values())}, {dict(counts)}")


def validate_classifier_dataset(root: Path, species: str) -> None:
    expected = EXPECTED_CLASSIFIER_CLASSES[species]
    for split in ("train", "val", "calib", "test"):
        counts = {class_name: len(image_files(root / split / class_name)) for class_name in expected}
        missing = [class_name for class_name, count in counts.items() if count == 0]
        if missing:
            raise ValueError(
                f"{species} classifier split '{split}' has no images for {missing}. "
                "The public data alone is insufficient; supply the matching Roboflow dataset."
            )
        print(f"{species}_classifier/{split}: {counts}")


def train_detector(data_yaml: Path, project: Path, args: argparse.Namespace) -> Path:
    from ultralytics import YOLO

    last = project / "detector" / "weights" / "last.pt"
    if args.resume and last.is_file():
        print(f"Resuming detector from {last}")
        YOLO(str(last)).train(resume=True)
    else:
        model = YOLO(args.detector_base)
        model.train(
            data=str(data_yaml),
            epochs=args.detector_epochs,
            imgsz=args.detector_imgsz,
            batch=args.detector_batch,
            device=args.device,
            project=str(project),
            name="detector",
            exist_ok=True,
            pretrained=True,
            optimizer="AdamW",
            patience=25,
            seed=args.seed,
            deterministic=True,
            hsv_h=0.0,
            hsv_s=0.5,
            hsv_v=0.35,
            degrees=7.0,
            translate=0.1,
            scale=0.4,
            fliplr=0.5,
            mosaic=0.5,
            close_mosaic=10,
            workers=args.workers,
            plots=True,
        )
    best = project / "detector" / "weights" / "best.pt"
    model = YOLO(str(best))
    model.val(
        data=str(data_yaml),
        split="test",
        imgsz=args.detector_imgsz,
        batch=args.detector_batch,
        device=args.device,
        project=str(project),
        name="detector_test",
        exist_ok=True,
        plots=True,
    )
    return best


def train_classifier(
    dataset_root: Path,
    species: str,
    project: Path,
    args: argparse.Namespace,
) -> Path:
    from ultralytics import YOLO

    run_name = f"{species}_classifier"
    last = project / run_name / "weights" / "last.pt"
    if args.resume and last.is_file():
        print(f"Resuming {species} classifier from {last}")
        YOLO(str(last)).train(resume=True)
    else:
        model = YOLO(args.classifier_base)
        model.train(
            data=str(dataset_root),
            epochs=args.classifier_epochs,
            imgsz=args.classifier_imgsz,
            batch=args.classifier_batch,
            device=args.device,
            project=str(project),
            name=run_name,
            exist_ok=True,
            pretrained=True,
            optimizer="AdamW",
            patience=15,
            seed=args.seed,
            deterministic=True,
            hsv_h=0.0,
            hsv_s=0.35,
            hsv_v=0.25,
            degrees=10.0,
            translate=0.08,
            scale=0.25,
            fliplr=0.5,
            erasing=0.1,
            workers=args.workers,
            plots=True,
        )
    best = project / run_name / "weights" / "best.pt"
    model = YOLO(str(best))
    model.val(
        data=str(dataset_root),
        split="test",
        imgsz=args.classifier_imgsz,
        batch=args.classifier_batch,
        device=args.device,
        project=str(project),
        name=f"{run_name}_test",
        exist_ok=True,
        plots=True,
    )
    return best


def softmax(logits: np.ndarray) -> np.ndarray:
    import numpy as np

    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


def expected_calibration_error(probabilities: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    import numpy as np

    confidence = probabilities.max(axis=1)
    predictions = probabilities.argmax(axis=1)
    edges = np.linspace(0.0, 1.0, bins + 1)
    error = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (confidence > lower) & (confidence <= upper)
        if not mask.any():
            continue
        accuracy = (predictions[mask] == labels[mask]).mean()
        error += mask.mean() * abs(accuracy - confidence[mask].mean())
    return float(error)


def choose_class_thresholds(
    probabilities: np.ndarray,
    labels: np.ndarray,
    class_names: dict[int, str],
    target_precision: float,
) -> dict[str, float]:
    import numpy as np

    predictions = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    thresholds = {}
    for class_id, class_name in class_names.items():
        candidate_mask = predictions == class_id
        candidate_confidence = confidence[candidate_mask]
        candidate_correct = labels[candidate_mask] == class_id
        if len(candidate_confidence) == 0:
            thresholds[class_name] = 1.0
            continue
        order = np.argsort(-candidate_confidence)
        ordered_confidence = candidate_confidence[order]
        ordered_correct = candidate_correct[order]
        cumulative_precision = np.cumsum(ordered_correct) / np.arange(1, len(order) + 1)
        minimum_support = min(len(order), max(5, math.ceil(len(order) * 0.10)))
        valid = [
            index
            for index, precision in enumerate(cumulative_precision)
            if index + 1 >= minimum_support and precision >= target_precision
        ]
        if not valid:
            thresholds[class_name] = 1.0
        else:
            # Largest accepted prefix gives the best coverage at the requested precision.
            thresholds[class_name] = round(float(ordered_confidence[max(valid)]), 6)
    return thresholds


def calibrate_classifier(
    weights: Path,
    dataset_root: Path,
    output_path: Path,
    args: argparse.Namespace,
) -> dict:
    import numpy as np
    from scipy.optimize import minimize_scalar

    from ultralytics import YOLO

    model = YOLO(str(weights))
    class_names = {int(index): name for index, name in model.names.items()}
    name_to_id = {name: index for index, name in class_names.items()}
    paths = []
    labels = []
    for class_name, class_id in name_to_id.items():
        class_paths = image_files(dataset_root / "calib" / class_name)
        paths.extend(class_paths)
        labels.extend([class_id] * len(class_paths))
    if not paths:
        raise ValueError(f"Calibration split is empty: {dataset_root / 'calib'}")

    order = np.argsort([path.as_posix() for path in paths])
    paths = [paths[index] for index in order]
    labels_array = np.asarray([labels[index] for index in order], dtype=np.int64)
    results = model.predict(
        source=[str(path) for path in paths],
        imgsz=args.classifier_imgsz,
        batch=args.classifier_batch,
        device=args.device,
        verbose=False,
    )
    probabilities = np.stack([result.probs.data.cpu().numpy() for result in results])
    log_probabilities = np.log(np.clip(probabilities, 1e-12, 1.0))

    def objective(temperature: float) -> float:
        calibrated = softmax(log_probabilities / temperature)
        return float(-np.log(np.clip(calibrated[np.arange(len(labels_array)), labels_array], 1e-12, 1.0)).mean())

    optimization = minimize_scalar(objective, bounds=(0.05, 10.0), method="bounded")
    temperature = float(optimization.x)
    calibrated = softmax(log_probabilities / temperature)
    thresholds = choose_class_thresholds(
        calibrated,
        labels_array,
        class_names,
        target_precision=args.target_precision,
    )
    payload = {
        "weights": str(weights),
        "temperature": round(temperature, 6),
        "target_precision": args.target_precision,
        "class_names": class_names,
        "class_thresholds": thresholds,
        "calibration_samples": len(labels_array),
        "accuracy_before": round(float((probabilities.argmax(axis=1) == labels_array).mean()), 6),
        "accuracy_after": round(float((calibrated.argmax(axis=1) == labels_array).mean()), 6),
        "ece_before": round(expected_calibration_error(probabilities, labels_array), 6),
        "ece_after": round(expected_calibration_error(calibrated, labels_array), 6),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def run(args: argparse.Namespace) -> dict:
    detector_yaml = args.dataset_root / "detector" / "data.yaml"
    mango_root = args.dataset_root / "mango_classifier"
    dragon_root = args.dataset_root / "dragon_classifier"
    args.project.mkdir(parents=True, exist_ok=True)

    validate_detector_dataset(detector_yaml)
    validate_classifier_dataset(mango_root, "mango")
    validate_classifier_dataset(dragon_root, "dragon")

    outputs = {}
    if not args.skip_detector:
        outputs["detector"] = str(train_detector(detector_yaml, args.project, args))
    if not args.skip_mango_classifier:
        mango_weights = train_classifier(mango_root, "mango", args.project, args)
        outputs["mango_classifier"] = str(mango_weights)
        outputs["mango_calibration"] = calibrate_classifier(
            mango_weights,
            mango_root,
            args.project / "mango_classifier" / "calibration.json",
            args,
        )
    if not args.skip_dragon_classifier:
        dragon_weights = train_classifier(dragon_root, "dragon", args.project, args)
        outputs["dragon_classifier"] = str(dragon_weights)
        outputs["dragon_calibration"] = calibrate_classifier(
            dragon_weights,
            dragon_root,
            args.project / "dragon_classifier" / "calibration.json",
            args,
        )

    outputs_path = args.project / "pipeline_outputs.json"
    if outputs_path.is_file():
        previous = json.loads(outputs_path.read_text(encoding="utf-8"))
        previous.update(outputs)
        outputs = previous
    outputs_path.write_text(json.dumps(outputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--detector-base", default="yolov8s.pt")
    parser.add_argument("--classifier-base", default="yolov8s-cls.pt")
    parser.add_argument("--detector-epochs", type=int, default=100)
    parser.add_argument("--classifier-epochs", type=int, default=50)
    parser.add_argument("--detector-imgsz", type=int, default=960)
    parser.add_argument("--classifier-imgsz", type=int, default=320)
    parser.add_argument("--detector-batch", type=int, default=8)
    parser.add_argument("--classifier-batch", type=int, default=32)
    parser.add_argument("--target-precision", type=float, default=0.80)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-detector", action="store_true")
    parser.add_argument("--skip-mango-classifier", action="store_true")
    parser.add_argument("--skip-dragon-classifier", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    parsed = parse_args()
    print(json.dumps(run(parsed), ensure_ascii=False, indent=2))
