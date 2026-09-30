# Fruit detection: project history

How the mango and dragon-fruit ripeness system evolved from the first 4-class
detector to the current two-stage pipeline trained on Google Cloud. Each round
records what we tried, what went wrong, why, what we changed, and the result.

All times are Vietnam time (UTC+7), September 2026.

## Summary of training rounds

| Round | Date | Model | Where | Main result | Main problem found |
|---|---|---|---|---|---|
| 0 | Sep 12 | YOLOv8s, 4 classes (mango/dragon x unripe/ripe) | Colab T4, 30 epochs | mAP50 91.3% (test, 714 images) | Metrics inflated by split leakage; yellow harvested mangoes called "unripe" |
| 1 | Sep 18 | YOLOv8s, 7 classes (4 mango stages, 3 dragon stages) | Colab, 80 epochs | val mAP50 85.4%, mAP50-95 75.2% | Checkpoint overwritten by an accidental CPU run; whole-tree photos fail |
| 2 | Sep 24-25 | Two-stage: detector + mango/dragon classifiers + calibration | Colab T4 | Not recorded (logs lost) | Dragon Roboflow labels were polygons read as boxes; noisy labels; Colab disconnects |
| 3 (v2) | Sep 28 | Two-stage, curated data `maturity_v2` | GCP Vertex AI, Spot V100, 3 h 9 min | Detector test mAP50 98.5%; mango 63.9%; dragon 100% | Mango stages defined by age look identical; wide shots miss most fruit |
| 4 (v3) | Sep 29 | Two-stage, `maturity_v3`: visible mango stages + whole-tree data | GCP Vertex AI, Spot V100, 3 h 54 min | Mango 90.2%; whole-tree mango recall 6% -> 86% | Dense dragon clusters ~53% found; other red fruit mistaken for dragon fruit |

## Phase 1: first detector (Sep 12-20)

### Round 0: 4-class detector (Sep 12)

- Initial project: FastAPI backend, React + Ant Design frontend, YOLOv8s weights
  `backend/weights/best.pt`.
- 4 classes: `mango_unripe`, `mango_ripe`, `dragonfruit_unripe`,
  `dragonfruit_ripe`. The Roboflow mango stages premature/early/mature were
  merged into "unripe"; dragon "rotten" was dropped.
- Trained on Colab T4, 30 epochs. Reported test results (714 images): precision
  95.6%, recall 85.1%, mAP50 91.3%, mAP50-95 77.7%.
- Problems noted at the time: yellow post-harvest mangoes were labelled
  "unripe" (domain shift); annotated output images turned cyan (BGR/RGB mix-up).
- Later finding (Sep 18): these metrics were measured before grouping Roboflow
  copies of the same photo into one split, so they were too optimistic.

### Round 1: 7-class detector on Colab (Sep 18-20)

- New Colab notebook with 7 classes: `mango_premature`, `mango_early`,
  `mango_mature`, `mango_ripe`, `dragonfruit_unripe`, `dragonfruit_ripe`,
  `dragonfruit_rotten`. YOLOv8s, 80 epochs, 640 px, batch 16, AdamW.
- Problem: free Colab often dropped the runtime and wiped checkpoints.
  Fix: write checkpoints straight to Google Drive and add a resume cell; also
  stopped step 6B from deleting the run folder.
- Problem: a later accidental run on **CPU**, using the same run name with
  `exist_ok=True`, overwrote the finished 80-epoch weights with a 1-epoch model
  (mAP50 0.027).
  Fix: recovered the 80-epoch `best.pt` from Drive's version history and rebuilt
  its training curve from inside the checkpoint.
  Result: 80 epochs (~1 h 39 min on GPU), validation precision 82.6%, recall
  81.3%, **mAP50 85.4%, mAP50-95 75.2%**. `mango_premature` was confused with
  `mango_mature`. No held-out test evaluation was run.
- Lessons: assert a GPU, use a new run name per run, `exist_ok=False`,
  `save_period`.
- Also found: the data split was not sorted before shuffling, so a new Colab
  session could produce a different test set (documented, fixed later).
- Integration: the API and UI were changed to read class names from the weight
  file, because the repo still held the old 4-class weights.

### Deployment attempts (Sep 20-24)

- Modal (free tier): deploy failed first with `Token missing`, then with
  `Workspace ... has exceeded its spend limit` (Modal's limit is $0 until a card
  is added). Temporary workaround: backend on the laptop behind a Cloudflare
  quick tunnel (works only while the laptop is on).
- Sep 24: deployed the 7-class model to **Google Cloud Run** (asia-southeast1,
  CPU, scale to zero). Fixed two issues: Cloud Build's service account could not
  read the source (granted the Cloud Run Builder role), and an organisation
  policy blocked public access (`--no-invoker-iam-check`). `/health` and
  `/detect` worked (about 7.6 s per image).

## Phase 2: redesign to a two-stage pipeline (Sep 24-25)

### Problem: "results are very bad" on real whole-tree photos (Sep 24)

Detections of the 7-class model on 4 real photos:

| Photo | conf 0.25 | conf 0.80 | conf 0.90 |
|---|---:|---:|---:|
| Dragon-fruit close-up | 3 | 2 | 1 |
| Whole dragon-fruit plant | 0 | 0 | 0 |
| Mango tree (dozens of fruit) | 7 | 0 | 0 |
| Ripe mango | 2 (labelled mature) | 0 | 0 |

Causes found:

1. Training images were close-ups at 640 px; fruit on a whole tree is 10-25 px
   (domain shift).
2. YOLO confidence is not calibrated: its best F1 was at about 0.42, so asking
   for 80-90% confidence removed almost every detection.
3. One detector had to find fruit *and* tell 7 ripeness stages apart;
   per-stage accuracy was only ~56% (premature), ~67% (mature), ~84% (ripe).

### Fix: two-stage design

```text
whole image -> detector (mango / dragonfruit)
            -> crop each fruit
            -> species-specific ripeness classifier (mango 4 stages, dragon 3)
            -> temperature calibration + per-class threshold
            -> ripeness label, or *_uncertain when not confident enough
```

- Detector confidence threshold stays low (0.25) so small fruit is not lost;
  ripeness must reach a calibrated 80% or it is reported as "uncertain".
- Added public, openly licensed data for the detector only: MangoYOLO (1,730
  images, 15,281 boxes), CQUniversity on-tree mango segmentation (542 images),
  plus Mendeley dragon-fruit maturity and quality sets.
- Data rules: remove exact duplicates (630 of 2,127 dragon "originals" were
  byte-identical), never use offline augmentations for validation/test, never
  map "fresh/defect" to ripe/rotten.
- Commits `f2c43ab` (pipeline) and `622b15e` (Colab caching).

### Round 2: two-stage training on Colab (Sep 25-27)

- Detector (6A) and mango classifier (6B) finished; the dragon classifier (6C)
  failed.
- Problem: resuming a finished run failed because Ultralytics marks finished
  checkpoints with `epoch=-1`. Fix: detect finished runs and reuse `best.pt`
  (`237fd8f`).
- Problems: Colab runtime disconnected again; a new runtime could not find the
  Roboflow zips on Drive.
- Sep 27: the team tested the models on on-tree photos: "terrible". No metrics
  from these Colab runs survive (the session logs for Sep 25-27 were deleted).

## Phase 3: fixing the data (Sep 28)

Decision: stop retraining and fix the data first ("we have trained a lot but
still can not recognize").

Problems found and fixed:

- **Polygons read as boxes.** The dragon-fruit Roboflow export (`.yolov8`)
  contained segmentation polygons, which the pipeline had read as boxes, so
  detector boxes and classifier crops were wrong. Fix: convert each polygon to
  its enclosing box. All earlier detector and dragon checkpoints became invalid.
- **Noisy dragon labels.** Audit found 145 conflicts between box labels and the
  source's own maturity label, and 703 boxes smaller than 1% of the image.
  Visual checks showed green stems labelled `Unripe` and tiny fragments labelled
  `Rotten`. Fix: keep only isolated, dominant fruit crops; quarantine
  conflicts; drop crops under 64 px.
- **Too little on-tree data.** Added DF pose v2 (2,448 orchard frames, 4,637
  dragon boxes, 7 recordings) and MangoFruitBD v2 (1,070 daylight images). Frames
  from one recording stay in one split.
- **Too few rotten dragon fruit.** Added DF-MOD `Black_Rot`: 675 files but only
  270 unique images (405 exact copies removed); 3 repeated-view pairs grouped.
- Readiness gate: each class needs at least 80 source groups in train and 20 in
  each of val/calib/test, or training refuses to start.

Result (`maturity_v2`): detector 10,438 images; mango classifier 2,534 crops;
dragon classifier 1,416 crops. 22 tests passed.

## Phase 4: moving training to Google Cloud (Sep 28)

- Problem: Colab needed 7-14 h on a T4 and could not finish unattended.
- The project had **0** Compute Engine GPU quota (Free Trial default), so a GPU
  VM was impossible. Vertex AI had its own Spot quota (T4, V100, A100).
- Constraint: spend only the Free Trial credit (about ₫5.78M, expires Dec 10).
- Built `scripts/gcp/`: upload the prepared dataset once to Cloud Storage, submit
  a **Vertex AI custom job** on a Spot V100 with a 24 h cap; checkpoints are
  written every epoch to the bucket, so a preempted job resumes. A status script
  shows epoch progress and logs (`scripts/gcp/README.md`).
- Small fixes on the way: Vertex rejects empty environment variables
  (`027ef31`); status parser quoting (`a495b66`).

### Round 3 (v2) results: job `4689768257580695552`

3 h 9 min on one Spot V100 (Sep 28, 20:00-23:09).

| Model | Test result |
|---|---|
| Detector | mAP50 98.5%, mAP50-95 80.9% (mango 97.8%, dragon 99.3%) |
| Dragon ripeness | 100% (131/131) |
| Mango ripeness | **63.9%** (92/144): premature 42.6%, early 69.7%, mature 66.7%, ripe 92% |

Verification on real photos and orchard samples (Sep 29):

- **Threshold bug:** thresholds were rounded to 6 decimals, so 0.9999997868
  became 1.0 and rejected correct dragon crops. Fixed (full precision, tie
  handling, tests). Dragon acceptance 128/131 -> 131/131.
- **Mango almost always "uncertain":** no threshold for premature/mature reached
  80% precision, so they were set to 1.0; only 18 of 144 test mangoes got a label.
- **Wide shots:** whole dragon-fruit plant 3 of ~40 fruits found; whole mango
  tree 8 found. An image-size/threshold sweep (640-1600 px) did not help: a data
  problem, not a setting.
- **Why mango failed:** the mango source (Mendeley "Mango Growth Stages") defines
  premature/early/mature by **days after fruit set**, not appearance. The
  misclassified crops are green mangoes that look identical. Merging stages at
  output showed the model already knew unripe vs ripe: 97.9% accuracy.

## Phase 5: visible stages and whole-tree data (Sep 29)

Changes (`maturity_v3`, commits `f4ccdd2` to `67cf444`):

- **Mango stages redefined by what a photo shows** (still 4 classes):
  `mango_young` (old premature + early), `mango_mature`, `mango_turning` (new),
  `mango_ripe`. Added Mendeley mm8g66d7rc ripening photos (951; Stage 0+1 ->
  mature green, Stage 2 -> turning, Stage 3 -> ripe, since Stage 1 looked the
  same as Stage 0).
- **Whole-tree detector data:** Mendeley gcgrjvwmm2 far-field mango (1,023),
  Roboflow mango-tree (690 whole trees, ~13 fruits each), pitaya orchard (992),
  ripe dragon plants (97). All CC BY 4.0. Augmented Roboflow copies are reduced
  to one per original.
- Grouping: consecutive far-field photos grouped in blocks of 10; ripening photos
  one per group (repeat views of the same fruit could not be identified).
- Backend and frontend learned the new class names.

Result: detector 13,240 images (+27%), 36,861 training boxes (+60%).

### Round 4 (v3) results: job `4169118715503181824`

3 h 54 min on one Spot V100 (Sep 29, 16:48-20:42).

| | v2 | v3 |
|---|---:|---:|
| Mango ripeness accuracy | 63.9% | **90.2%** |
| Mango answers given with confidence | 18/144 | **179/234** (174 correct) |
| Dragon ripeness accuracy | 100% | 100% |

Detector recall on the same test images (v2 -> v3): whole mango trees 6% ->
**86%**, pitaya orchard rows 25% -> **92%**, whole dragon plants 12% -> **53%**,
far-field mango 63% -> **77%**; older sources unchanged or better.

User photos: whole dragon plant 3 -> 22 fruits found; whole mango tree 8 -> 46
found; mango cluster 5 -> 10 labelled ripe.

Details: `training/results/maturity_v3_review.md`.

### Internet photo check (Sep 30)

37 photos from Wikimedia Commons ("thanh long", "xoài", "dragon fruit plant",
"mango tree"), checked by eye:

- Works: mango found in 10 of 11 photos with visible mangoes (31 on one crowded
  tree); ripe yellow mangoes correct; dragon fruit on the plant found and
  labelled correctly; almost no false alarms on leaves, flowers or buildings.
- New problems: lychee called dragon fruit (the model only knows two fruits);
  one dragon-fruit flower called unripe fruit; red/purple mango varieties get
  "uncertain"; green mango close-ups often "uncertain".

## Lessons learned

1. **Check the data before training again.** Three rounds failed for data
   reasons: polygon labels read as boxes, labels defined by fruit age, and no
   whole-tree images. More epochs would not have fixed any of them.
2. **Test on the photos you will actually use.** High test scores (91%, 98.5%)
   hid failures on whole-tree photos because the test set looked like the
   training set.
3. **Raw model confidence is not a probability.** Calibration plus an
   "uncertain" answer gives honest output; a fixed 80-90% cut on raw YOLO scores
   removed nearly all detections.
4. **Labels must be visible in the image.** Stages defined by days after fruit
   set cannot be learned from a photo.
5. **Protect long training runs.** Unique run names, checkpoints outside the
   machine, resume logic, and a managed cloud job instead of a notebook.

## Current status (Sep 30)

- Working: detection of both fruits, dragon ripeness, 4 visible mango stages,
  "uncertain" when unsure, cloud training pipeline.
- Main weakness: dense dragon-fruit clusters on whole plants (~53% found).
- Also open: other red fruit mistaken for dragon fruit; red mango varieties;
  young vs mature green mango; no labelled test photos from the target orchard;
  v3 weights not yet installed in `backend/weights/`.
- Planned next retrain: more whole-plant dragon data (`thanh-long-detection`,
  more pitaya sets), 1280 px detector, negative photos (lychee, rambutan, tomato,
  dragon flowers), red mango varieties.

## Sources

Git history; Codex CLI session logs (Sep 20, Sep 24, Sep 29-30); Claude Code
session (Sep 28-30); prepared-data and audit reports under `data/`; review
files `fruit_detection_runs_gcp_review/*/REVIEW.md`. The Codex logs for Sep 25
and Sep 27-28 were deleted; those parts were rebuilt from saved prompts, file
times, reports and screenshots, and their Colab metrics are unknown.
