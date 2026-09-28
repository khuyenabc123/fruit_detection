#!/usr/bin/env bash
# Runs inside the Vertex AI custom-job container. Vertex mounts the bucket at
# /gcs/<bucket>, so checkpoints written under RUN_DIR survive a Spot preemption
# and a resubmitted job resumes from them (train_two_stage.py --resume).
set -euo pipefail

: "${BUCKET:?BUCKET must be set}"
: "${CODE_PREFIX:?CODE_PREFIX must be set}"
GCS_ROOT="/gcs/${BUCKET}"
CODE_DIR="${GCS_ROOT}/${CODE_PREFIX}"
RUN_DIR="${GCS_ROOT}/${RUN_PREFIX:-runs_maturity_v2}"
DATA_TAR="${GCS_ROOT}/${DATA_OBJECT:-data/two_stage_maturity_v2.tar}"
WORK=/workspace
DATASET="${WORK}/data/two_stage_maturity_v2"
WORKERS="${WORKERS:-6}"

mkdir -p "${RUN_DIR}"
status() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "${RUN_DIR}/job_status.log"
}
trap 'code=$?; if [ $code -eq 0 ]; then status "FINISHED"; else status "FAILED exit=$code"; fi' EXIT

status "STARTED host=$(hostname) job=${CLOUD_ML_JOB_ID:-unknown}"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true

status "SETUP installing ultralytics"
(apt-get update -qq && apt-get install -y -qq libgl1 libglib2.0-0) >/dev/null 2>&1 || true
pip install -q "ultralytics==8.4.155" "numpy>=1.24" "PyYAML>=6.0" "Pillow>=10.0" "scipy>=1.11"

status "SETUP copying dataset to local disk"
mkdir -p "${WORK}/data" "${WORK}/code"
tar -xf "${DATA_TAR}" -C "${WORK}/data"
# The prepared data.yaml stores the absolute path from the machine that built it.
sed -i "s#^path:.*#path: ${DATASET}/detector#" "${DATASET}/detector/data.yaml"
cp "${CODE_DIR}"/training/*.py "${WORK}/code/"

# Small /dev/shm makes PyTorch dataloader workers crash with "bus error".
shm_kb=$(df -k /dev/shm | awk 'NR==2 {print $2}')
if [ "${shm_kb:-0}" -lt 2000000 ]; then
  status "WARN /dev/shm is ${shm_kb} KB; using workers=0"
  WORKERS=0
fi

cd "${WORK}/code"
status "TRAINING run_dir=${RUN_DIR} workers=${WORKERS}"
python3 train_two_stage.py \
  --dataset-root "${DATASET}" \
  --project "${RUN_DIR}" \
  --workers "${WORKERS}" \
  --resume \
  ${EXTRA_TRAIN_ARGS:-}
