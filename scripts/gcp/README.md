# Training on GCP (Vertex AI)

This folder runs the same pipeline as the Colab notebook
(`training/train_two_stage.py`: detector -> mango classifier -> dragon
classifier + calibration) on Google Cloud, so training keeps going with the
laptop switched off.

## What service is used, and why

| Piece | Service | Why |
|---|---|---|
| GPU training | **Vertex AI custom training job** | Runs a container on a GPU machine, then shuts the machine down by itself when the script exits. No VM to create, SSH into, or forget to stop. |
| Machine | `n1-standard-8` (8 vCPU, 30 GB RAM) + 1 **NVIDIA V100** | The project's Compute Engine GPU quota is 0 (Free Trial default), so a plain GPU VM is impossible. Vertex AI has its own quota: 1 Spot T4, 1 Spot V100, 8 Spot A100 in `us-central1`. V100 is ~2-3x faster than T4 for YOLOv8 and usually easier to get than A100. |
| Pricing mode | **Spot** | Spot capacity is 60-90% cheaper. Google may reclaim the machine; checkpoints are saved every epoch, so a rerun continues where it stopped. |
| Storage | **Cloud Storage** bucket `<project>-fruit-training` in `us-central1` | Same region as the job (no transfer fees). Vertex mounts it at `/gcs/<bucket>`, so the job writes checkpoints there like a normal folder — the equivalent of Google Drive in Colab. |
| Container | Google's prebuilt `us-docker.pkg.dev/vertex-ai/training/pytorch-gpu.2-4.py310` | Already has CUDA + PyTorch. The job only `pip install`s ultralytics, so no Docker build or Artifact Registry is needed. |
| Logs | **Cloud Logging** | Everything the job prints (epoch bars, metrics, errors) is kept and viewable in the Console. |

Alternatives considered: Colab (disconnects, needs the laptop/browser for
long runs unless Pro+), a Compute Engine GPU VM (blocked by 0 GPU quota, and
must be stopped manually or it keeps billing).

## How it works

```text
your laptop                         Google Cloud (us-central1)
-----------                         --------------------------
launch_vertex_training.sh
  1. tar data/prepared/two_stage_maturity_v2  ->  gs://BUCKET/data/two_stage_maturity_v2.tar   (once, ~2 GB)
  2. copy training/*.py + entrypoint          ->  gs://BUCKET/code/<timestamp>/                 (frozen snapshot)
  3. gcloud ai custom-jobs create             ->  Vertex AI job (Spot V100, 24 h timeout)
                                                    vertex_entrypoint.sh:
                                                      pip install ultralytics==8.4.155
                                                      untar dataset to local SSD, fix data.yaml path
                                                      python train_two_stage.py --resume
                                                        -> gs://BUCKET/runs_maturity_v2/{detector,mango_classifier,dragon_classifier}/
                                                      job_status.log: STARTED / SETUP / TRAINING / FINISHED|FAILED
                                                    machine is released when the script exits
```

Files:

- `launch_vertex_training.sh` — creates the bucket if missing, uploads data
  (only if not already there) and a code snapshot, submits the job.
- `vertex_entrypoint.sh` — runs inside the cloud machine.
- `training_status.sh` — prints job state, per-stage epoch progress, metrics,
  and the latest log lines.

## Step by step

One-time setup (already done for `project-1c166153-8e72-4d82-9e0`):

```bash
gcloud auth login
gcloud config set project <PROJECT_ID>
gcloud services enable aiplatform.googleapis.com storage.googleapis.com logging.googleapis.com
```

Prepare the dataset locally (notebook steps 3-5, or
`training/prepare_two_stage_data.py`), so that
`data/prepared/two_stage_maturity_v2/data_readiness.json` exists.

Launch:

```bash
scripts/gcp/launch_vertex_training.sh                          # V100 Spot
GPU=NVIDIA_TESLA_T4 scripts/gcp/launch_vertex_training.sh      # if stuck in PENDING (no V100 capacity)
FORCE_DATA=1 scripts/gcp/launch_vertex_training.sh             # after rebuilding the dataset
EXTRA_TRAIN_ARGS="--detector-epochs 1 --classifier-epochs 1" RUN_PREFIX=smoke \
  scripts/gcp/launch_vertex_training.sh                        # quick smoke test in a separate folder
```

The upload goes at your internet upload speed (~3 MiB/s measured, ~11 min for
2 GB). After the job shows `RUNNING` the laptop can be turned off.

If the job ends `FAILED`/`CANCELLED` before all three stages finish (e.g. a
Spot preemption), run the launcher again with the same `RUN_PREFIX`: finished
stages are reused and the current stage resumes from `last.pt`. To start a
completely fresh run instead, use a new `RUN_PREFIX`.

## Tracking progress

```bash
scripts/gcp/training_status.sh                     # latest job
scripts/gcp/training_status.sh <JOB_ID> 30         # a given job, 30 log lines
gcloud ai custom-jobs stream-logs <JOB_ID> --region=us-central1   # live log
```

Example output:

```text
== Job 4689768257580695552
state: JOB_STATE_RUNNING
== Epoch progress
detector: epoch 2/100 (best.pt available)
    precision(B)=0.8594, recall(B)=0.7757, mAP50(B)=0.8636, mAP50-95(B)=0.5258, ...
mango_classifier: not started
dragon_classifier: not started
```

Job states: `PENDING` (waiting for a Spot GPU) -> `RUNNING` -> `SUCCEEDED`, or
`FAILED` / `CANCELLED`.

Without the terminal (e.g. from a phone):

- Console -> **Vertex AI -> Training -> Custom jobs** -> the job -> **View logs**.
- Console -> **Cloud Storage -> Buckets -> `<project>-fruit-training` ->
  `runs_maturity_v2/<stage>/`**: `results.csv`, `results.png`, confusion
  matrices, `weights/`.

Stop a job early: `gcloud ai custom-jobs cancel <JOB_ID> --region=us-central1`.

## Getting the trained weights

```bash
B=gs://$(gcloud config get-value project)-fruit-training/runs_maturity_v2
gcloud storage cp $B/detector/weights/best.pt           backend/weights/detector.pt
gcloud storage cp $B/mango_classifier/weights/best.pt   backend/weights/mango_classifier.pt
gcloud storage cp $B/mango_classifier/calibration.json  backend/weights/mango_calibration.json
gcloud storage cp $B/dragon_classifier/weights/best.pt  backend/weights/dragon_classifier.pt
gcloud storage cp $B/dragon_classifier/calibration.json backend/weights/dragon_calibration.json
```

## Cost

Vertex AI bills per second from when the machine starts until the script
exits (`PENDING` time is free). Approximate `us-central1` list prices:

| Item | On-demand | Spot (used here) |
|---|---|---|
| n1-standard-8 | ~$0.44/h | ~$0.10-0.20/h |
| V100 GPU | ~$2.48/h | ~$0.75-1.00/h |
| T4 GPU | ~$0.35/h | ~$0.10-0.15/h |
| Storage (~3-5 GB) | ~$0.02/GB/month | — |

Spot prices change; check the
[Vertex AI pricing page](https://cloud.google.com/vertex-ai/pricing) for
current numbers. Measured speed on V100: ~2 min per detector epoch, so the full
run (up to 100 detector epochs + two 50-epoch classifiers) is about 4-5 h,
roughly **$5-10 on Spot**. The 24 h `TIMEOUT` caps one job at worst about
$30 Spot / $70 on-demand.

Charges go to the project's billing account; Free Trial credit is used first.
See the real amount under **Billing -> Reports**, filtered by service
"Vertex AI". Other resources in the project (e.g. the `langfuse-server` VM)
spend the same credit.

When finished, remove what you no longer need:

```bash
gcloud storage rm -r gs://<bucket>/code gs://<bucket>/data     # keep runs_maturity_v2 (weights)
```
