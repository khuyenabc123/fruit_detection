#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
raw_dir="${PUBLIC_DATA_RAW_DIR:-${project_dir}/data/external/raw}"
extracted_dir="${PUBLIC_DATA_EXTRACTED_DIR:-${project_dir}/data/external/extracted}"
profile="${1:-all}"

if [[ "${profile}" != "all" && "${profile}" != "two-stage-minimal" ]]; then
  echo "Usage: $0 [all|two-stage-minimal]" >&2
  exit 2
fi

mkdir -p "${raw_dir}" "${extracted_dir}"

download_and_verify() {
  local name="$1"
  local url="$2"
  local archive="$3"
  local algorithm="$4"
  local expected="$5"
  local output="${raw_dir}/${archive}"

  if [[ -f "${output}" ]]; then
    local existing
    if [[ "${algorithm}" == "md5" ]]; then
      existing="$(md5sum "${output}" | awk '{print $1}')"
    else
      existing="$(sha256sum "${output}" | awk '{print $1}')"
    fi
    if [[ "${existing}" == "${expected}" ]]; then
      echo "[skip] ${archive} is already downloaded and verified"
      return
    fi
  fi

  echo "[download] ${name}"
  curl --location --fail --retry 4 --retry-delay 3 --continue-at - \
    --output "${output}" "${url}"

  local actual
  if [[ "${algorithm}" == "md5" ]]; then
    actual="$(md5sum "${output}" | awk '{print $1}')"
  else
    actual="$(sha256sum "${output}" | awk '{print $1}')"
  fi

  if [[ "${actual}" != "${expected}" ]]; then
    echo "Checksum mismatch for ${archive}" >&2
    echo "Expected: ${expected}" >&2
    echo "Actual:   ${actual}" >&2
    return 1
  fi
  echo "[verified] ${archive} (${algorithm})"
}

extract_once() {
  local archive="$1"
  local destination="$2"
  local marker="${extracted_dir}/${destination}/.extracted-ok"

  if [[ -f "${marker}" ]]; then
    echo "[skip] ${destination} was already extracted"
    return
  fi

  mkdir -p "${extracted_dir}/${destination}"
  echo "[extract] ${archive} -> ${destination}"
  unzip -q "${raw_dir}/${archive}" -d "${extracted_dir}/${destination}"
  touch "${marker}"
}

download_and_verify \
  "MangoYOLO" \
  "https://ndownloader.figshare.com/files/26220632" \
  "mango_yolo.zip" \
  "md5" \
  "6702f497522098e0068bf39eb3bc79e9"

download_and_verify \
  "On-tree mango instance segmentation" \
  "https://ndownloader.figshare.com/files/38394074" \
  "mango_on_tree_segmentation.zip" \
  "md5" \
  "96ea1cfd4fe95c26cdb6430cc89beded"

if [[ "${profile}" == "all" ]]; then
  download_and_verify \
    "On-tree mango-branch instance segmentation" \
    "https://ndownloader.figshare.com/files/47511947" \
    "mango_branch_segmentation.zip" \
    "md5" \
    "e6a98fed9109f17f887ec33f497aff95"
fi

download_and_verify \
  "Mango deep-yield" \
  "https://ndownloader.figshare.com/files/26469419" \
  "mango_deep_yield.zip" \
  "md5" \
  "56a47595422ebba6f3d0c8dfe126e677"

download_and_verify \
  "Dragon fruit maturity classification" \
  "https://data.mendeley.com/public-files/datasets/2jpzbx8tm6/files/4a971fd0-07cf-4d88-9109-a8513886c32a/file_downloaded" \
  "dragon_fruit_maturity.zip" \
  "sha256" \
  "7265501db07c50056a3d4062be44c1f30f98cb039ef4ecbf2a591fccf4fa27fc"

if [[ "${profile}" == "all" ]]; then
  download_and_verify \
    "Dragon fruit quality classification" \
    "https://data.mendeley.com/public-files/datasets/2jpzbx8tm6/files/b48bea93-6b57-482b-a6e9-fc35548fc2dd/file_downloaded" \
    "dragon_fruit_quality.zip" \
    "sha256" \
    "d1a938590a8fa30bdb589f6774a5cfb84382952748ba2f4084439bfd0d5b5766"
fi

extract_once "mango_yolo.zip" "mango_yolo"
extract_once "mango_on_tree_segmentation.zip" "mango_on_tree_segmentation"
if [[ "${profile}" == "all" ]]; then
  extract_once "mango_branch_segmentation.zip" "mango_branch_segmentation"
fi
extract_once "mango_deep_yield.zip" "mango_deep_yield"
extract_once "dragon_fruit_maturity.zip" "dragon_fruit_maturity"
if [[ "${profile}" == "all" ]]; then
  extract_once "dragon_fruit_quality.zip" "dragon_fruit_quality"
fi

echo "All public datasets were downloaded, verified, and extracted."
