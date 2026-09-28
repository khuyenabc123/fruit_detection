#!/usr/bin/env bash
# Show the latest Vertex training job's state, per-stage epoch progress, and log tail.
# Usage: scripts/gcp/training_status.sh [JOB_ID] [LOG_LINES]
set -euo pipefail

PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-${PROJECT}-fruit-training}"
RUN_PREFIX="${RUN_PREFIX:-runs_maturity_v2}"
JOB_ID="${1:-}"
LOG_LINES="${2:-15}"

if [ -z "${JOB_ID}" ]; then
  JOB_ID="$(gcloud ai custom-jobs list --project="${PROJECT}" --region="${REGION}" \
    --filter='displayName~^fruit-two-stage' --sort-by=~createTime --limit=1 \
    --format='value(name.basename())' 2>/dev/null)"
fi
[ -n "${JOB_ID}" ] || { echo "No fruit-two-stage job found in ${REGION}" >&2; exit 1; }

echo "== Job ${JOB_ID}"
gcloud ai custom-jobs describe "${JOB_ID}" --project="${PROJECT}" --region="${REGION}" \
  --format='value(displayName,state,createTime,startTime,endTime,error.message)' 2>/dev/null \
  | tr '\t' '\n' | paste -d' ' <(printf '%s\n' name: state: created: started: ended: error:) -

echo
echo "== Status markers (gs://${BUCKET}/${RUN_PREFIX}/job_status.log)"
gcloud storage cat "gs://${BUCKET}/${RUN_PREFIX}/job_status.log" 2>/dev/null | tail -5 || echo "(none yet)"

echo
echo "== Epoch progress"
for stage in detector mango_classifier dragon_classifier; do
  base="gs://${BUCKET}/${RUN_PREFIX}/${stage}"
  results="$(gcloud storage cat "${base}/results.csv" 2>/dev/null || true)"
  if [ -z "${results}" ]; then
    echo "${stage}: not started"
    continue
  fi
  total="$(gcloud storage cat "${base}/args.yaml" 2>/dev/null | awk '/^epochs:/ {print $2}')"
  done_flag=""
  gcloud storage objects describe "${base}/weights/best.pt" >/dev/null 2>&1 && done_flag=" (best.pt saved)"
  STAGE="${stage}" TOTAL="${total:-?}" FLAG="${done_flag}" python3 -c '
import csv, io, os, sys
rows = list(csv.reader(io.StringIO(sys.stdin.read())))
header = [h.strip() for h in rows[0]]
last = dict(zip(header, (v.strip() for v in rows[-1])))
keys = [k for k in header if k.startswith("metrics/") or k.endswith("loss")]
metrics = ", ".join(f"{k.split(chr(47))[-1]}={float(last[k]):.4f}" for k in keys if last.get(k))
print(f"{os.environ[\"STAGE\"]}: epoch {last[\"epoch\"]}/{os.environ[\"TOTAL\"]}{os.environ[\"FLAG\"]}")
print(f"    {metrics}")
' <<< "${results}"
done

echo
echo "== Last ${LOG_LINES} log lines"
gcloud logging read "resource.type=\"ml_job\" AND resource.labels.job_id=\"${JOB_ID}\"" \
  --project="${PROJECT}" --limit="${LOG_LINES}" --freshness=2d \
  --format='value(timestamp.date("%H:%M:%S"),textPayload)' 2>/dev/null | tac | cut -c1-220
