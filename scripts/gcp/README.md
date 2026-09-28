# Training on GCP (Vertex AI)

Runs the same `training/train_two_stage.py` pipeline as the Colab notebook
(detector -> mango classifier -> dragon classifier + calibration) on a Vertex
AI custom job, so the laptop can be switched off while it trains.

```text
laptop: launch_vertex_training.sh
  -> gs://<project>-fruit-training/data/two_stage_maturity_v2.tar   (prepared data, uploaded once)
  -> gs://<project>-fruit-training/code/<timestamp>/                (frozen code snapshot)
  -> Vertex AI custom job: n1-standard-8 + 1 GPU, Spot, 24 h timeout
       vertex_entrypoint.sh: pip install ultralytics, untar data to local disk,
       train with --resume, write runs to /gcs/<bucket>/runs_maturity_v2/
```

The bucket is mounted in the job at `/gcs/<bucket>`, so every epoch's
`last.pt` and `results.csv` land in Cloud Storage immediately.

## Launch

```bash
scripts/gcp/launch_vertex_training.sh                   # V100 Spot, us-central1
GPU=NVIDIA_TESLA_T4 scripts/gcp/launch_vertex_training.sh   # if V100 capacity is unavailable
```

The prepared dataset (`data/prepared/two_stage_maturity_v2`, built by the
notebook steps 3-5 or `prepare_two_stage_data.py`) is uploaded only if missing;
use `FORCE_DATA=1` after rebuilding it.

Spot machines can be preempted. If a job ends as `FAILED`/`CANCELLED` before
finishing, run the launcher again: it resumes each stage from `last.pt` and
skips finished stages.

## Track progress

```bash
scripts/gcp/training_status.sh              # state, epoch N/total per stage, metrics, log tail
gcloud ai custom-jobs stream-logs <JOB_ID> --region=us-central1   # live log
```

Console: Vertex AI -> Training -> Custom jobs -> the job -> View logs.
Per-epoch plots/CSV: Cloud Storage -> `<bucket>/runs_maturity_v2/<stage>/`.

## Get the weights back

```bash
B=gs://$(gcloud config get-value project)-fruit-training/runs_maturity_v2
gcloud storage cp $B/detector/weights/best.pt           backend/weights/detector.pt
gcloud storage cp $B/mango_classifier/weights/best.pt   backend/weights/mango_classifier.pt
gcloud storage cp $B/mango_classifier/calibration.json  backend/weights/mango_calibration.json
gcloud storage cp $B/dragon_classifier/weights/best.pt  backend/weights/dragon_classifier.pt
gcloud storage cp $B/dragon_classifier/calibration.json backend/weights/dragon_calibration.json
```

## Cost

Billing is per second while the job runs, charged against the project's
billing account (Free Trial credit first). The 24 h `TIMEOUT` caps a single
job. Delete the bucket's `code/` and `data/` objects when done to stop storage
charges (a few cents per month).
