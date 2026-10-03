#!/usr/bin/env python3
"""Download labeled orchard subsets, validate them, and normalize detection boxes.

HTTP ranges avoid storing multi-GB source archives. Every downloaded ZIP member
is checked against its CRC before decoding. Original source hashes, coordinates,
and selection decisions are retained in the output for review.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import shutil
import struct
import subprocess
import tempfile
import time
import zipfile
import zlib
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from PIL import Image


SOURCES = {
    "dragon_fruit_orchard": {
        "page": "https://data.mendeley.com/datasets/t8kbmg6cgz/2",
        "url": "https://data.mendeley.com/public-files/datasets/t8kbmg6cgz/files/a6dde2a4-a170-488c-8bda-35bafb0f84ac/file_downloaded",
        "archive_bytes": 1193555548,
        "archive_sha256": "97caeb0104f780dd6c342035b91114b9f72ae2a846978e26e5cdd10317ab8423",
        "license": "CC BY 4.0",
        "species_id": 1,
        "format": "pose",
        "selection": "Original HD1080 orchard frames with matching nonempty pose labels; exclude augmentations and Mendeley maturity copies.",
    },
    "mango_orchard_daylight": {
        "page": "https://data.mendeley.com/datasets/bhrz29mkmr/2",
        "url": "https://data.mendeley.com/public-files/datasets/bhrz29mkmr/files/e42f9450-9138-4d27-85e0-4a5cdc35d2b7/file_downloaded",
        "archive_bytes": 4135934275,
        "archive_sha256": "a6db857c7eab03d52692060e8e52e401bb6d2740eb100d634a21f7e363540447",
        "license": "CC BY-NC 3.0 on version-2 landing page; archive README states CC BY-NC 4.0. Research/noncommercial use only.",
        "species_id": 0,
        "format": "box",
        "selection": "Exclude controlled-background/augmented Alternaria images; retain other source categories and explicitly labeled Background images.",
    },
}


def range_get(url: str, start: int, end: int) -> bytes:
    for attempt in range(4):
        try:
            with tempfile.TemporaryDirectory(prefix="orchard-range-") as temporary:
                headers = Path(temporary) / "headers"
                result = subprocess.run(
                    ["curl", "--fail", "--location", "--silent", "--show-error",
                     "--max-time", "120", "--range", f"{start}-{end}",
                     "--dump-header", str(headers), url],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                ranges = re.findall(r"(?im)^content-range:\s*([^\r\n]+)", headers.read_text())
                if not ranges or not ranges[-1].startswith(f"bytes {start}-{end}/"):
                    raise RuntimeError(f"Server did not honor byte range: {ranges}")
                data = result.stdout
            if len(data) != end - start + 1:
                raise RuntimeError("Incomplete archive range")
            return data
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def archive_index(source: dict) -> list[dict]:
    size = source["archive_bytes"]
    tail = range_get(source["url"], size - 65536, size - 1)
    position = tail.rfind(b"PK\x05\x06")
    if position < 0:
        raise ValueError("ZIP end record not found")
    _, disk, cd_disk, _, _, cd_size, cd_start, _ = struct.unpack_from("<4s4H2LH", tail, position)
    if disk or cd_disk or cd_start == 0xFFFFFFFF:
        raise ValueError("Unexpected multipart/ZIP64 source")
    directory = range_get(source["url"], cd_start, size - 1)
    with zipfile.ZipFile(io.BytesIO(directory)) as archive:
        rows = [
            {"name": info.filename, "offset": info.header_offset + cd_start,
             "compressed": info.compress_size, "size": info.file_size,
             "crc": info.CRC, "method": info.compress_type}
            for info in archive.infolist() if not info.is_dir()
        ]
    rows.sort(key=lambda item: item["offset"])
    for index, row in enumerate(rows):
        row["end"] = (rows[index + 1]["offset"] if index + 1 < len(rows) else cd_start) - 1
    return rows


def download_members(source: dict, rows: list[dict], workers: int):
    """Yield verified members, merging nearby ranges to reduce HTTP requests."""
    batches = []
    for row in sorted(rows, key=lambda item: item["offset"]):
        if (batches and row["offset"] - batches[-1][-1]["end"] < 65536
                and row["end"] - batches[-1][0]["offset"] < 8 * 1024 * 1024):
            batches[-1].append(row)
        else:
            batches.append([row])

    def fetch(batch):
        start = batch[0]["offset"]
        data = range_get(source["url"], start, batch[-1]["end"])
        result = []
        for row in batch:
            offset = row["offset"] - start
            if data[offset:offset + 4] != b"PK\x03\x04":
                raise ValueError(f"Invalid local ZIP header: {row['name']}")
            name_len, extra_len = struct.unpack_from("<HH", data, offset + 26)
            payload_start = offset + 30 + name_len + extra_len
            compressed = data[payload_start:payload_start + row["compressed"]]
            if row["method"] == zipfile.ZIP_DEFLATED:
                raw = zlib.decompress(compressed, -15)
            elif row["method"] == zipfile.ZIP_STORED:
                raw = compressed
            else:
                raise ValueError(f"Unsupported ZIP compression: {row['method']}")
            if len(raw) != row["size"] or zlib.crc32(raw) & 0xFFFFFFFF != row["crc"]:
                raise ValueError(f"ZIP member checksum failed: {row['name']}")
            result.append((row, raw))
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        remaining = iter(batches)
        pending = {pool.submit(fetch, batch) for batch in [next(remaining, None) for _ in range(workers)] if batch}
        while pending:
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                pending.remove(future)
                yield from future.result()
                batch = next(remaining, None)
                if batch:
                    pending.add(pool.submit(fetch, batch))


def parse_boxes(text: str, source: dict) -> list[list[float]]:
    boxes = []
    for line in text.splitlines():
        values = list(map(float, line.split()))
        if not values:
            continue
        expected = 17 if source["format"] == "pose" else 5
        if len(values) != expected or not all(math.isfinite(value) for value in values):
            raise ValueError(f"Expected {expected} finite YOLO values, got {len(values)}")
        if values[0] != int(values[0]) or int(values[0]) not in ({0, 1} if expected == 17 else {0, 1, 2, 3}):
            raise ValueError("Unexpected source class")
        x, y, width, height = values[1:5]
        left, top, right, bottom = x - width / 2, y - height / 2, x + width / 2, y + height / 2
        if width <= 0 or height <= 0 or min(left, top) < -1e-5 or max(right, bottom) > 1.00001:
            raise ValueError("Invalid normalized bounding box")
        left, top, right, bottom = max(0, left), max(0, top), min(1, right), min(1, bottom)
        boxes.append([source["species_id"], (left + right) / 2, (top + bottom) / 2, right - left, bottom - top])
    return boxes


def box_text(boxes) -> str:
    return "".join(f"{int(box[0])} " + " ".join(f"{value:.8f}" for value in box[1:]) + "\n" for box in boxes)


def record_valid(output: Path, record: dict) -> bool:
    image, label = output / record["image"], output / record["label"]
    return (image.is_file() and label.is_file()
            and hashlib.sha256(image.read_bytes()).hexdigest() == record["sha256"]
            and label.read_text() == box_text(record["boxes"]))


def completed_import(output: Path, name: str, max_edge: int) -> bool:
    try:
        report = json.loads((output / "import_report.json").read_text())
        records = [json.loads(line) for line in (output / "import_manifest.jsonl").read_text().splitlines()]
        return (report["source"] == SOURCES[name] and report["max_image_edge"] == max_edge
                and len(records) == report["selected_images"] > 0
                and len({row["source_image"] for row in records}) == len(records)
                and sum(len(row["boxes"]) for row in records) == report["boxes"]
                and all(record_valid(output, row) for row in records))
    except (OSError, ValueError, KeyError):
        return False


def import_source(name: str, output_root: Path, workers: int, max_edge: int) -> None:
    source = SOURCES[name]
    output = output_root / name
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "import_manifest.jsonl"
    records = {}
    if manifest_path.is_file():
        for line in manifest_path.read_text().splitlines():
            record = json.loads(line)
            if (record_valid(output, record)
                    and max(record["dimensions"]) == min(max(record["source_dimensions"]), max_edge)):
                records[record["source_image"]] = record
    # A report marks a completed import. Remove it before any repair/download.
    (output / "import_report.json").unlink(missing_ok=True)
    rows = archive_index(source)
    by_name = {row["name"]: row for row in rows}
    images = [row for row in rows if row["name"].lower().endswith(".jpg")]
    selected = []
    excluded = Counter()
    for row in images:
        stem = Path(row["name"]).stem
        if source["format"] == "pose" and not stem.startswith("HD1080_"):
            excluded["augmentation_or_existing_maturity_source"] += 1
            continue
        if source["format"] == "box" and stem.startswith("Alternaria"):
            excluded["controlled_background_or_augmentation"] += 1
            continue
        label = row["name"].replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
        if label not in by_name:
            excluded["missing_label_file"] += 1
            continue
        row["label"] = label
        selected.append(row)
    print(f"{name}: {len(selected)} candidate images; downloading labels", flush=True)
    label_text = {
        row["name"]: raw.decode("utf-8-sig")
        for row, raw in download_members(source, [by_name[row["label"]] for row in selected], workers)
    }
    valid = []
    errors = []
    for row in selected:
        try:
            row["boxes"] = parse_boxes(label_text[row["label"]], source)
            if not row["boxes"] and not Path(row["name"]).name.startswith("Background"):
                excluded["empty_unverified_label"] += 1
                continue
            valid.append(row)
        except ValueError as exc:
            excluded["invalid_labels"] += 1
            errors.append({"image": row["name"], "error": str(exc)})

    for folder in ("images", "labels", "source_labels"):
        (output / folder).mkdir(exist_ok=True)
    pending = [row for row in valid if row["name"] not in records]
    print(f"{name}: {len(valid)} valid images, {len(pending)} left to download", flush=True)
    with manifest_path.open("a", encoding="utf-8") as manifest:
        for index, (row, raw) in enumerate(download_members(source, pending, workers), 1):
            image_id = hashlib.sha256(row["name"].encode()).hexdigest()[:20]
            destination = output / "images" / f"{image_id}.jpg"
            with Image.open(io.BytesIO(raw)) as original:
                dimensions = original.size
                image = original.convert("RGB")
                image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                image.save(destination, quality=95)
            (output / "labels" / f"{image_id}.txt").write_text(box_text(row["boxes"]))
            (output / "source_labels" / f"{image_id}.txt").write_text(label_text[row["label"]])
            stem = Path(row["name"]).stem
            group = stem.rsplit("-", 1)[0] if source["format"] == "pose" else stem
            record = {
                "image": f"images/{image_id}.jpg", "label": f"labels/{image_id}.txt",
                "source_image": row["name"], "source_sha256": hashlib.sha256(raw).hexdigest(),
                "source_dimensions": dimensions, "dimensions": image.size,
                "group": f"{name}:{group}", "boxes": row["boxes"],
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            }
            records[row["name"]] = record
            manifest.write(json.dumps(record) + "\n")
            manifest.flush()
            if index % 100 == 0 or index == len(pending):
                print(f"{name}: downloaded {index}/{len(pending)}", flush=True)
    records = {row["name"]: records[row["name"]] for row in valid}
    # Rewrite in stable order after a successful import; interrupted runs resume.
    manifest_path.write_text("".join(json.dumps(records[key]) + "\n" for key in sorted(records)))
    report = {
        "source": source, "archive_images": len(images), "selected_images": len(records),
        "boxes": sum(len(record["boxes"]) for record in records.values()),
        "groups": len({record["group"] for record in records.values()}),
        "excluded": dict(excluded), "label_errors": errors,
        "max_image_edge": max_edge, "verification": "HTTP ranges checked; every selected member size and ZIP CRC verified; source and normalized image SHA256 recorded. Whole-archive SHA256 is publisher metadata only.",
    }
    (output / "import_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"dataset": name, "images": len(records), "boxes": report["boxes"], "excluded": dict(excluded)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    parser.add_argument("--output-root", type=Path, default=Path("data/external/extracted"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-edge", type=int, default=1600)
    parser.add_argument("--cache-dir", type=Path, help="Store/reuse compact imported ZIPs, e.g. on Google Drive")
    args = parser.parse_args()
    if args.workers < 1 or args.max_edge < 32:
        parser.error("workers must be positive and max-edge must be at least 32")
    for name in SOURCES if args.source == "all" else [args.source]:
        output = args.output_root / name
        cache = args.cache_dir / f"{name}_v1_{args.max_edge}.zip" if args.cache_dir else None
        complete = completed_import(output, name, args.max_edge)
        if not complete and cache and cache.is_file():
            print(f"{name}: restoring {cache}", flush=True)
            with zipfile.ZipFile(cache) as archive:
                root = output.resolve()
                for member in archive.infolist():
                    destination = (args.output_root / member.filename).resolve()
                    if not destination.is_relative_to(root):
                        raise ValueError(f"Unexpected cache member: {member.filename}")
                archive.extractall(args.output_root)
            complete = completed_import(output, name, args.max_edge)
        if complete:
            print(f"{name}: verified existing import", flush=True)
        else:
            import_source(name, args.output_root, args.workers, args.max_edge)
        if cache and not cache.is_file():
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_suffix(".partial")
            archive = shutil.make_archive(str(temporary), "zip", args.output_root, name)
            Path(archive).replace(cache)
            print(f"{name}: saved cache {cache}", flush=True)


if __name__ == "__main__":
    main()
