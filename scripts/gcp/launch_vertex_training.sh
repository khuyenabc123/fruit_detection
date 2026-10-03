#!/usr/bin/env bash
# Upload the prepared dataset + training code to Cloud Storage and submit a
# Vertex AI Spot GPU job that runs detector -> mango -> dragon training.
# Rerunning this after a preemption/failure resumes from the saved checkpoints.
#
# Usage: scripts/gcp/launch_vertex_training.sh
# Common overrides: GPU=NVIDIA_TESLA_T4 REGION=us-central1 CODE_ROOT=/path/to/repo
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_ROOT="${CODE_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-${PROJECT}-fruit-training}"
GPU="${GPU:-NVIDIA_TESLA_V100}"
MACHINE="${MACHINE:-n1-standard-8}"
DATASET="${DATASET:-${CODE_ROOT}/data/prepared/two_stage_maturity_v3}"
DATA_NAME="$(basename "${DATASET}")"
DATA_OBJECT="data/${DATA_NAME}.tar"
RUN_PREFIX="${RUN_PREFIX:-runs_maturity_v3}"
# Hard cap on billable time per job, so a stuck job cannot drain credits.
TIMEOUT="${TIMEOUT:-86400s}"
IMAGE="us-docker.pkg.dev/vertex-ai/training/pytorch-gpu.2-4.py310:latest"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CODE_PREFIX="code/${STAMP}"

[ -f "${DATASET}/data_readiness.json" ] || { echo "Missing prepared dataset: ${DATASET}" >&2; exit 1; }
[ -f "${CODE_ROOT}/training/maturity_data.py" ] || { echo "training/maturity_data.py missing under ${CODE_ROOT}" >&2; exit 1; }

if ! gcloud storage buckets describe "gs://${BUCKET}" --project="${PROJECT}" >/dev/null 2>&1; then
  echo "Creating bucket gs://${BUCKET} in ${REGION}"
  gcloud storage buckets create "gs://${BUCKET}" --project="${PROJECT}" \
    --location="${REGION}" --uniform-bucket-level-access
fi

if [ "${FORCE_DATA:-0}" = 1 ] || ! gcloud storage objects describe "gs://${BUCKET}/${DATA_OBJECT}" >/dev/null 2>&1; then
  echo "Uploading dataset $(du -sh "${DATASET}" | cut -f1) (streamed tar)"
  tar -cf - -C "$(dirname "${DATASET}")" "$(basename "${DATASET}")" \
    | gcloud storage cp - "gs://${BUCKET}/${DATA_OBJECT}"
else
  echo "Dataset already in gs://${BUCKET}/${DATA_OBJECT} (FORCE_DATA=1 to replace)"
fi

echo "Uploading code snapshot to gs://${BUCKET}/${CODE_PREFIX}"
gcloud storage cp "${CODE_ROOT}"/training/*.py "${CODE_ROOT}/training/requirements.txt" \
  "gs://${BUCKET}/${CODE_PREFIX}/training/"
gcloud storage cp "${SCRIPT_DIR}/vertex_entrypoint.sh" "gs://${BUCKET}/${CODE_PREFIX}/"

# Vertex rejects env vars with empty values, so add this one only when set.
EXTRA_ENV=""
if [ -n "${EXTRA_TRAIN_ARGS:-}" ]; then
  EXTRA_ENV="        - {name: EXTRA_TRAIN_ARGS, value: \"${EXTRA_TRAIN_ARGS}\"}
"
fi
CONFIG="$(mktemp --suffix=.yaml)"
trap 'rm -f "${CONFIG}"' EXIT
cat > "${CONFIG}" <<EOF
workerPoolSpecs:
  - machineSpec:
      machineType: ${MACHINE}
      acceleratorType: ${GPU}
      acceleratorCount: 1
    replicaCount: 1
    diskSpec:
      bootDiskType: pd-ssd
      bootDiskSizeGb: 100
    containerSpec:
      imageUri: ${IMAGE}
      command: ["bash", "/gcs/${BUCKET}/${CODE_PREFIX}/vertex_entrypoint.sh"]
      env:
        - {name: BUCKET, value: "${BUCKET}"}
        - {name: CODE_PREFIX, value: "${CODE_PREFIX}"}
        - {name: RUN_PREFIX, value: "${RUN_PREFIX}"}
        - {name: DATA_OBJECT, value: "${DATA_OBJECT}"}
        - {name: DATA_NAME, value: "${DATA_NAME}"}
${EXTRA_ENV}scheduling:
  strategy: SPOT
  timeout: ${TIMEOUT}
EOF

gcloud ai custom-jobs create --project="${PROJECT}" --region="${REGION}" \
  --display-name="fruit-two-stage-${STAMP}" --config="${CONFIG}"

echo
echo "Check progress:  scripts/gcp/training_status.sh"
echo "Live logs:       gcloud ai custom-jobs stream-logs <JOB_ID> --region=${REGION}"
echo "Console:         https://console.cloud.google.com/vertex-ai/training/custom-jobs?project=${PROJECT}"
