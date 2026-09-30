#!/usr/bin/env python3
"""Repair a YOLO detector whose BatchNorm variance was clipped when saved in fp16.

Ultralytics stores best.pt in half precision. A BatchNorm running_var above
65504 (the fp16 maximum) is clipped, and the model then outputs bogus boxes at
100% confidence (seen in the maturity_v4 detector run, job 5533271247212773376).
Only the clipped layers get fresh statistics: a cumulative average over training
images at the training size, with every weight left unchanged. The result is
saved in float32.

Usage:
  python scripts/repair_batchnorm_fp16.py WEIGHTS DETECTOR_DATASET_DIR [--imgsz 1280] [--images 400]
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from ultralytics.data.augment import LetterBox

FP16_MAX = 65504.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("weights", type=Path)
    parser.add_argument("dataset", type=Path, help="Prepared detector folder containing manifest.csv")
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--images", type=int, default=400)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.weights.with_name(args.weights.stem + "_bnfix_fp32.pt")

    checkpoint = torch.load(args.weights, map_location="cpu", weights_only=False)
    net = checkpoint["model"].float().eval()
    clipped = {name: module for name, module in net.named_modules()
               if isinstance(module, torch.nn.BatchNorm2d) and float(module.running_var.max()) >= FP16_MAX * 0.999}
    if not clipped:
        raise SystemExit("No clipped BatchNorm layers found; nothing to repair.")
    print("clipped layers:", list(clipped))
    for module in clipped.values():
        module.reset_running_stats()
        module.momentum = None
        module.train()

    rows = [row for row in csv.DictReader((args.dataset / "manifest.csv").open()) if row["split"] == "train"]
    letterbox = LetterBox((args.imgsz, args.imgsz), auto=False)
    with torch.no_grad():
        for row in random.Random(0).sample(rows, min(args.images, len(rows))):
            bgr = np.array(Image.open(args.dataset / row["output_image"]).convert("RGB"))[:, :, ::-1]
            rgb = letterbox(image=bgr)[:, :, ::-1]
            net(torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1))).float()[None] / 255.0)
    for name, module in clipped.items():
        module.eval()
        print(f"{name}: running_var max {float(module.running_var.max()):.0f}")
    checkpoint["model"] = net
    checkpoint["bn_repair"] = {"layers": list(clipped), "images": args.images, "imgsz": args.imgsz}
    torch.save(checkpoint, output)
    print("saved", output)


if __name__ == "__main__":
    main()
