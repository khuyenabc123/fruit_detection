"""
Google Colab Script: YOLOv8s Fruit Detection, Counting, and Ripeness Assessment
Project: Mango & Dragon Fruit Object Detection with YOLOv8s & ByteTrack

Dataset Schema (7 Classes) - per-fruit ripeness granularity:
  0: mango_premature      3: mango_ripe          6: dragonfruit_rotten
  1: mango_early          4: dragonfruit_unripe
  2: mango_mature         5: dragonfruit_ripe
"""

import os
import shutil
import glob
import random
import yaml
import zipfile
import collections
import cv2
from PIL import Image

# ==============================================================================
# MASTER SCHEMA - single source of truth, used by every step below
# ==============================================================================
TARGET_NAMES = {
    0: 'mango_premature',
    1: 'mango_early',
    2: 'mango_mature',
    3: 'mango_ripe',
    4: 'dragonfruit_unripe',
    5: 'dragonfruit_ripe',
    6: 'dragonfruit_rotten',
}
NUM_CLASSES = len(TARGET_NAMES)

# Roboflow original class name -> master class id
MANGO_NAME_MAP = {'Premature': 0, 'early-fruit': 1, 'mature': 2, 'ripe': 3}
DF_NAME_MAP = {'Unripe': 4, 'Ripe': 5, 'Rotten': 6}

SEED = 42

# ==============================================================================
# STEP 1: INSTALL DEPENDENCIES & CHECK CUDA GPU ACCELERATION
# ==============================================================================
def step1_check_environment():
    print("================ STEP 1: ENVIRONMENT & GPU CHECK ================")
    os.system("pip install -q ultralytics")
    import torch
    import ultralytics
    print(f"✓ Ultralytics version: {ultralytics.__version__}")
    print(f"✓ PyTorch version    : {torch.__version__}")
    print(f"✓ CUDA Available     : {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"✓ GPU Device         : {torch.cuda.get_device_name(0)}")
    else:
        print("⚠️  No GPU. Colab: Runtime > Change runtime type > T4 GPU")


def _pick_device():
    """Return 0 for the first CUDA GPU, or 'cpu'. Avoids a hard crash on CPU runtimes."""
    import torch
    return 0 if torch.cuda.is_available() else 'cpu'

# ==============================================================================
# STEP 2: EXTRACT DATASETS & LOAD ORIGINAL ROBOFLOW MAPS
# ==============================================================================
def step2_extract_datasets(mango_zip, df_zip, base_dir="/content/datasets"):
    print("\n================ STEP 2: EXTRACT DATASETS ================")
    mango_rf_dir = os.path.join(base_dir, "mango_roboflow")
    df_rf_dir = os.path.join(base_dir, "dragonfruit_roboflow")
    os.makedirs(mango_rf_dir, exist_ok=True)
    os.makedirs(df_rf_dir, exist_ok=True)

    if os.path.exists(mango_zip) and not os.path.exists(os.path.join(mango_rf_dir, "data.yaml")):
        with zipfile.ZipFile(mango_zip, 'r') as z:
            z.extractall(mango_rf_dir)
        print(f"✓ Extracted Mango dataset to {mango_rf_dir}")

    if os.path.exists(df_zip) and not os.path.exists(os.path.join(df_rf_dir, "data.yaml")):
        with zipfile.ZipFile(df_zip, 'r') as z:
            z.extractall(df_rf_dir)
        print(f"✓ Extracted Dragon Fruit dataset to {df_rf_dir}")

    for d in (mango_rf_dir, df_rf_dir):
        if not os.path.exists(os.path.join(d, "data.yaml")):
            raise FileNotFoundError(
                f"No data.yaml directly under {d}. The zip probably nests one more level - "
                f"move the inner folder's contents up, then re-run."
            )
    return mango_rf_dir, df_rf_dir

# ==============================================================================
# STEP 3: NAME-BASED CLASS MAPPING & UNIFIED DATASET CREATION
# ==============================================================================
def step3_merge_datasets(mango_rf_dir, df_rf_dir, combined_dir="/content/datasets/combined_fruit_v2"):
    print("\n================ STEP 3: NAME-BASED CLASS MAPPING & MERGE ================")

    def load_id_to_name(rf_dir):
        with open(os.path.join(rf_dir, "data.yaml"), 'r') as f:
            names = yaml.safe_load(f).get('names')
        if isinstance(names, dict):
            return {int(k): v for k, v in names.items()}
        return {i: n for i, n in enumerate(names)}

    m_id_to_name = load_id_to_name(mango_rf_dir)
    df_id_to_name = load_id_to_name(df_rf_dir)

    # Fail loudly if Roboflow renamed a class - silent mismatch is how labels get lost.
    for src_map, id_to_name, tag in ((MANGO_NAME_MAP, m_id_to_name, "mango"),
                                     (DF_NAME_MAP, df_id_to_name, "dragonfruit")):
        unknown = set(id_to_name.values()) - set(src_map)
        if unknown:
            raise ValueError(f"{tag}: class name(s) {sorted(unknown)} not in the mapping. Update the map.")

    splits = ['train', 'valid', 'test']
    stats = collections.Counter()

    def process_sub(src_dir, id_map, target_map, prefix):
        for split in splits:
            src_split_img = os.path.join(src_dir, split, "images")
            src_split_lbl = os.path.join(src_dir, split, "labels")
            if not os.path.exists(src_split_img) and split == 'valid':
                src_split_img = os.path.join(src_dir, "val", "images")
                src_split_lbl = os.path.join(src_dir, "val", "labels")

            dst_split_img = os.path.join(combined_dir, split, "images")
            dst_split_lbl = os.path.join(combined_dir, split, "labels")
            os.makedirs(dst_split_img, exist_ok=True)
            os.makedirs(dst_split_lbl, exist_ok=True)

            if not os.path.exists(src_split_img):
                continue

            for img_p in glob.glob(os.path.join(src_split_img, "*")):
                base = os.path.splitext(os.path.basename(img_p))[0]
                lbl_p = os.path.join(src_split_lbl, f"{base}.txt")

                mapped_lines = []
                if os.path.exists(lbl_p):
                    with open(lbl_p, 'r') as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                orig_name = id_map.get(int(parts[0]), '')
                                if orig_name in target_map:
                                    new_id = target_map[orig_name]
                                    mapped_lines.append(f"{new_id} " + " ".join(parts[1:]) + "\n")
                                    stats[TARGET_NAMES[new_id]] += 1

                if not mapped_lines:
                    stats['__dropped_images__'] += 1
                    continue

                new_base = f"{prefix}_{base}"
                shutil.copy(img_p, os.path.join(dst_split_img, f"{new_base}{os.path.splitext(img_p)[1]}"))
                with open(os.path.join(dst_split_lbl, f"{new_base}.txt"), 'w') as f:
                    f.writelines(mapped_lines)
                stats['__kept_images__'] += 1

    process_sub(mango_rf_dir, m_id_to_name, MANGO_NAME_MAP, "m")
    process_sub(df_rf_dir, df_id_to_name, DF_NAME_MAP, "df")

    print(f"✓ Images kept   : {stats['__kept_images__']}")
    print(f"✓ Images dropped: {stats['__dropped_images__']}  (no label survived the mapping)")
    print("✓ Boxes per master class:")
    for cid in sorted(TARGET_NAMES):
        print(f"    {cid} {TARGET_NAMES[cid]:<22} {stats[TARGET_NAMES[cid]]}")
    print(f"✓ Combined raw dataset saved to {combined_dir}")
    return combined_dir

# ==============================================================================
# STEP 4: ELIMINATE DATA LEAKAGE BY GROUPING ORIGINAL IMAGE IDENTITIES
# ==============================================================================
def step4_eliminate_leakage(src_dir="/content/datasets/combined_fruit_v2",
                            dst_dir="/content/datasets/combined_fruit_clean"):
    """Roboflow ships several augmented variants of the same source photo. Splitting
    per-file would scatter variants of one fruit across train and test. Group by the
    original identity first, then split whole groups."""
    print("\n================ STEP 4: ELIMINATE SPLIT DATA LEAKAGE ================")
    all_pairs = []
    for split in ['train', 'valid', 'test']:
        img_dir = os.path.join(src_dir, split, "images")
        lbl_dir = os.path.join(src_dir, split, "labels")
        for img_p in glob.glob(os.path.join(img_dir, "*")):
            base = os.path.splitext(os.path.basename(img_p))[0]
            lbl_p = os.path.join(lbl_dir, f"{base}.txt")
            if os.path.exists(lbl_p):
                all_pairs.append((base.split('.rf.')[0], img_p, lbl_p))

    groups = {}
    for identity, img_p, lbl_p in all_pairs:
        groups.setdefault(identity, []).append((img_p, lbl_p))

    unique_identities = list(groups.keys())
    random.seed(SEED)
    random.shuffle(unique_identities)

    print(f"  {len(all_pairs)} images from {len(unique_identities)} unique source photos")

    total_bases = len(unique_identities)
    n_train = int(total_bases * 0.70)
    n_valid = int(total_bases * 0.20)

    split_map = {
        'train': set(unique_identities[:n_train]),
        'valid': set(unique_identities[n_train:n_train + n_valid]),
        'test': set(unique_identities[n_train + n_valid:]),
    }

    per_split_counts = {}
    for split_name, identity_set in split_map.items():
        dst_img_dir = os.path.join(dst_dir, split_name, "images")
        dst_lbl_dir = os.path.join(dst_dir, split_name, "labels")
        os.makedirs(dst_img_dir, exist_ok=True)
        os.makedirs(dst_lbl_dir, exist_ok=True)

        cls_counter = collections.Counter()
        n_imgs = 0
        for identity in identity_set:
            for img_p, lbl_p in groups[identity]:
                shutil.copy(img_p, os.path.join(dst_img_dir, os.path.basename(img_p)))
                shutil.copy(lbl_p, os.path.join(dst_lbl_dir, os.path.basename(lbl_p)))
                n_imgs += 1
                with open(lbl_p) as f:
                    for line in f:
                        if line.strip():
                            cls_counter[int(line.split()[0])] += 1
        per_split_counts[split_name] = (n_imgs, cls_counter)

    print("\n  Split result (images, then boxes per class):")
    for split_name, (n_imgs, cls_counter) in per_split_counts.items():
        total_boxes = sum(cls_counter.values())
        print(f"  [{split_name}] images={n_imgs} boxes={total_boxes}")
        for cid in sorted(TARGET_NAMES):
            n = cls_counter[cid]
            pct = 100 * n / total_boxes if total_boxes else 0
            print(f"      {TARGET_NAMES[cid]:<22} {n:>6}  ({pct:4.1f}%)")

    missing = [TARGET_NAMES[c] for c in TARGET_NAMES
               if any(per_split_counts[s][1][c] == 0 for s in per_split_counts)]
    if missing:
        print(f"  ⚠️  class(es) absent from at least one split: {missing} - re-run with a different SEED")

    yaml_content = {
        'path': dst_dir,
        'train': 'train/images',
        'val': 'valid/images',
        'test': 'test/images',
        'nc': NUM_CLASSES,
        'names': dict(TARGET_NAMES),
    }
    yaml_path = os.path.join(dst_dir, "data.yaml")
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_content, f, default_flow_style=False, sort_keys=False)

    print(f"\n✓ Clean leak-free dataset created at {dst_dir}")
    print(f"✓ Clean data.yaml saved at {yaml_path}")
    return yaml_path

# ==============================================================================
# STEP 5: TRAIN YOLOV8S MODEL WITH ADAMW & ZERO HUE ROTATION
# ==============================================================================
def step5_train_yolov8s(data_yaml_path, epochs=80, imgsz=640, batch=16,
                        project_dir="/content/runs/detect",
                        run_name="fruit_yolov8s_7class"):
    print("\n================ STEP 5: TRAIN YOLOV8S MODEL ================")
    from ultralytics import YOLO
    model = YOLO('yolov8s.pt')

    results = model.train(
        data=data_yaml_path,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=_pick_device(),
        project=project_dir,
        name=run_name,
        exist_ok=True,
        pretrained=True,
        optimizer='AdamW',
        patience=20,
        seed=SEED,          # reproducible runs - the report has to be defensible
        hsv_h=0.0,          # CRITICAL RULE: Zero Hue rotation to avoid label noise!
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        fliplr=0.5,
        mosaic=1.0,
        verbose=True,
    )
    best_weights = os.path.join(project_dir, run_name, "weights", "best.pt")
    print(f"✓ Training finished. Best weights saved at: {best_weights}")
    return best_weights

# ==============================================================================
# STEP 6: TEST SET EVALUATION
# ==============================================================================
def step6_evaluate_test(best_weights, data_yaml_path, project_dir="/content/runs/detect"):
    print("\n================ STEP 6: TEST SET EVALUATION ================")
    from ultralytics import YOLO
    model = YOLO(best_weights)
    test_metrics = model.val(
        data=data_yaml_path,
        split='test',
        imgsz=640,
        batch=16,
        device=_pick_device(),
        project=project_dir,
        name="test_evaluation",
        exist_ok=True,
        plots=True,
    )
    print("\n  Per-class results:")
    for i, cid in enumerate(test_metrics.ap_class_index):
        p, r, ap50, ap = test_metrics.class_result(i)
        print(f"    {TARGET_NAMES.get(int(cid), cid):<22} P={p:.3f} R={r:.3f} mAP50={ap50:.3f} mAP50-95={ap:.3f}")
    print(f"\n  Overall mAP50={test_metrics.box.map50:.4f}  mAP50-95={test_metrics.box.map:.4f}")
    print("✓ Test evaluation complete.")
    return test_metrics

# ==============================================================================
# STEP 6B: PERSIST ARTIFACTS - /content is wiped when the Colab session ends
# ==============================================================================
def step6b_save_artifacts(project_dir="/content/runs/detect",
                          drive_dir="/content/drive/MyDrive/fruit_detection_runs"):
    print("\n================ STEP 6B: SAVE ARTIFACTS TO DRIVE ================")
    try:
        from google.colab import drive
        drive.mount('/content/drive')
    except ImportError:
        print("  Not on Colab - copying locally instead.")

    os.makedirs(os.path.dirname(drive_dir), exist_ok=True)
    if os.path.exists(drive_dir):
        shutil.rmtree(drive_dir)
    shutil.copytree(project_dir, drive_dir)
    print(f"✓ Copied runs to {drive_dir}")
    print("  Download best.pt, results.csv, results.png, confusion_matrix.png for the report.")
    return drive_dir

# ==============================================================================
# STEP 7: SINGLE-IMAGE INFERENCE & COUNTING (no tracking - one frame has no history)
# ==============================================================================
def step7_inference_image(best_weights, sample_image_path, out_path="/content/sample_detection_output.jpg"):
    print("\n================ STEP 7: SINGLE-IMAGE INFERENCE & COUNTING ================")
    from ultralytics import YOLO
    model = YOLO(best_weights)

    results = model.predict(source=sample_image_path, conf=0.25, verbose=False)[0]
    counts = collections.Counter()
    if results.boxes is not None:
        for cls_id in results.boxes.cls.cpu().numpy():
            counts[TARGET_NAMES.get(int(cls_id), f"unknown_{int(cls_id)}")] += 1

    print(f"Inference on {sample_image_path}:")
    print(f"Total fruits detected: {sum(counts.values())}")
    for k, v in counts.most_common():
        print(f"  • {k}: {v}")

    cv2.imwrite(out_path, results.plot())
    print(f"✓ Output image saved to {out_path}")
    return counts

# ==============================================================================
# STEP 8: VIDEO TRACKING & NON-DUPLICATE COUNTING (ByteTrack)
# ==============================================================================
def step8_video_tracking(best_weights, video_path, out_path="/content/tracked_output.mp4"):
    """ByteTrack runs AFTER detection: it takes the boxes YOLO emits for each frame
    and links them across frames with a Kalman filter + IoU matching. Counting unique
    track IDs is what stops one fruit being counted once per frame."""
    print("\n================ STEP 8: VIDEO TRACKING & COUNTING (ByteTrack) ================")
    from ultralytics import YOLO
    model = YOLO(best_weights)

    seen = {}          # track_id -> class name (first confident assignment wins)
    writer = None
    n_frames = 0

    for result in model.track(source=video_path, tracker="bytetrack.yaml",
                              persist=True, conf=0.25, stream=True, verbose=False):
        n_frames += 1
        boxes = result.boxes
        if boxes is not None and boxes.id is not None:
            for tid, cid in zip(boxes.id.int().cpu().tolist(),
                                boxes.cls.int().cpu().tolist()):
                seen.setdefault(tid, TARGET_NAMES.get(cid, f"unknown_{cid}"))

        frame = result.plot()
        if writer is None:
            h, w = frame.shape[:2]
            writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*'mp4v'), 25, (w, h))
        writer.write(frame)

    if writer is not None:
        writer.release()

    counts = collections.Counter(seen.values())
    print(f"Frames processed      : {n_frames}")
    print(f"Unique fruits counted : {len(seen)}   (not per-frame detections)")
    for k, v in counts.most_common():
        print(f"  • {k}: {v}")
    print(f"✓ Annotated video saved to {out_path}")
    return counts


if __name__ == "__main__":
    step1_check_environment()

    # --- Data preparation: run once, then comment out again ---
    # mango_dir, df_dir = step2_extract_datasets("mango_dataset.zip", "dragonfruit_dataset.zip")
    # combined_dir = step3_merge_datasets(mango_dir, df_dir)
    # data_yaml = step4_eliminate_leakage(combined_dir)

    # --- Training & evaluation ---
    # best_weights = step5_train_yolov8s(data_yaml)
    # step6_evaluate_test(best_weights, data_yaml)
    # step6b_save_artifacts()

    # --- Inference ---
    # step7_inference_image(best_weights, "/content/sample_image.jpg")
    # step8_video_tracking(best_weights, "/content/orchard.mp4")
