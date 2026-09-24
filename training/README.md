# Two-stage training pipeline

The recommended architecture is:

```text
whole-tree image
  -> detector: mango / dragonfruit
  -> crop every detected fruit
  -> species-specific maturity classifier
  -> calibrated threshold
  -> maturity label or *_uncertain
```

This keeps counting/localization separate from visually subtle maturity stages.
The existing seven-class detector remains available as a legacy baseline.

## Colab workflow

Open `train_two_stage_colab.ipynb`, enable a T4 GPU, and run each cell in order.
The notebook deliberately separates detector, mango-classifier, and
dragon-classifier training so each can be resumed independently.

Before running it, place these existing exports in Google Drive:

```text
MyDrive/fruit_data/mango_dataset.zip
MyDrive/fruit_data/dragonfruit_dataset.zip
```

Public CC BY archives are downloaded once and cached under
`MyDrive/fruit_data/public_raw/`. Each Colab runtime extracts them to `/content`
for faster preparation and training. Checkpoints, calibration files, test plots,
and split manifests are stored under `MyDrive/fruit_two_stage/`.
The minimal training cache is about 1.4 GB; the unused quality/branch/deep-yield
archives are not downloaded by the Colab notebook.

## Data rules enforced by the preparation script

- MangoYOLO and on-tree mango masks are used only for the species detector.
- Mendeley maturity originals add dragon-fruit `unripe/ripe` classifier data.
- Offline Mendeley augmentations are excluded; augmentation is applied only to
  the training split at training time.
- `fresh/defect` is not mapped to `ripe/rotten`, because those labels are not
  semantically equivalent.
- Roboflow variants sharing the part before `.rf.` stay in one split.
- Exact image duplicates are removed before splitting.
- Classifiers have separate train, validation, calibration, and test splits.
- Validation/calibration/test keep only one Roboflow variant per original group.

The training command refuses to start if either detector species or any
maturity class is absent from a split.

## Artifacts to copy back after Colab training

```text
fruit_two_stage/runs/detector/weights/best.pt
  -> backend/weights/detector.pt

fruit_two_stage/runs/mango_classifier/weights/best.pt
  -> backend/weights/mango_classifier.pt
fruit_two_stage/runs/mango_classifier/calibration.json
  -> backend/weights/mango_calibration.json

fruit_two_stage/runs/dragon_classifier/weights/best.pt
  -> backend/weights/dragon_classifier.pt
fruit_two_stage/runs/dragon_classifier/calibration.json
  -> backend/weights/dragon_calibration.json
```

When all three weights are present, the FastAPI service automatically switches
from the legacy model to the two-stage pipeline.

## Confidence behavior

The detector threshold stays relatively low (default `0.25`) to avoid missing
small or occluded fruit. It is not presented as maturity certainty. The crop
classifier is temperature-calibrated and uses both a learned per-class threshold
and an API minimum (default `0.80`). Predictions below either threshold become
`mango_uncertain` or `dragonfruit_uncertain` instead of being forced into an
incorrect maturity class.
