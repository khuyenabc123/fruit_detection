#!/usr/bin/env python3
"""Import the original fruit Black_Rot class from DF-MOD v1 for Colab.

Dataset: https://data.mendeley.com/datasets/kpsywfwkrf/1 (CC BY 4.0).
Only the 675 original Black_Rot images qualify; healthy, fungal, stem, and
augmented categories are not remapped to ripeness. No detector boxes are made.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps

try:
    from .download_orchard_datasets import archive_index, download_members
except ImportError:
    from download_orchard_datasets import archive_index, download_members

DATASET = "kpsywfwkrf/1"
SOURCE = "https://data.mendeley.com/datasets/" + DATASET
NAME = "dragon_fruit_black_rot"
EXPECTED_IMAGES = 675


def black_rot_member(name):
    parts = [re.sub(r"[^a-z0-9]", "", part.lower()) for part in Path(name).parts]
    return (Path(name).suffix.lower() in {".jpg", ".jpeg", ".png"}
            and "blackrot" in parts
            and not any("augment" in part or "balanced" in part or part in {"stem", "leaf", "leaves"} for part in parts))


def choose_archive(files, requested=None):
    files = [row for row in files if row.get("filename", row.get("name", "")).lower().endswith(".zip")]
    if requested:
        files = [row for row in files if row.get("filename", row.get("name")) == requested]
    else:
        files = [row for row in files if not re.search(r"augment|balanced", row.get("filename", row.get("name", "")), re.I)]
        originals = [row for row in files if re.search(r"original|raw", row.get("filename", row.get("name", "")), re.I)]
        files = originals or files
    if len(files) != 1:
        names = [row.get("filename", row.get("name")) for row in files]
        raise ValueError(f"Cannot uniquely identify the original ZIP: {names}. Use --archive-file-name or --archive for an already downloaded original ZIP.")
    return files[0]


def api_json(endpoint):
    url = "https://data.mendeley.com/public-api/datasets/kpsywfwkrf/" + endpoint
    result = subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--max-time", "60",
                             "--retry", "3", "-H", "Accept: application/vnd.mendeley-public-dataset.1+json", url],
                            check=True, stdout=subprocess.PIPE)
    payload = json.loads(result.stdout)
    if not isinstance(payload, list):
        raise ValueError(f"Unexpected publisher metadata for {endpoint}: {payload}")
    return payload


def folder_files(folder_id):
    rows, start = [], 0
    while True:
        batch = api_json(f"files?folder_id={folder_id}&version=1&$start={start}&$limit=1000")
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        start += 1000


def original_black_rot_folder(folders):
    by_id = {row["id"]: row for row in folders}
    candidates = []
    for row in folders:
        parts, current, seen = [], row, set()
        while current:
            if current["id"] in seen:
                raise ValueError("Cycle in publisher folder metadata")
            seen.add(current["id"])
            parts.insert(0, current["name"])
            parent = current.get("parent_id")
            if parent and parent not in by_id:
                raise ValueError("Incomplete publisher folder metadata")
            current = by_id.get(parent)
        path = "/".join(parts)
        if (re.sub(r"[^a-z0-9]", "", row["name"].lower()) == "blackrot"
                and any(part.lower() == "fruit" for part in parts)
                and black_rot_member(path + "/check.jpg")):
            candidates.append((row["id"], path))
    if len(candidates) != 1:
        raise ValueError(f"Expected one original Fruit/Black_Rot folder, found {candidates}")
    return candidates[0]


def discover_source(requested=None):
    files = folder_files("root")
    # DF-MOD v1 publishes individual images inside folders, with a separate
    # Balanced tree. Select by the complete path, never the class name alone.
    if not requested and not any(row.get("filename", "").lower().endswith(".zip") for row in files):
        folder_id, path = original_black_rot_folder(api_json("folders/1"))
        selected = []
        for row in folder_files(folder_id):
            name = path + "/" + row["filename"]
            if not black_rot_member(name):
                continue
            details = row["content_details"]
            if (row.get("status") != "COMPLETED" or not details.get("size")
                    or not details.get("download_url")
                    or not re.fullmatch(r"[0-9a-f]{64}", details.get("sha256_hash", ""))):
                raise ValueError(f"Incomplete publisher image metadata: {name}")
            selected.append({"name": name, "url": details["download_url"], "size": details["size"],
                             "publisher_sha256": details["sha256_hash"], "publisher_file_id": row["id"]})
        return {"transport": "individual_files", "folder_id": folder_id, "folder_path": path,
                "source_page": SOURCE, "files": selected}
    row = choose_archive(files, requested)
    details = row.get("content_details", {})
    size = details.get("size", row.get("size"))
    download_url = details.get("download_url")
    if not size or not download_url:
        raise ValueError("Publisher file metadata lacks size/download_url. Supply the original ZIP with --archive.")
    return {"url": download_url, "archive_bytes": int(size), "publisher_archive_sha256": details.get("sha256_hash"),
            "archive_name": row.get("filename", row.get("name")), "source_page": SOURCE}


def download_file(row):
    result = subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--max-time", "60",
                             "--retry", "3", row["url"]], check=True, stdout=subprocess.PIPE)
    raw = result.stdout
    if len(raw) != row["size"] or hashlib.sha256(raw).hexdigest() != row["publisher_sha256"]:
        raise ValueError(f"Publisher size/SHA256 mismatch: {row['name']}")
    return row, raw


def valid_import(root):
    try:
        report = json.loads((root / "import_report.json").read_text())
        rows = [json.loads(line) for line in (root / "import_manifest.jsonl").read_text().splitlines()]
        return (report["source_dataset"] == DATASET and len(rows) == report["selected_images"] == EXPECTED_IMAGES
                and len({r["source_image"] for r in rows}) == len(rows)
                and all(r["source_class"] == "Black_Rot" and hashlib.sha256((root / r["image"]).read_bytes()).hexdigest() == r["sha256"] for r in rows))
    except (OSError, KeyError, ValueError):
        return False


def import_images(output_root, workers=4, archive_path=None, requested=None):
    output = output_root / NAME
    (output / "images").mkdir(parents=True, exist_ok=True)
    report_path = output / "import_report.json"
    report_path.unlink(missing_ok=True)
    manifest = output / "import_manifest.jsonl"
    records = {}
    if manifest.is_file():
        for line in manifest.read_text().splitlines():
            row = json.loads(line)
            image = output / row["image"]
            if image.is_file() and hashlib.sha256(image.read_bytes()).hexdigest() == row["sha256"]:
                records[row["source_image"]] = row
    if archive_path:
        source = {"local_archive": str(archive_path), "source_page": SOURCE}
        with zipfile.ZipFile(archive_path) as archive:
            names = [info.filename for info in archive.infolist() if black_rot_member(info.filename)]
        rows = [{"name": name} for name in names]
    else:
        source = discover_source(requested)
        rows = source.pop("files") if source.get("transport") == "individual_files" else [
            row for row in archive_index(source) if black_rot_member(row["name"])]
    if len(rows) != EXPECTED_IMAGES or len({row["name"] for row in rows}) != EXPECTED_IMAGES:
        raise ValueError(f"Expected {EXPECTED_IMAGES} original fruit Black_Rot images, found {len(rows)}. No completion report written; inspect the archive layout and augmentation folders.")
    pending = [row for row in rows if row["name"] not in records or (
        row.get("publisher_sha256") and records[row["name"]].get("source_sha256") != row["publisher_sha256"])]

    def members():
        if archive_path:
            with zipfile.ZipFile(archive_path) as archive:
                for row in pending:
                    yield row, archive.read(row["name"])  # ZipFile verifies CRC.
        elif source.get("transport") == "individual_files":
            with ThreadPoolExecutor(max_workers=workers) as pool:
                yield from pool.map(download_file, pending)
        else:
            yield from download_members(source, pending, workers)

    print(f"Black_Rot: {len(rows)} originals, {len(pending)} to import", flush=True)
    with manifest.open("a") as stream:
        for index, (row, raw) in enumerate(members(), 1):
            name = row["name"]
            image_id = hashlib.sha256(name.encode()).hexdigest()[:24]
            image_path = output / "images" / (image_id + ".jpg")
            with Image.open(io.BytesIO(raw)) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                original_size = im.size
                im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                im.save(image_path, quality=95)
            record = {"image": "images/" + image_path.name, "source_image": name, "source_class": "Black_Rot",
                      "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(), "source_sha256": hashlib.sha256(raw).hexdigest(),
                      "source_dimensions": original_size, "dimensions": im.size, "group": "dfmod:" + Path(name).stem}
            if row.get("publisher_sha256"):
                record.update(publisher_sha256=row["publisher_sha256"], publisher_file_id=row["publisher_file_id"])
            records[name] = record
            stream.write(json.dumps(record) + "\n"); stream.flush()
            if index % 100 == 0 or index == len(pending):
                print(f"Black_Rot: {index}/{len(pending)} imported", flush=True)
    ordered = [records[row["name"]] for row in sorted(rows, key=lambda row: row["name"])]
    manifest.write_text("".join(json.dumps(row) + "\n" for row in ordered))
    report = {"source_dataset": DATASET, "source": source, "selected_images": len(ordered), "license": "CC BY 4.0",
              "unique_output_images": len({row["sha256"] for row in ordered}),
              "exact_duplicate_files": len(ordered) - len({row["sha256"] for row in ordered}),
              "source_dimensions": dict(Counter("x".join(map(str, row["source_dimensions"])) for row in ordered)),
              "authors": "MD. Fahiz Siddikur Pranto; Anamika Dhar; Rokonozzaman Ayon",
              "mapping": "Fruit/Black_Rot -> dragonfruit_rotten (visible spoilage). No other disease/healthy categories used.",
              "verification": ("Each original image checked against publisher size and SHA256, decoded, and output SHA256 recorded."
                               if source.get("transport") == "individual_files" else
                               "Selected ZIP member CRC and image decoding; source and output SHA256 recorded. Whole-archive SHA256 not checked."),
              "limitations": "One rot disease; image-level source labels; field accuracy and exhaustive visual review not established."}
    report_path.write_text(json.dumps(report, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("data/external/extracted"))
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--archive", type=Path, help="Already downloaded original DF-MOD ZIP")
    parser.add_argument("--archive-file-name", help="Select a publisher ZIP if metadata lists multiple candidates")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    root = args.output_root / NAME
    cache = args.cache_dir / (NAME + "_v1.zip") if args.cache_dir else None
    complete = valid_import(root)
    if not complete and cache and cache.is_file():
        with zipfile.ZipFile(cache) as archive:
            for member in archive.infolist():
                if not (args.output_root / member.filename).resolve().is_relative_to(root.resolve()):
                    raise ValueError("Unsafe black-rot cache path")
            archive.extractall(args.output_root)
        complete = valid_import(root)
    if not complete:
        import_images(args.output_root, args.workers, args.archive, args.archive_file_name)
    if cache and not cache.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        temporary = shutil.make_archive(str(cache.with_suffix(".partial")), "zip", args.output_root, NAME)
        Path(temporary).replace(cache)
    records = [json.loads(line) for line in (root / "import_manifest.jsonl").read_text().splitlines()]
    unique = len({row["sha256"] for row in records})
    print(f"Verified Black_Rot import: {root}; {len(records)} files, {unique} unique images. Preparation removes duplicates.")


if __name__ == "__main__":
    main()
