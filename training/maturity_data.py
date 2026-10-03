"""Conservative dragon-fruit label curation and pre-training readiness checks.

Source labels remain evidence, not proof of universal accuracy. Geometry rules
quarantine ambiguous multi-object examples; they never invent a ripeness label.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

REVISION = "maturity_v3"
CLASSES = ["dragonfruit_unripe", "dragonfruit_ripe", "dragonfruit_rotten"]
SOURCE_LABELS = {"Immature": "dragonfruit_unripe", "Mature": "dragonfruit_ripe"}
# Trial floors, not statistically established guarantees of dataset sufficiency.
MIN_GROUPS = {"train": 80, "val": 20, "calib": 20, "test": 20}
# DF-MOD v1 repeated views confirmed visually on 2026-09-28 after geometric
# feature matching. Original publisher SHA256s make this independent of local
# JPEG encoders and duplicate filenames. These are known matches, not a claim
# that all physical fruit identities have been recovered.
BLACK_ROT_VIEW_PAIRS = [
    # Black_Rot_385 / Black_Rot_409 (and their exact-copy aliases)
    ("3b42cf551c98fe661168b3cb0991fae5f1a942db568b36401f1837d028af292a",
     "9095b4d0eb817d06e6f761a23cd09d6e7dddb7280a456a5775ed7d9db62722f4"),
    # Black_Rot_593 / Black_Rot_662
    ("85226a13e7fdec71d032134241c1e34dbac4accc6ac0a2f9f5db7925f5ab0143",
     "553873d6aafe91135ce0e4d2ef51ec90c9d5b50dad7e44edbeec9e40b6805d81"),
    # Black_Rot_664 / Black_Rot_454
    ("6d991bc2aa59957a95d2bce14e322c02f1b55dc0274ffbfc084b9430080234bc",
     "bcfaf1ad0a6640d4a04bcd3feebfd241b3fa39aaa7a898ab420c237ff639c47e"),
]
BLACK_ROT_REVIEW_GROUPS = {checksum: "dfmod_review:" + min(pair)
                          for pair in BLACK_ROT_VIEW_PAIRS for checksum in pair}


def rebalance_classification_groups(group_examples, assignments):
    """Move whole groups to fill evaluation floors when the supply permits it."""
    labels = {group: {row.class_name for row in members} for group, members in group_examples.items()}
    classes = sorted({name for names in labels.values() for name in names})
    counts = Counter((assignments[group], name) for group, names in labels.items() for name in names)
    while True:
        deficits = [(MIN_GROUPS[split] - counts[split, name], split, name)
                    for split in MIN_GROUPS for name in classes if counts[split, name] < MIN_GROUPS[split]]
        moved = False
        for _, target, name in sorted(deficits, reverse=True):
            candidates = [group for group in sorted(labels) if name in labels[group] and assignments[group] != target
                          and all(counts[assignments[group], label] > MIN_GROUPS[assignments[group]] for label in labels[group])]
            if not candidates:
                continue
            group = max(candidates, key=lambda group: (
                sum(counts[target, label] < MIN_GROUPS[target] for label in labels[group]),
                min(counts[assignments[group], label] - MIN_GROUPS[assignments[group]] for label in labels[group]),
            ))
            donor = assignments[group]
            assignments[group] = target
            for label in labels[group]:
                counts[donor, label] -= 1; counts[target, label] += 1
            moved = True
            break
        if not moved:
            return assignments


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounds(box):
    _, x, y, w, h = box
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2


def contained_fraction(inner, outer):
    a, b, c, d = bounds(inner)
    e, f, g, h = bounds(outer)
    return max(0, min(c, g) - max(a, e)) * max(0, min(d, h) - max(b, f)) / (inner[3] * inner[4])


def dominant_fruit(boxes, size):
    """Retain one substantial, isolated fruit; nested parts are not extra fruit."""
    if not boxes:
        return None, "missing_boxes"
    index = max(range(len(boxes)), key=lambda i: boxes[i][3] * boxes[i][4])
    box = boxes[index]
    left, top, right, bottom = bounds(box)
    if min(left, top) < -1e-5 or max(right, bottom) > 1.00001:
        return None, "out_of_bounds"
    if (box[3] * box[4] < 0.10 or min(box[3] * size[0], box[4] * size[1]) < 64
            or not 0.25 <= box[3] * size[0] / (box[4] * size[1]) <= 4):
        return None, "small_or_narrow_subject"
    if any(i != index and contained_fraction(other, box) < 0.90 for i, other in enumerate(boxes)):
        return None, "disjoint_annotations_need_review"
    return index, "isolated_dominant_subject"


def crop_bounds(box, size, padding):
    _, x, y, w, h = box
    width, height = size
    return (max(0, round(width * (x - w / 2 - padding * w))),
            max(0, round(height * (y - h / 2 - padding * h))),
            min(width, round(width * (x + w / 2 + padding * w))),
            min(height, round(height * (y + h / 2 + padding * h))))


def fingerprint(image):
    """Mirror-invariant difference hash plus color thumbnail; heuristic grouping."""
    variants = []
    for im in (image, ImageOps.mirror(image)):
        pixels = list(im.convert("L").resize((9, 8), Image.Resampling.LANCZOS).getdata())
        bits = 0
        for y in range(8):
            for x in range(8):
                bits = (bits << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
        color = im.resize((8, 8), Image.Resampling.LANCZOS).convert("RGB").tobytes()
        variants.append((bits, color))
    return min(variants)


def cluster_records(records):
    """Union known originals, exact images, and conservative visual near-copies."""
    parent = list(range(len(records)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        a, b = find(a), find(b)
        parent[max(a, b)] = min(a, b)

    known = {}
    near_pairs = 0
    for i, record in enumerate(records):
        for key in ("hash:" + record["sha256"], "original:" + record["original_group"]):
            if key in known:
                union(i, known[key])
            else:
                known[key] = i
        a, colors = record["fingerprint"]
        for j in range(i):
            b, other_colors = records[j]["fingerprint"]
            if (a ^ b).bit_count() <= 4 and sum(abs(x - y) for x, y in zip(colors, other_colors)) / 192 <= 12:
                union(i, j)
                near_pairs += 1
    components = defaultdict(list)
    for i, record in enumerate(records):
        components[find(i)].append(record)
    conflicts = 0
    for members in components.values():
        group = "dragon_cluster:" + min(row["candidate_id"] for row in members)
        mixed = len({row["class_name"] for row in members}) > 1
        for row in members:
            row["group"] = group
            if mixed:
                row["status"], row["reason"] = "quarantine", "similar_images_have_conflicting_classes"
                conflicts += 1
    return {"near_copy_pairs_grouped": near_pairs, "conflicting_candidates_quarantined": conflicts}


def load_black_rot(root):
    if not root.is_dir():
        return [], "Black-rot import is missing. Run the notebook download cell."
    report_path, manifest_path = root / "import_report.json", root / "import_manifest.jsonl"
    if not report_path.is_file() or not manifest_path.is_file():
        raise ValueError(f"Incomplete black-rot import: {root}")
    report = json.loads(report_path.read_text())
    rows = [json.loads(line) for line in manifest_path.read_text().splitlines()]
    if report.get("source_dataset") != "kpsywfwkrf/1" or report.get("selected_images") != len(rows) or not rows:
        raise ValueError("Black-rot import report mismatch")
    records = []
    for row in rows:
        path = root / row["image"]
        if row["source_class"] != "Black_Rot" or digest(path) != row["sha256"]:
            raise ValueError(f"Changed or mislabeled black-rot import: {path}")
        records.append({"candidate_id": row["sha256"][:24], "image": str(path),
                        "sha256": row["sha256"], "crop_xyxy": None, "crop_index": 0,
                        "source_sha256": row.get("source_sha256"),
                        "class_name": "dragonfruit_rotten", "source": "dragon_black_rot_original",
                        "original_group": BLACK_ROT_REVIEW_GROUPS.get(row.get("source_sha256"),
                            row.get("group", "black_rot:" + row["source_image"])),
                        "status": "accepted", "reason": "publisher_fruit_black_rot_label"})
    return records, None


def contact_sheet(records, destination, title):
    selected = random.Random(42).sample(records, min(24, len(records)))
    sheet = Image.new("RGB", (1200, 40 + 220 * max(1, (len(selected) + 5) // 6)), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 10), title, fill="black")
    for i, row in enumerate(selected):
        with Image.open(row["image"]) as im:
            im = im.convert("RGB")
            if row["crop_xyxy"]:
                im = im.crop(row["crop_xyxy"])
            im.thumbnail((196, 170))
            x, y = (i % 6) * 200, 40 + (i // 6) * 220
            sheet.paste(im, (x, y))
            draw.text((x, y + 171), row["candidate_id"][:12], fill="black")
            draw.text((x, y + 188), row["reason"][:27], fill="black")
    sheet.save(destination, quality=90)


def curate_dragon(pairs, names, label_reader, black_rot_root, output, padding=0.10):
    output.mkdir(parents=True, exist_ok=True)
    candidates, detector = [], {}
    inventory, box_flags = defaultdict(Counter), Counter()
    invalid_files = []
    for image_path, label_path in pairs:
        origin = image_path.name.split("_", 1)[0]
        try:
            with Image.open(image_path) as original:
                original.load()
                size = original.size
            boxes = label_reader(label_path)
        except (OSError, ValueError) as exc:
            invalid_files.append({"image": str(image_path), "error": str(exc)})
            continue
        for box in boxes:
            source_class = names.get(box[0], "unknown").lower()
            inventory[origin][source_class] += 1
            if box[3] * box[4] < 0.01:
                box_flags["boxes_below_one_percent_area"] += 1
            expected = SOURCE_LABELS.get(origin)
            if expected and "dragonfruit_" + source_class != expected:
                box_flags["maturity_source_label_conflicts"] += 1
        index, reason = dominant_fruit(boxes, size)
        checksum = digest(image_path)
        row = {"candidate_id": hashlib.sha256((checksum + ":dominant").encode()).hexdigest()[:24],
               "image": str(image_path), "sha256": checksum,
               "label_sha256": digest(label_path) if label_path.is_file() else None,
               "source": "rf_dragonfruit_curated", "origin": origin,
               "original_group": image_path.stem.split(".rf.")[0],
               "crop_xyxy": None, "crop_index": index if index is not None else -1,
               "class_name": "", "status": "quarantine", "reason": reason}
        if index is not None:
            box = boxes[index]
            row["crop_xyxy"] = crop_bounds(box, size, padding)
            expected = SOURCE_LABELS.get(origin)
            observed = "dragonfruit_" + names.get(box[0], "unknown").lower()
            # Species detection can use an isolated whole-fruit box irrespective
            # of maturity. Never retain extra stem/tip/fragment annotations.
            detector[str(image_path)] = [box]
            if expected is None:
                row["reason"] = "quality_label_is_not_a_verified_maturity_label"
            elif observed != expected:
                row["reason"] = "dominant_label_conflicts_with_source"
            else:
                row.update(class_name=expected, status="accepted", reason="source_and_dominant_label_agree")
        candidates.append(row)
    supplemental, missing = load_black_rot(black_rot_root)
    candidates.extend(supplemental)
    accepted = [row for row in candidates if row["status"] == "accepted"]
    for row in accepted:
        with Image.open(row["image"]) as im:
            im = im.convert("RGB")
            if row["crop_xyxy"]:
                im = im.crop(row["crop_xyxy"])
            row["fingerprint"] = fingerprint(im)
    clustering = cluster_records(accepted)
    for row in accepted:
        row.pop("fingerprint", None)
    accepted = [row for row in candidates if row["status"] == "accepted"]
    rejected = [row for row in candidates if row["status"] != "accepted"]
    report = {"revision": REVISION, "rotten_definition": "visible spoilage/decay; fruit Black_Rot accepted, generic Defect excluded",
              "source_annotation_inventory": {k: dict(v) for k, v in inventory.items()},
              "box_flags": dict(box_flags), "invalid_files": invalid_files,
              "candidate_images": len(candidates), "accepted_class_images": dict(Counter(r["class_name"] for r in accepted)),
              "accepted_class_groups": {c: len({r["group"] for r in accepted if r["class_name"] == c}) for c in CLASSES},
              "quarantine_reasons": dict(Counter(r["reason"] for r in rejected)),
              "rf_detector_images_kept": len(detector), "rf_detector_boxes_kept": len(detector),
              "black_rot_reviewed_view_groups": len({r["original_group"] for r in supplemental
                                                       if r["original_group"].startswith("dfmod_review:")}),
              "clustering": clustering, "missing_supplement": missing,
              "limitations": ["Automatic filtering and source agreement are not expert review of every label.",
                              "Visual near-copy grouping is heuristic; distinct views of the same fruit may remain.",
                              "No target-orchard accuracy guarantee. Black rot covers one spoilage condition only.",
                              "Uncropped legacy maturity originals excluded: RF counterparts supply isolated subject crops."]}
    (output / "curation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "candidates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in candidates))
    with (output / "quarantine.csv").open("w", newline="") as stream:
        fields = ["candidate_id", "image", "origin", "reason"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rejected)
    for class_name in CLASSES:
        contact_sheet([r for r in accepted if r["class_name"] == class_name], output / f"{class_name}.jpg", class_name)
    contact_sheet(rejected, output / "quarantine.jpg", "QUARANTINED: excluded from classifier training")
    return accepted, detector, report


def audit_prepared_classifier(root, class_names, floors=None):
    floors = floors or MIN_GROUPS
    manifest = root / "manifest.csv"
    failures, groups, images, hashes = [], defaultdict(set), Counter(), defaultdict(set)
    assignments, labels_by_crop = defaultdict(set), defaultdict(set)
    if not manifest.is_file():
        return {"ready_for_training_trial": False, "failures": [f"Missing {manifest}"]}
    with manifest.open() as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        path = root / row["output_image"]
        if row["class_name"] not in class_names or row["split"] not in floors:
            failures.append(f"Unexpected class/split: {path}")
            continue
        try:
            with Image.open(path) as im:
                im.load()
                if min(im.size) < 64:
                    failures.append(f"Crop smaller than 64px: {path}")
                pixel_hash = hashlib.sha256(im.convert("RGB").tobytes()).hexdigest()
        except OSError:
            failures.append(f"Unreadable image: {path}")
            continue
        key = row["split"] + "/" + row["class_name"]
        groups[key].add(row["group"]); images[key] += 1
        assignments[row["group"]].add(row["split"])
        hashes[pixel_hash].add(row["split"])
        labels_by_crop[pixel_hash].add(row["class_name"])
    if any(len(v) > 1 for v in assignments.values()):
        failures.append("Source group crosses splits")
    if any(len(v) > 1 for v in hashes.values()):
        failures.append("Identical decoded image crosses splits")
    if any(len(v) > 1 for v in labels_by_crop.values()):
        failures.append("Identical decoded image has conflicting classes")
    counts = {}
    for split, minimum in floors.items():
        for name in class_names:
            key = split + "/" + name
            counts[key] = {"images": images[key], "source_groups": len(groups[key]), "minimum_groups": minimum}
            if len(groups[key]) < minimum:
                failures.append(f"{key}: {len(groups[key])} source groups; require at least {minimum} for a trial")
    return {"ready_for_training_trial": not failures, "counts": counts, "failures": failures,
            "threshold_scope": "Conservative trial floors; not a guarantee of statistical precision or field accuracy."}
