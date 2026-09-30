"""The fp16 BatchNorm clipping guard picks the float32 copy or refuses clipped weights."""

import tempfile
import unittest
from pathlib import Path

import torch

from train_two_stage import saturated_batchnorm, usable_best


def save_model(path: Path, variance: float, half: bool) -> None:
    model = torch.nn.Sequential(torch.nn.Conv2d(3, 4, 1), torch.nn.BatchNorm2d(4))
    model[1].running_var.fill_(variance)
    torch.save({"model": model.half() if half else model}, path)


class Fp16GuardTests(unittest.TestCase):
    def test_clipped_best_falls_back_to_float32_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            best = Path(directory) / "best.pt"
            save_model(best, 250000.0, half=True)  # fp16 storage clips to 65504
            self.assertEqual(saturated_batchnorm(best), ["1"])
            with self.assertRaises(ValueError):
                usable_best(best)
            save_model(best.with_name("best_fp32.pt"), 250000.0, half=False)
            self.assertEqual(usable_best(best), best.with_name("best_fp32.pt"))

    def test_healthy_best_is_used_as_is(self):
        with tempfile.TemporaryDirectory() as directory:
            best = Path(directory) / "best.pt"
            save_model(best, 28448.0, half=True)
            self.assertEqual(usable_best(best), best)


if __name__ == "__main__":
    unittest.main()
