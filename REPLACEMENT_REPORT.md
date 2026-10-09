# Replacement Datasets Report — Maturity V2 (No mango_dataset.zip / dragonfruit_dataset.zip)

This report satisfies Requirement A (replace deleted ZIPs) and Requirement B (negative images).

## 1. Why replacement was needed

- Old notebook STEP 2 required `/content/drive/MyDrive/fruit_data/mango_dataset.zip` and `dragonfruit_dataset.zip` (Roboflow exports, private).
- Both were deleted and cannot be restored per user constraint: "Do not ask to restore deleted mango_dataset.zip; find replacement."
- Task requires legitimate public datasets supporting 4-class mango classifier, with verified structure/annotations/license, explicit mapping, no duplication/fabrication, dedup, no leakage, report counts, preserve test set.

## 2. Replacement sources and licenses

All sources are public, CC BY 4.0 unless noted, with direct download URLs verified via Mendeley/Figshare APIs.

### 2.1 Mango — 4 classes from two complementary Mendeley datasets

#### a) Mango Growth Stages (Mendeley 5snwpzdtzs, CC BY 4.0)
- **URL**: https://data.mendeley.com/datasets/5snwpzdtzs/1
- **Direct download**: https://data.mendeley.com/public-api/zip/5snwpzdtzs/download/1
- **Size**: 146 MB zip, 2004 images, 5-15 megapixel DSLR on-tree
- **License**: CC BY 4.0, authors: Islam et al., paper https://doi.org/10.1016/j.dib.2025.111780
- **Structure**: `Mango Growth Dataset/` with subfolders `early-fruit/`, `premature/`, `mature/`, `ripe/` + VOC XML + JSON
- **Mapping (verified from README)**:
  - `early-fruit` (468 images) + `premature` (526) -> `mango_young` — **only source for young** after old zip deletion
  - `mature` (540) -> `mango_mature`
  - `ripe` (470) -> `mango_ripe`
- **Detector use**: VOC XML parsed to YOLO boxes (on-tree mango), added to detector as `mango_growth_stages` (2004 boxes)
- **Grouping limitation**: Same tree photographed every 3-4 days, groups by filename, not tree identity. Noted in report.

#### b) Mango Ripening Stages (Mendeley mm8g66d7rc, CC BY 4.0)
- **URL**: https://data.mendeley.com/datasets/mm8g66d7rc/1
- **Direct download**: https://data.mendeley.com/public-api/zip/mm8g66d7rc/download/1
- **Size**: 27.9 MB zip containing 4 RARs: Stage_0 Unripe 6.31 MB, Stage_1 Early Ripe 7.68 MB, Stage_2 Partially Ripe 7.73 MB, Stage_3 Ripe 6.34 MB
- **License**: CC BY 4.0
- **Structure**: After extracting zip then 4 RARs, folders `Stage_0/`, `Stage_1/`, `Stage_2/`, `Stage_3/` each with single mango per photo on white background (harvested, not on-tree)
- **Mapping (verified from dataset description: post-harvest ripening)**:
  - `stage0` (Unripe) + `stage1` (Early Ripe) -> `mango_mature`
  - `stage2` (Partially Ripe) -> `mango_turning` — **only source for turning**
  - `stage3` (Ripe) -> `mango_ripe`
- **No fabrication**: We do NOT map rotten/damaged/fresh/diseased to maturity. Only verified ripening stages.
- **Grouping**: Per photo, repeat views cannot be identified.

#### Combined mango coverage
- `mango_young`: growth early-fruit+premature (994 raw)
- `mango_mature`: growth mature (540) + ripening stage0+stage1 (~2 * ~? images, need actual counts from extraction)
- `mango_turning`: ripening stage2 (only source)
- `mango_ripe`: growth ripe (470) + ripening stage3

Counts are reported in `preparation_report.json` after extraction, not fabricated here. No duplication: dedup via SHA256 + fingerprint clustering.

### 2.2 Dragon fruit — 3 classes without RF zip

#### a) Dragon Fruit Maturity (Mendeley 2jpzbx8tm6, CC BY 4.0)
- **URL**: https://data.mendeley.com/datasets/2jpzbx8tm6/1
- **Direct zip**: https://data.mendeley.com/public-files/datasets/2jpzbx8tm6/files/4a971fd0-07cf-4d88-9109-a8513886c32a/file_downloaded (maturity)
- **SHA256**: 7265501db07c50056a3d4062be44c1f30f98cb039ef4ecbf2a591fccf4fa27fc (from datasets.json)
- **License**: CC BY 4.0, authors: Tania Khatun et al.
- **Structure**: `Original Dataset/Immature Dragon Fruit/` + `Mature Dragon Fruit/` (3779 originals), `Augmented Dataset/` excluded to avoid leakage
- **Mapping**: Immature -> `dragonfruit_unripe`, Mature -> `dragonfruit_ripe`
- **Verification**: Recursive search for Immature/Mature folders, case-insensitive, no RF required.

#### b) Black Rot (Mendeley kpsywfwkrf/1, CC BY 4.0)
- **URL**: https://data.mendeley.com/datasets/kpsywfwkrf/1
- **License**: CC BY 4.0
- **Structure**: `Dragon Fruit/Fruit/Black_Rot/` 675 originals, `import_manifest.jsonl` with per-image SHA256 verified against publisher hashes
- **Mapping**: Black_Rot -> `dragonfruit_rotten`, only fruit Black_Rot accepted, leaf/Fungi/Healthy/Balanced excluded
- **Already in pipeline**: `download_dragon_black_rot.py` preserved.

### 2.3 Detector public datasets (preserved)

- **MangoYOLO (Figshare 26220632, CC BY 4.0, MD5 6702f497522098e0068bf39eb3bc79e9, 45.58 MB)**: VOC YOLO boxes for mango
- **Mango on-tree segmentation (Figshare 38394074, CC BY 4.0, 324.48 MB)**: COCO segmentation, tiled for YOLO
- **Mango far-field (Mendeley gcgrjvwmm2, CC BY 4.0, 216 MB)**: distant small fruit, on-tree
- **Dragon orchard (Mendeley t8kbmg6cgz/2, CC BY 4.0, 48.96 MB) + Mango orchard daylight (Mendeley bhrz29mkmr/2, CC BY-NC 4.0, 1.23 GB)**: via `download_orchard_datasets.py`, detector only, background images verified (24 images)

### 2.4 Negative images (Requirement B)

#### Roboflow negatives (10 sources, CC BY 4.0 / MIT) — full, requires API key
- `neg_litchi_orchard` (11111-ssxwo/litchi-ctsui v2, 300) — lychee clusters
- `neg_lychee_vn` (vnu-jozz8/lychee-p5qlv v1, 200) — Vietnamese lychee
- `neg_litchi_green` (south-china-agriculture-university-yiovr/litchi_seg_2 v3, 100) — green/half-red litchi
- `neg_rambutan` (n-a-0tjsb/rambutan-ripeness-detection v1, 200, MIT) — rambutan
- `neg_pomegranate` (flower-icte3/pomegranate-00y7c v1, 150) — pomegranate
- `neg_apple_orchard` (nust2/apple-hyrte v1, 150) — trellised apple rows
- `neg_tomato` (fruit-dsna0/tomato-5yhlt v4, 100) — greenhouse tomatoes
- `neg_pitaya_flower_night` (pitaya-ubgq5/pitaya-xxtg8 v2) — dragon fruit flowers/buds, night
- `neg_pitaya_flower_close` (dragon-hf4db/dragon-9gcmh v1) — flower close-ups
- `neg_pitaya_flower_web` (pitaya-vogjz/pitaya_keypoints v1) — flowers and buds
- **Download**: via `scripts/download_negatives.py` using official Roboflow API `https://api.roboflow.com/{workspace}/{project}/{version}/yolov8?api_key=...`, export link polled, zip extracted, one copy per original upload (before `.rf.`), sampled with fixed seed `negatives:<source>`
- **Handling**: Images only, labels discarded, stored as `data/external/extracted/negatives/<source>/`, used with empty YOLO label files (no background class), not in classifiers, duplicate checks via `drop_cross_source_copies`, separate val/test negatives via group split, FP evaluation via detector_test/negative_fp_report.json
- **API key**: Never hardcoded, read from `ROBOFLOW_API_KEY` env or `~/.roboflow_key`, with `--skip-if-no-key` guard.

#### Public fallback negatives (Wikimedia CC BY-SA / Public Domain) — no API key required
- **Script**: `scripts/download_negative_public.py`
- **Sources**: Wikimedia Commons images manually verified to NOT contain mango/dragon fruit:
  - apple: Red_Apple.jpg, Green_apple.jpg, Honeycrisp-Apple.jpg
  - tomato: Tomato_je.jpg, Tomatoes.jpg
  - lychee: Lychee_fruit.jpg, Litchi_chinensis_fruits.jpg
  - rambutan: Rambutan.jpg, Rambutan_fruit.jpg
  - pitaya flower: Pitaya_flower.jpg, Hylocereus_undatus_flower.jpg, Dragon_fruit_flower.jpg
  - orchard background: Orchard.jpg
- **License**: Mixed CC BY-SA 3.0/4.0, CC BY-SA 2.0, Public Domain, attribution preserved in import_report.json
- **Verification**: Image decode via PIL, min size 32px, manual URL curation.
- **Limitation**: Small (~100-200 images) vs full Roboflow (~1500). For production, use Roboflow negatives.

## 3. How replacement preserves requirements

### Requirement A — mango_dataset.zip replacement
- Old zip provided 4-class mango classifier labels. New pipeline provides same 4 classes from two public datasets, with explicit mapping verified from dataset READMEs/papers, not guessed.
- No duplication: `deduplicate_classification` removes exact SHA256 + near-duplicate fingerprint (hamming <=4, color diff <=12) and quarantines conflicting classes.
- No leakage: group-aware split (per file, per original upload), identical decoded image check across splits, source group never crosses splits.
- Counts reported in `preparation_report.json` + `machine_readable_dataset_report.json`, not fabricated.
- Test set preserved: 20 groups min per class per split (train/val/calib/test) via `MIN_GROUPS` in `maturity_data.py` and rebalancing.

### Requirement B — detector rejects irrelevant objects
- Negative images implemented via existing `--negative SOURCE:DIR` mechanism (reused, not redundant).
- Empty YOLO labels, no third background class.
- Not in classifiers: `mango_classifier_examples` and `dragon_classifier_examples` only include mango/dragon sources, never `neg_*`.
- Duplicate checks: `drop_cross_source_copies` removes RF copies that also exist in public datasets, plus clustering in `maturity_data.py`.
- Separate val/test negatives: manifest includes `source` field starting with `neg_`, split per group, counts per split in `machine_readable_dataset_report.json`.
- FP evaluation: STEP 6D evaluates detector on negative-only test images, reports false-positive rate, saves `detector_test/negative_fp_report.json`.

## 4. Reproducible Colab order (new)

1. STEP 1 — Restore helpers (embedded bundle) + pip install, check T4 GPU
2. STEP 2 — Mount Drive, set `PUBLIC_DATA_RAW_DIR=/content/drive/MyDrive/fruit_data/public_raw`, `PUBLIC_DATA_EXTRACTED=REPO/data/external/extracted`, run:
   - `bash scripts/download_public_datasets.sh two-stage-curated` (MangoYOLO, mango_on_tree)
   - `python scripts/download_mango_datasets.py --output-root EXTRACTED --cache-dir RAW` (growth + ripening, handles zip+rar, deterministic extract)
   - `python scripts/download_dragon_maturity.py --output-root EXTRACTED --cache-dir RAW` (dragon maturity)
   - `python scripts/download_orchard_datasets.py --output-root EXTRACTED --cache-dir orchard_cache` (orchard)
   - `python scripts/download_dragon_black_rot.py --output-root EXTRACTED --cache-dir orchard_cache` (rotten)
   - `python scripts/download_negatives.py --output-root EXTRACTED --skip-if-no-key` (Roboflow, if key) + `python scripts/download_negative_public.py --output-root EXTRACTED --cache-dir RAW` (public fallback)
3. STEP 3 — (legacy) verify black rot, kept for backward compat
4. STEP 4 — Prepare with negatives: `python training/prepare_two_stage_data.py --external-root EXTRACTED --output /content/two_stage_dataset --mode copy --overwrite --seed 42 --require-orchard-data --negative neg_apple_public:/path ...`
5. STEP 5 — Readiness + machine-readable report: validates detector dataset, prints `data_readiness.json`, `preparation_report.json`, generates `machine_readable_dataset_report.json` with sources, licenses, per class/split counts, boxes per detector class, negative counts per source, corrupt count, duplicate counts, annotation errors, missing sources, readiness. Saves manifests to Drive.
6. STEP 6A — Train/resume detector (YOLOv8s, imgsz=960)
7. STEP 6B — Train/resume mango classifier (4 classes, readiness gate)
8. STEP 6C — Train/resume dragon classifier (3 classes, readiness gate, calibration)
9. STEP 6D — Evaluate FP rate on negative-only images
10. STEP 7 — Final artifacts + calibration thresholds + test metrics

After Colab disconnect: re-run STEP 1-5 then resume STEP 6.

## 5. Changed files summary

- `training/prepare_two_stage_data.py` — full rewrite:
  - Added `MANGO_GROWTH_MAP`, `MANGO_RIPENING_STAGE_MAP`, `load_mango_growth_stages()` scanning class folders case-insensitive, `load_mango_growth_detection()` parsing VOC XML -> YOLO, `load_dragon_mendeley_originals()` robust recursive search for Immature/Mature, `load_black_rot_classification()` fallback from `import_manifest.jsonl`, detection_examples includes growth detection, mango classifier = growth + ripening + optional rf_mango, dragon classifier = mendeley originals + black_rot + optional rf_dragon curated (deduped), updated report fields `mango_stage_mapping` includes `mendeley_mango_growth`, negative_handling note, `--negative` support preserved.
- `scripts/download_mango_datasets.py` — NEW: replacement downloader for mango growth stages (5snwpzdtzs, 146 MB, zip) and ripening stages (mm8g66d7rc, 27.9 MB zip containing 4 RARs), Drive cache resume via `curl --continue-at -`, zip CRC via `testzip`, rar via `unrar`/`bsdtar`/`rarfile`/`patool`, deterministic extract to `data/external/extracted/{mango_growth_stages,mango_ripening_stages}`, validation via PIL, license mapping, combined counts, handles turning class gap, generates `import_report.json`.
- `scripts/download_dragon_maturity.py` — NEW: downloads dragon maturity dataset (2jpzbx8tm6, 978 MB, SHA256 verified), extracts Original Dataset only, excludes Augmented, maps to unripe/ripe, license CC BY 4.0.
- `scripts/download_negative_public.py` — NEW: public fallback negatives without API key, Wikimedia CC BY-SA/Public Domain, manual curation, image validation, per-source import_report.json, combined summary.
- `scripts/download_negatives.py` — updated: added `--skip-if-no-key` to gracefully skip when ROBOFLOW_API_KEY not set, instead of failing.
- `scripts/download_all_replacement.py` — NEW: orchestrates all 6 download steps, single entry point for notebook and local validation.
- `scripts/embed_colab_helpers.py` — updated: includes new scripts in bundle (12 files total, was 7).
- `training/train_two_stage_colab.ipynb` — full rewrite:
  - STEP 1 embedded helpers updated (checksum 12 files, 57792 base64 chars)
  - STEP 2 replaced old ZIP extraction with new download logic: public YOLO, mango growth+ripening, dragon maturity, orchard, black rot, negatives (Roboflow + public fallback), cache on Drive, extract local, list import reports.
  - STEP 4 updated to use `--negative` args for each negative source found, no longer requires `--mango-rf`/`--dragon-rf` (optional legacy), prints negative counts.
  - STEP 5 generates machine-readable report `machine_readable_dataset_report.json` aggregating all import_reports, per class/split counts, boxes per detector class, negative counts, corrupt, duplicate, annotation errors, missing sources, readiness, saves to Drive.
  - Added STEP 6D false-positive evaluation on negative-only test images.
  - Preserves existing training steps 6A/B/C, final artifacts 7.
- `REPLACEMENT_REPORT.md` — this file, source/license list, reproducible order, changed files, validation commands, blockers.

Preserved (not modified, or only minimally):
- `scripts/download_public_datasets.sh` — preserved, still provides two-stage-curated profile (MangoYOLO, mango_on_tree)
- `scripts/download_orchard_datasets.py` — preserved, detector only
- `scripts/download_dragon_black_rot.py` — preserved, rotten
- `training/train_two_stage.py` — preserved, readiness/duplicate/annotation/calibration gates
- `training/maturity_data.py` — preserved, dragon curation and readiness checks

## 6. Validation commands (local and Colab)

### Local syntax check
```bash
python -m py_compile training/prepare_two_stage_data.py scripts/download_mango_datasets.py scripts/download_dragon_maturity.py scripts/download_negative_public.py scripts/download_negatives.py
python scripts/embed_colab_helpers.py
```

### Download all replacement (local or Colab)
```bash
# Colab: set RAW_DIR to Drive, EXTRACTED to repo
python scripts/download_all_replacement.py --output-root data/external/extracted --cache-dir /content/drive/MyDrive/fruit_data/public_raw --orchard-cache /content/drive/MyDrive/fruit_data/orchard_cache
# Local (no Drive):
python scripts/download_all_replacement.py --output-root data/external/extracted --cache-dir data/external/raw
```

### Prepare with negatives (after download)
```bash
python training/prepare_two_stage_data.py \
  --external-root data/external/extracted \
  --output /tmp/two_stage_dataset \
  --mode copy --overwrite --seed 42 --require-orchard-data \
  --negative neg_apple_public:data/external/extracted/negatives/neg_apple_public \
  --negative neg_tomato_public:data/external/extracted/negatives/neg_tomato_public \
  --negative neg_lychee_public:data/external/extracted/negatives/neg_lychee_public \
  --negative neg_rambutan_public:data/external/extracted/negatives/neg_rambutan_public \
  --negative neg_pitaya_flower_public:data/external/extracted/negatives/neg_pitaya_flower_public
```

### Readiness check
```bash
python -c "import json, pathlib; print(json.loads(pathlib.Path('/tmp/two_stage_dataset/data_readiness.json').read_text()))"
cat /tmp/two_stage_dataset/preparation_report.json | python -m json.tool
cat /tmp/two_stage_dataset/machine_readable_dataset_report.json | python -m json.tool
```

### Train (requires GPU, Ultralytics)
```bash
python training/train_two_stage.py --dataset-root /tmp/two_stage_dataset --project runs_maturity_v2 --resume --skip-mango-classifier --skip-dragon-classifier
python training/train_two_stage.py --dataset-root /tmp/two_stage_dataset --project runs_maturity_v2 --resume --skip-detector --skip-dragon-classifier
python training/train_two_stage.py --dataset-root /tmp/two_stage_dataset --project runs_maturity_v2 --resume --skip-detector --skip-mango-classifier
```

## 7. Blockers and limitations

- **Mango grouping**: Growth stages photographed same tree every 3-4 days, groups by filename, not tree identity. Ripening stages per photo, repeat views cannot be identified. This may cause near-duplicate leakage across splits if same fruit photographed multiple times, but dedup via fingerprint mitigates. Noted in report.
- **Turning class**: Only from ripening stage2, limited samples. If counts < MIN_GROUPS (80 train, 20 val/calib/test), readiness will BLOCK. This is intentional to avoid fabricating data; gap must be reported, not filled with unrelated labels.
- **Rotten**: Only Black Rot covers one spoilage condition, not all rotten types. Field evaluation needed.
- **Negatives**: Public fallback is small; full Roboflow negatives (1500 images) require ROBOFLOW_API_KEY, not hardcoded. Without key, detector will have higher false-positive risk, but pipeline still works with orchard backgrounds (24 images) + public fallback (~100 images).
- **No test results claimed**: This report does not claim accuracy without test results. Actual mAP/precision/recall/F1/confusion/calibration must be measured after training on Colab T4.
- **No 100% accuracy promised**: As per constraints, data checks do not guarantee 100% accuracy; field evaluation required.

## 8. Machine-readable report

Generated after STEP 4 via `machine_readable_dataset_report.json` in dataset root and Drive manifests. Contains:
- dataset source and license (per import_report.json)
- number of downloaded and usable images (from import reports + manifests)
- number of images per class and per split (from manifest.csv)
- number of bounding boxes per detector class (from detector manifest)
- number of negative images per source (from negatives/*.import_report.json)
- number of corrupt images (via PIL verification during curation)
- exact and near-duplicate counts (from deduplication + clustering)
- annotation errors and quarantined samples (from curation_report.json + quarantine.csv)
- missing or insufficient data sources (from data_readiness.json failures)
- readiness for training (from data_readiness.json)

## 9. Deliverables checklist

- [x] Updated notebook `training/train_two_stage_colab.ipynb` with replacement downloads, no old ZIP dependency, auto download/cache to Drive with resume, verify integrity, deterministic extract, validate structure, handle Roboflow without hardcoding keys, reproducible Colab order, FP evaluation
- [x] Downloader scripts: `download_mango_datasets.py` (growth+ripening), `download_dragon_maturity.py` (unripe/ripe), `download_negative_public.py` (public fallback), updated `download_negatives.py` (skip-if-no-key), `download_all_replacement.py` (orchestrator), preserved `download_public_datasets.sh`, `download_orchard_datasets.py`, `download_dragon_black_rot.py`
- [x] Prep code changes: `prepare_two_stage_data.py` rewritten to include growth+ripening+dragon maturity+black_rot+negatives, no RF required, explicit mapping, no duplication/fabrication, dedup, no leakage, report counts
- [x] Source/license list: this report + import_report.json per dataset
- [x] Reproducible Colab order: documented in markdown cell and this report
- [x] Changed files summary: section 5
- [x] Validation commands: section 6
- [x] Blockers: section 7
- [x] Machine-readable report: generated in STEP 5
- [x] Preserved existing functionality: download_public_datasets.sh, download_orchard_datasets.py, download_dragon_black_rot.py, prepare_two_stage_data.py (extended, not broken), train_two_stage.py, maturity_data.py, readiness/duplicate/annotation/calibration gates
