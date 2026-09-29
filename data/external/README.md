# Public external datasets

This directory tracks open datasets used to extend the fruit-detection project.
Large archives and extracted files are intentionally ignored by Git.

## Reproduce the download

From the repository root:

```bash
bash scripts/download_public_datasets.sh
python3 scripts/download_orchard_datasets.py
```

The shell script resumes interrupted downloads, verifies the publisher checksum, and
extracts each archive under `data/external/extracted/<dataset_id>/`.
The orchard importer selects usable labeled originals from two additional ZIPs
using HTTP ranges, verifies each selected member's CRC, and saves normalized
images/boxes plus provenance. It supports resuming and optional `--cache-dir`.
See `training/README.md` for its connection to Colab steps 3–5.

Create or refresh the local inventory after extraction:

```bash
python3 scripts/audit_public_datasets.py
```

The resulting `audit_report.json` records image counts, file types, directory
classes, Pascal VOC object totals, and COCO annotation totals.

Source URLs, licenses, archive sizes, checksums, intended tasks, and known
limitations are recorded in `datasets.json`.

## Local inventory (updated 2026-09-28)

| Dataset | Downloaded content | Recommended use |
| --- | --- | --- |
| MangoYOLO | 1,730 labelled orchard images; 15,281 fruit boxes | Mango detector and counting pretraining |
| On-tree mango segmentation | 542 canopy tiles with 5,314 mango masks; 1,200 cropped fruit snips | Dense/occluded mango localization; crop-level auxiliary data |
| Mango-branch segmentation | 250 canopy images; 2,567 mango masks plus branch masks | Mango/branch separation under occlusion |
| Mango deep-yield | 336 dual-side whole-tree images with harvest-count workbook | Independent whole-tree counting benchmark |
| Dragon-fruit maturity | 2,127 original images (1,241 immature, 886 mature) plus 5,010 augmented images | Crop classifier for mature vs immature |
| Dragon-fruit quality | 1,652 original images (898 fresh, 754 defect) plus 5,000 augmented images | Crop classifier for fresh vs defect |
| DF pose orchard subset | 2,448 original frames; 4,637 boxes; seven recordings | Small/occluded dragon-fruit detection; detector only |
| MangoFruitBD selected subset | 1,072 images; 1,841 boxes, including 24 background images; 1,070 unique image hashes | Daylight mango detection; detector only; noncommercial use |
| DF-MOD original fruit Black_Rot | 675 downloaded files; 270 distinct images; 405 exact copies excluded during preparation | Visible spoilage classifier; image labels only; no detector boxes |

The original public-source inventory is in `audit_report.json`. Each orchard
import has an `import_report.json` and `import_manifest.jsonl` in its extracted
directory. Two exact duplicate MangoFruitBD images are removed during preparation.
The orchard review and combined preparation checks are recorded in
[`orchard_audit_report.json`](orchard_audit_report.json).
Those counts describe the earlier orchard_v1 preparation. The newer
[`maturity_audit_report.json`](maturity_audit_report.json) supersedes its maturity
readiness assessment and records additional annotation cleanup. DF-MOD Black_Rot
has now been downloaded and checked against every publisher image SHA256. All
270 distinct images were screened in contact sheets; three additional pairs of
repeated views are grouped by their original hashes before splitting. These
groups do not establish independence of every photographed fruit.
COCO files
in the branch dataset expose multiple views of the same annotations (mango-only,
branch-only, and combined); their annotation counts must not be added together.

## Important training constraints

- The mango detection/segmentation sources do not provide four-stage ripeness
  labels. They can strengthen fruit localization and counting, but they cannot
  by themselves supervise `premature/early/mature/ripe`.
- The dragon-fruit maturity and quality sources are classification datasets.
  They can train a crop-level classifier after duplicate/augmentation cleanup,
  but they cannot directly train an orchard detector without bounding boxes.
- Do not randomly split augmented variants of the same original across train,
  validation, and test sets. Group them with their source image to prevent data
  leakage.
- Keep an untouched local-field test set. Internet accuracy is not a substitute
  for evaluation on the actual target orchard, camera, distance, and lighting.

MangoFruitBD's landing page specifies CC BY-NC 3.0; its archive README specifies
CC BY-NC 4.0. Both restrict use to noncommercial purposes. The other sources are
CC BY 4.0. Preserve source attribution when redistributing data or derived artifacts.
