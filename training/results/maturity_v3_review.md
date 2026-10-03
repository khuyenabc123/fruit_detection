# GCP training result review: maturity_v3

Checked September 30, 2026. Job `4169118715503181824`, `JOB_STATE_SUCCEEDED`, Spot V100 (`n1-standard-8`), 3 h 54 min of training (September 29, 16:48-20:42 Vietnam time). Data: `data/prepared/two_stage_maturity_v3`. Outputs: `gs://project-1c166153-8e72-4d82-9e0-fruit-training/runs_maturity_v3/`. Local copy of weights and evaluation: `fruit_detection_runs_gcp_review/4169118715503181824/`.

## What changed from v2

- Mango stages are defined by appearance: `mango_young` (old premature + early), `mango_mature`, `mango_turning` (new), `mango_ripe`. Added Mendeley mm8g66d7rc ripening photos (951).
- Detector: +2,802 images (Mendeley gcgrjvwmm2 far-field 1,023; Roboflow mango-tree 690, pitaya orchard 992, ripe dragon plants 97; all CC BY 4.0). 13,240 images, 36,861 training boxes.

## Detector: v2 vs v3 on the same v3 test images

Up to 40 test images per source, conf 0.25, IoU 0.5, one-to-one matching.

| Source | Fruits | v2 recall | v3 recall | v3 precision |
|---|---:|---:|---:|---:|
| Roboflow mango tree (whole trees) | 587 | 6.3% | **86.0%** | 75.5% |
| Roboflow pitaya orchard | 226 | 25.2% | **91.6%** | 79.0% |
| Roboflow ripe dragon plants | 94 | 11.7% | **53.2%** | 58.8% |
| Mendeley mango far-field | 200 | 63.0% | **76.5%** | 80.5% |
| Mango orchard daylight | 73 | 95.9% | 98.6% | 90.0% |
| MangoYOLO | 315 | 97.5% | 97.5% | 88.7% |
| Mango on-tree | 202 | 96.5% | 96.0% | 90.2% |
| Dragon orchard | 62 | 100% | 100% | 87.3% |

Old sources keep their performance; whole-tree sources improve dramatically. Full v3 test set (2,037 images, 7,468 fruits): mAP50 94.9%, mAP50-95 68.3% (mango 94.2/66.4, dragon 95.6/70.1). Not comparable with v2's 98.5% because v2's test set lacked the whole-tree images.

## Classifiers (held-out test split)

| | v2 | v3 |
|---|---:|---:|
| Mango accuracy | 63.9% (4 age stages) | **90.2%** (4 visible stages) |
| Mango answers accepted (>= 0.8 and calibrated threshold) | 18/144 | **179/234**, 174 correct |
| Dragon accuracy | 100% | 100% (131/131, all accepted) |

Mango recall: young 64/74, mature 76/87, turning 24/24, ripe 47/49. Remaining errors are young vs mature (19 of 23). By source: Roboflow mango 115/138 (83%), Mendeley ripening 96/96. Mendeley ripening photos are single harvested fruit on a white table, grouped per photo (repeat views could not be identified), so 100% on that source is optimistic. Calibrated mango thresholds are now all below 1.0 (0.44-0.82), so stages are no longer forced to `mango_uncertain`.

## User photos (`~/Downloads`, full pipeline, conf 0.25, ripeness >= 0.8)

| Photo | v2 | v3 |
|---|---|---|
| Close-up dragon fruit | 3 ripe | 3 ripe |
| Whole dragon-fruit plant (~40 fruit) | 3 found | **22 found**: 21 ripe, 1 unripe |
| Whole mango tree | 8 found, all uncertain | **46 found**: 25 young, 21 uncertain (smallest/blurred fruit) |
| Mango cluster (231x148 px) | 11: 5 ripe, 6 uncertain | 11: **10 ripe**, 1 uncertain |

## Remaining limitations

- Dense dragon-fruit clusters: still about half missed on whole-plant web photos (53% recall on that source).
- Young vs mature green mango remains the main mango confusion.
- `mango_turning` examples come only from white-background harvested photos; on-tree turning fruit is untested.
- No independent photos from the target orchard have been labeled yet.
- The new weights are not yet installed in `backend/weights/`.
