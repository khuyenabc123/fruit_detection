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
The notebook includes a checksum-verified copy of its seven training helper
files. Step 1 restores them under `/content/fruit_detection_maturity_v2/`, so
opening this updated notebook does not depend on publishing local Git changes.

Before running it, place these existing exports in Google Drive:

```text
MyDrive/fruit_data/mango_dataset.zip
MyDrive/fruit_data/dragonfruit_dataset.zip
```

The original CC BY archives are downloaded once and cached under
`MyDrive/fruit_data/public_raw/`. Each Colab runtime extracts them to `/content`
for faster preparation and training. Checkpoints, calibration files, test plots,
and split manifests are stored under `MyDrive/fruit_two_stage/`.
The current `two-stage-curated` profile downloads about 369 MB of MangoYOLO and
on-tree mango archives. The unused maturity/quality/branch/deep-yield
archives are not downloaded by the Colab notebook.

Step 3 also downloads the selected labeled orchard subsets described below and
caches compact ZIPs under `MyDrive/fruit_data/orchard_cache/`. Step 4 requires both
imports to be complete. Their images are decoded and resized with aspect ratio
preserved to at most 1600 pixels per edge; normalized boxes remain aligned.
The first download fetches several GB of source image bytes without retaining
the full source archives. Later sessions restore the smaller cached imports.

Step 3B imports only the 675 original fruit `Black_Rot` images described by
[DF-MOD v1](https://data.mendeley.com/datasets/kpsywfwkrf/1), CC BY 4.0, by
MD. Fahiz Siddikur Pranto, Anamika Dhar, and Rokonozzaman Ayon. Other disease,
healthy, stem, and augmented categories are excluded. The publisher serves
individual images in `Dragon Fruit/Fruit/Black_Rot`, alongside a separate
`Dragon Fruit Balanced` tree. The notebook selects the original folder, checks
the count, verifies each downloaded image against its publisher size and SHA256,
decodes it, and caches the import. A local original ZIP is also supported using
`--archive`; that route checks member CRCs. Failed/incomplete imports cannot pass
the maturity gate. Black rot covers one spoilage condition, not every cause of rot.

The completed local download contains 675 files but only **270 distinct images**;
405 exact copies are removed during preparation. All 270 distinct images were
screened in contact sheets for visible decay. Three additional pairs of repeated
views were visually confirmed and assigned shared groups using the original
publisher hashes. Image groups are not verified counts of independent fruits or
farms; an independent orchard test is still required.

This revision uses `fruit_two_stage/runs_maturity_v2/` and
`fruit_two_stage/manifests_maturity_v2/`. Start fresh runs because detector labels,
classifier crops, splits, and augmentation settings changed. Earlier runs remain
available. After a disconnect, rerun steps 1–5 before continuing step 6. Local
data is not automatically uploaded; Colab downloads/restores its own copies.

## Data rules enforced by the preparation script

- MangoYOLO and on-tree mango masks are used only for the species detector.
- DF pose orchard boxes and MangoFruitBD disease boxes are mapped only to the
  species detector; pose/disease classes never become maturity classes.
- Dragon orchard frames from the same recording stay in one split. Recordings
  are allocated by frame count so a short clip cannot dominate validation.
- Dragon classifier crops must contain an isolated, dominant fruit. Its RF label
  must agree with its `Immature`/`Mature` source identity. Uncropped legacy
  maturity images are no longer mixed into this classifier.
- Offline Mendeley augmentations are excluded; augmentation is applied only to
  the training split at training time.
- `fresh/defect` is not mapped to `ripe/rotten`, because those labels are not
  semantically equivalent.
- Roboflow variants sharing the part before `.rf.` stay in one split.
- Exact image duplicates are removed before splitting.
- Similar dragon crops, including mirrored copies, are grouped using a visual
  hash and color thumbnail. Conflicting classes within a cluster are quarantined.
  This is a heuristic, not proof that every view of the same fruit was found.
- The three reviewed pairs of DF-MOD repeated views, including their exact-copy
  aliases, stay in the same split even when visual hashes differ.
- Classifiers have separate train, validation, calibration, and test splits.
- Validation/calibration/test keep only one Roboflow variant per original group.
- Crops smaller than 64 pixels on either edge are excluded from classification.
- Classifier augmentation disables `auto_augment`, making `hsv_h=0` effective;
  no synthetic labels or augmented evaluation images are generated.

The corresponding training stage refuses to start if its required classes or
maturity audit are missing. A blocked dragon classifier does not prevent detector
training. Classifier audits check decoded-image duplication, conflicting labels,
crop sizes, split overlap, and minimum source groups: **80 train, 20 validation,
20 calibration, 20 test per class**. These are explicit trial floors, not a
statistical guarantee. Whole source groups are reassigned when needed to meet
evaluation floors; no duplicates are created to inflate counts.

Step 5 prints `READY FOR TRIAL` or `BLOCKED`, displays sample crops and rejected
examples, and saves `data_readiness.json`, `curation_report.json`,
`candidates.jsonl`, `quarantine.csv`, and sample sheets to Drive. A successful
automatic audit still requires testing on independent target-orchard photographs.

## Data audit before retraining

The downloaded `dragonfruit_dataset.zip` contains YOLO segmentation polygons
for most labels, despite its `.yolov8` folder name. The preparation script now
converts each polygon to a bounding box before building detector labels and
classifier crops. It also groups Roboflow copies of Mendeley maturity originals
with their source images so they cannot cross classifier splits. Regenerate the
prepared data and retrain any detector or dragon classifier made with the older
preparation script; those checkpoints used incorrect boxes/crops.

The RF audit found 145 annotation/source-label disagreements and 703 boxes below
1% of image area. Visual checks exposed green stems/tips labeled `Unripe` and
tiny detached fragments labeled `Rotten`. The curator keeps isolated dominant
fruit boxes and quarantines ambiguous multi-object images. `Fresh` and `Defect`
images are excluded from maturity classification; their isolated fruit boxes can
still supervise species detection. Keep orchard
images from the target camera and field out of training for a real-world test.
The new labeled orchard subsets add wider dragon-fruit plant views and daylight
mango views. The split/class count audit alone
cannot establish that the data matches the intended deployment scenes.

## Labeled orchard additions

```bash
python3 scripts/download_orchard_datasets.py
python3 scripts/download_dragon_black_rot.py
python3 training/prepare_two_stage_data.py \
  --mango-rf /path/to/mango/export --dragon-rf /path/to/dragon/export \
  --require-orchard-data --output data/prepared/two_stage_maturity_v2
```

- [DF pose v2](https://data.mendeley.com/datasets/t8kbmg6cgz/2), Xing Yang,
  CC BY 4.0: select original `HD1080` orchard frames with matching valid labels;
  discard augmentation, reused maturity photos, and unlabeled images. Pose
  labels contain boxes followed by keypoints; only the box is retained.
- [MangoFruitBD v2](https://data.mendeley.com/datasets/bhrz29mkmr/2), Ariful Islam
  et al.: select daylight orchard images and explicitly labeled background
  negatives; exclude the controlled-background/augmented Alternaria category.
  The landing page specifies CC BY-NC 3.0; the archive README says CC BY-NC 4.0.
  Both restrict use to noncommercial purposes. Preserve attribution.

Each import retains original label text, source filenames and image hashes,
normalized labels, an `import_manifest.jsonl`, and an `import_report.json` under
`data/external/extracted/<source>/`. The downloader supports interruption/resume
and checks selected ZIP member CRCs. The full-archive SHA256 is publisher metadata,
not a verification claim for a selectively downloaded archive.

These are supplements: the inspected dragon frames mostly show red fruit, and
the frames come from only seven recording names
and some visible partial/distant fruits are unlabeled in inspected samples. Mango
adds daylight variety but still includes many closeups; capture/tree grouping is
unavailable. An independent target-orchard test remains necessary. No new manual
labeling is needed to import these datasets, but visual sample checks cannot
certify that every object in every source image is labeled.

## Artifacts to copy back after Colab training

```text
fruit_two_stage/runs_maturity_v2/detector/weights/best.pt
  -> backend/weights/detector.pt

fruit_two_stage/runs_maturity_v2/mango_classifier/weights/best.pt
  -> backend/weights/mango_classifier.pt
fruit_two_stage/runs_maturity_v2/mango_classifier/calibration.json
  -> backend/weights/mango_calibration.json

fruit_two_stage/runs_maturity_v2/dragon_classifier/weights/best.pt
  -> backend/weights/dragon_classifier.pt
fruit_two_stage/runs_maturity_v2/dragon_classifier/calibration.json
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

## Updating notebook helpers

After editing any bundled helper, run `python3 scripts/embed_colab_helpers.py`.
`python3 -m unittest discover -s training -p 'test_*.py'` checks curation,
download selection, training gates, and that the embedded helpers match the source.
