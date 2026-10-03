"""Regression checks for Roboflow labels and shared source-image groups."""

import tempfile
import unittest
import hashlib
import json
import sys
from pathlib import Path

from prepare_two_stage_data import DetectionExample, assign_group_splits, load_orchard_detection, read_yolo_boxes, rf_group_id

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.download_orchard_datasets import SOURCES, box_text, parse_boxes


class RoboflowLabelTests(unittest.TestCase):
    def test_polygon_becomes_enclosing_box(self):
        with tempfile.TemporaryDirectory() as directory:
            label = Path(directory) / "labels.txt"
            label.write_text("1 0.2 0.1 0.8 0.2 0.7 0.9 0.1 0.8\n")
            class_id, x, y, width, height = read_yolo_boxes(label)[0]
        self.assertEqual(class_id, 1)
        self.assertAlmostEqual(x, 0.45)
        self.assertAlmostEqual(y, 0.5)
        self.assertAlmostEqual(width, 0.7)
        self.assertAlmostEqual(height, 0.8)

    def test_standard_box_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            label = Path(directory) / "labels.txt"
            label.write_text("2 0.5 0.4 0.2 0.3\n")
            self.assertEqual(read_yolo_boxes(label), [(2, 0.5, 0.4, 0.2, 0.3)])

    def test_mendeley_copy_shares_group_with_roboflow(self):
        image = Path("Mature_Dragon_Original_Data0739_jpg.rf.abc123.jpg")
        self.assertEqual(
            rf_group_id(image, "rf_dragonfruit"),
            "dragon_maturity:Mature_Dragon_Original_Data0739",
        )


class OrchardImportTests(unittest.TestCase):
    def test_unequal_recordings_have_usable_held_out_splits(self):
        examples = []
        for index, frames in enumerate([505, 489, 441, 407, 324, 259, 23]):
            examples.extend([DetectionExample(Path('fixture.jpg'), ((1, 0.5, 0.5, 0.2, 0.2),),
                                               'dragon_fruit_orchard', f'clip:{index}', 'fixture')] * frames)
        ratios = {'train': 0.7, 'val': 0.15, 'test': 0.15}
        assignments = assign_group_splits(examples, ratios, 42, classification=False)
        self.assertEqual(len(assignments), 7)
        for split, ratio in ratios.items():
            count = sum(assignments[row.group] == split for row in examples)
            self.assertLess(abs(count / len(examples) - ratio), 0.05)
        self.assertEqual(assignments, assign_group_splits(examples, ratios, 42, classification=False))

    def test_pose_keypoints_are_not_polygon_coordinates(self):
        label = "0 0.5 0.4 0.2 0.3 0.4 0.3 2 0.6 0.3 2 0.5 0.4 1 0.5 0.5 2"
        boxes = parse_boxes(label, SOURCES["dragon_fruit_orchard"])
        self.assertEqual(len(boxes), 1)
        for actual, expected in zip(boxes[0], [1, 0.5, 0.4, 0.2, 0.3]):
            self.assertAlmostEqual(actual, expected)

    def test_disease_boxes_map_to_mango_only(self):
        boxes = parse_boxes("3 0.5 0.5 0.2 0.2", SOURCES["mango_orchard_daylight"])
        self.assertEqual(boxes[0][0], 0)
        self.assertEqual(parse_boxes("", SOURCES["mango_orchard_daylight"]), [])

    def test_invalid_geometry_is_rejected(self):
        for label in ["0 nan 0.5 0.2 0.2", "0 0.05 0.5 0.2 0.2", "0 0.5 0.5 -0.2 0.2"]:
            with self.subTest(label=label), self.assertRaises(ValueError):
                parse_boxes(label, SOURCES["mango_orchard_daylight"])

    def test_loader_rejects_partial_and_changed_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory)
            root = external / "dragon_fruit_orchard"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                load_orchard_detection(external)
            image, label = root / "image.jpg", root / "label.txt"
            image.write_bytes(b"verified image fixture")
            boxes = [[1, 0.5, 0.5, 0.2, 0.2]]
            label.write_text(box_text(boxes))
            record = {"image": image.name, "label": label.name, "boxes": boxes,
                      "source_image": "original.jpg", "group": "dragon_fruit_orchard:recording",
                      "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}
            (root / "import_manifest.jsonl").write_text(json.dumps(record) + "\n")
            (root / "import_report.json").write_text(json.dumps({"selected_images": 1, "boxes": 1}))
            self.assertEqual(len(load_orchard_detection(external)), 1)
            label.write_text("0 0.5 0.5 0.2 0.2\n")
            with self.assertRaisesRegex(ValueError, "Changed orchard"):
                load_orchard_detection(external)


if __name__ == "__main__":
    unittest.main()
