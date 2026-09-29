"""Checks for the maturity_v3 mango sources: visible stages, grouping, augmentation copies."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from prepare_two_stage_data import (
    MANGO_CLASS_NAMES,
    MANGO_RF_MAP,
    load_extra_rf_detection,
    load_mango_farfield,
    load_mango_ripening_stages,
)


def write_image(path: Path, color=(0, 128, 0)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 80), color).save(path)


class MangoStageMappingTests(unittest.TestCase):
    def test_age_stages_merge_into_visible_young(self):
        self.assertEqual(MANGO_RF_MAP["premature"], "mango_young")
        self.assertEqual(MANGO_RF_MAP["early-fruit"], "mango_young")
        self.assertEqual(set(MANGO_RF_MAP.values()) | {"mango_turning"}, set(MANGO_CLASS_NAMES))

    def test_ripening_stages_map_and_group_by_minute(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "mango_ripening_stages"
            write_image(base / "stage0/Training/IMG20200713144302.jpg", (0, 120, 0))
            write_image(base / "stage0/Training/IMG20200713144359.jpg", (0, 121, 0))
            write_image(base / "stage1/Test/IMG20200714100000.jpg", (10, 130, 0))
            write_image(base / "stage2/Training/IMG20200715100000.jpg", (150, 150, 0))
            write_image(base / "stage3/Training/IMG20200716100000.jpg", (230, 180, 0))
            examples = load_mango_ripening_stages(root)
        by_name = {example.image.name: example for example in examples}
        self.assertEqual(by_name["IMG20200713144302.jpg"].class_name, "mango_mature")
        self.assertEqual(by_name["IMG20200714100000.jpg"].class_name, "mango_mature")
        self.assertEqual(by_name["IMG20200715100000.jpg"].class_name, "mango_turning")
        self.assertEqual(by_name["IMG20200716100000.jpg"].class_name, "mango_ripe")
        # Two shots in the same minute share a group, so they cannot straddle splits.
        self.assertEqual(by_name["IMG20200713144302.jpg"].group, by_name["IMG20200713144359.jpg"].group)


class DetectorSourceTests(unittest.TestCase):
    def test_farfield_groups_consecutive_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "mango_farfield/Mango_Dataset/Far_Field"
            for number, color in ((101, (0, 100, 0)), (109, (0, 101, 0)), (110, (0, 102, 0))):
                write_image(base / f"images/image_{number}.png", color)
                (base / "labels").mkdir(parents=True, exist_ok=True)
                (base / f"labels/image_{number}.txt").write_text("0 0.5 0.5 0.1 0.1\n")
            write_image(base / "images/image_200.png", (0, 103, 0))  # unlabeled: skipped
            examples = load_mango_farfield(root)
        groups = {example.image.stem: example.group for example in examples}
        self.assertEqual(set(groups), {"image_101", "image_109", "image_110"})
        self.assertEqual(groups["image_101"], groups["image_109"])
        self.assertNotEqual(groups["image_109"], groups["image_110"])

    def test_extra_roboflow_keeps_one_copy_per_original_as_species_box(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for split, suffix, color in (("train", "aaa", (1, 1, 1)), ("train", "bbb", (2, 2, 2)), ("valid", "ccc", (3, 3, 3))):
                name = "tree_jpg.rf." + suffix if suffix != "ccc" else "other_jpg.rf." + suffix
                write_image(root / split / "images" / f"{name}.jpg", color)
                (root / split / "labels").mkdir(parents=True, exist_ok=True)
                (root / split / "labels" / f"{name}.txt").write_text("3 0.5 0.5 0.2 0.2\n")
            examples = load_extra_rf_detection(root, "dragonfruit", "rf_pitaya")
        self.assertEqual(len(examples), 2)
        self.assertTrue(all(box[0] == 1 for example in examples for box in example.boxes))


if __name__ == "__main__":
    unittest.main()
