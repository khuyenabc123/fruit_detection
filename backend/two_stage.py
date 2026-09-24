"""Two-stage inference: species detector followed by calibrated ripeness classifiers."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


MASTER_CLASS_IDS = {
    "mango_premature": 0,
    "mango_early": 1,
    "mango_mature": 2,
    "mango_ripe": 3,
    "dragonfruit_unripe": 4,
    "dragonfruit_ripe": 5,
    "dragonfruit_rotten": 6,
    "mango_uncertain": 7,
    "dragonfruit_uncertain": 8,
}


def load_calibration(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"temperature": 1.0, "class_thresholds": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    temperature = float(payload.get("temperature", 1.0))
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError(f"Invalid calibration temperature in {path}: {temperature}")
    return {
        "temperature": temperature,
        "class_thresholds": {
            str(name): float(value)
            for name, value in payload.get("class_thresholds", {}).items()
        },
    }


def calibrate_probabilities(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    log_probabilities = np.log(np.clip(probabilities.astype(np.float64), 1e-12, 1.0))
    logits = log_probabilities / temperature
    logits -= logits.max()
    calibrated = np.exp(logits)
    return calibrated / calibrated.sum()


class TwoStagePipeline:
    def __init__(
        self,
        detector: Any,
        mango_classifier: Any,
        dragon_classifier: Any,
        mango_calibration: dict[str, Any],
        dragon_calibration: dict[str, Any],
        crop_padding: float = 0.10,
    ) -> None:
        self.detector = detector
        self.classifiers = {
            "mango": mango_classifier,
            "dragonfruit": dragon_classifier,
        }
        self.calibrations = {
            "mango": mango_calibration,
            "dragonfruit": dragon_calibration,
        }
        self.crop_padding = crop_padding
        detector_names = {int(index): str(name) for index, name in detector.names.items()}
        if set(detector_names.values()) != {"mango", "dragonfruit"}:
            raise ValueError(
                "Two-stage detector must have exactly ['mango', 'dragonfruit']; "
                f"got {detector_names}"
            )
        self.detector_names = detector_names

    @property
    def output_names(self) -> list[str]:
        return list(MASTER_CLASS_IDS)

    def _padded_crop(self, image: Image.Image, xyxy: list[float]) -> tuple[Image.Image, list[float]]:
        width, height = image.size
        xmin, ymin, xmax, ymax = xyxy
        pad_x = (xmax - xmin) * self.crop_padding
        pad_y = (ymax - ymin) * self.crop_padding
        clipped = [
            max(0.0, xmin - pad_x),
            max(0.0, ymin - pad_y),
            min(float(width), xmax + pad_x),
            min(float(height), ymax + pad_y),
        ]
        crop = image.crop(tuple(round(value) for value in clipped))
        return crop, [xmin, ymin, xmax, ymax]

    def predict(
        self,
        image: Image.Image,
        detection_threshold: float,
        minimum_ripeness_confidence: float,
    ) -> tuple[list[dict[str, Any]], Image.Image]:
        detector_result = self.detector.predict(
            source=image,
            conf=detection_threshold,
            verbose=False,
        )[0]
        candidates = []
        crops_by_species: dict[str, list[tuple[int, Image.Image]]] = {
            "mango": [],
            "dragonfruit": [],
        }
        if detector_result.boxes is not None:
            for box in detector_result.boxes:
                detector_class_id = int(box.cls[0].item())
                species = self.detector_names[detector_class_id]
                xyxy = [float(value) for value in box.xyxy[0].cpu().numpy().tolist()]
                crop, original_xyxy = self._padded_crop(image, xyxy)
                candidate_index = len(candidates)
                candidates.append(
                    {
                        "species": species,
                        "bbox": original_xyxy,
                        "detection_confidence": float(box.conf[0].item()),
                    }
                )
                crops_by_species[species].append((candidate_index, crop))

        for species, indexed_crops in crops_by_species.items():
            if not indexed_crops:
                continue
            classifier = self.classifiers[species]
            calibration = self.calibrations[species]
            results = classifier.predict(
                source=[crop for _, crop in indexed_crops],
                imgsz=320,
                batch=min(32, len(indexed_crops)),
                verbose=False,
            )
            class_names = {int(index): str(name) for index, name in classifier.names.items()}
            for (candidate_index, _), result in zip(indexed_crops, results):
                raw = result.probs.data.cpu().numpy()
                calibrated = calibrate_probabilities(raw, calibration["temperature"])
                predicted_id = int(calibrated.argmax())
                predicted_name = class_names[predicted_id]
                confidence = float(calibrated[predicted_id])
                calibrated_threshold = float(
                    calibration["class_thresholds"].get(predicted_name, 0.0)
                )
                required = max(minimum_ripeness_confidence, calibrated_threshold)
                uncertain = confidence < required
                final_name = f"{species}_uncertain" if uncertain else predicted_name
                candidates[candidate_index].update(
                    {
                        "class_id": MASTER_CLASS_IDS[final_name],
                        "class_name": final_name,
                        "confidence": confidence,
                        "ripeness_confidence": confidence,
                        "uncertain": uncertain,
                        "candidate_class": predicted_name,
                        "required_ripeness_confidence": required,
                    }
                )

        detections = []
        for candidate in candidates:
            if "class_name" not in candidate:
                continue
            detections.append(
                {
                    **candidate,
                    "confidence": round(candidate["confidence"], 4),
                    "ripeness_confidence": round(candidate["ripeness_confidence"], 4),
                    "detection_confidence": round(candidate["detection_confidence"], 4),
                    "required_ripeness_confidence": round(
                        candidate["required_ripeness_confidence"], 4
                    ),
                    "bbox": [round(value, 2) for value in candidate["bbox"]],
                }
            )
        return detections, self.annotate(image, detections)

    @staticmethod
    def annotate(image: Image.Image, detections: list[dict[str, Any]]) -> Image.Image:
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        for detection in detections:
            color = "#f59e0b" if detection["uncertain"] else "#22c55e"
            xmin, ymin, xmax, ymax = detection["bbox"]
            draw.rectangle((xmin, ymin, xmax, ymax), outline=color, width=3)
            label = (
                f"{detection['class_name']} "
                f"{detection['ripeness_confidence'] * 100:.0f}%"
            )
            text_box = draw.textbbox((xmin, ymin), label)
            text_height = text_box[3] - text_box[1] + 6
            text_width = text_box[2] - text_box[0] + 8
            label_y = max(0, ymin - text_height)
            draw.rectangle((xmin, label_y, xmin + text_width, label_y + text_height), fill=color)
            draw.text((xmin + 4, label_y + 3), label, fill="black")
        return annotated


def count_detections(detections: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(detection["class_name"] for detection in detections)
    return {name: counts.get(name, 0) for name in MASTER_CLASS_IDS}
