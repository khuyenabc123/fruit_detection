"""
Google Colab Script: YOLOv8s Fruit Detection, Counting, and Ripeness Assessment
Project: Mango & Dragon Fruit Object Detection with YOLOv8s & ByteTrack
Dataset Schema (4 Classes):
  0: mango_unripe
  1: mango_ripe
  2: dragonfruit_unripe
  3: dragonfruit_ripe
"""

import os
import shutil
import glob
import random
import yaml
import zipfile
import cv2
from PIL import Image

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

    return mango_rf_dir, df_rf_dir

# ==============================================================================
# STEP 3: NAME-BASED CLASS MAPPING & UNIFIED DATASET CREATION
# ==============================================================================
def step3_merge_datasets(mango_rf_dir, df_rf_dir, combined_dir="/content/datasets/combined_fruit_v2"):
    print("\n================ STEP 3: NAME-BASED CLASS MAPPING & MERGE ================")
    
    with open(os.path.join(mango_rf_dir, "data.yaml"), 'r') as f:
        m_names = yaml.safe_load(f).get('names')
        m_id_to_name = {int(k): v for k, v in m_names.items()} if isinstance(m_names, dict) else {i: n for i, n in enumerate(m_names)}

    with open(os.path.join(df_rf_dir, "data.yaml"), 'r') as f:
        df_names = yaml.safe_load(f).get('names')
        df_id_to_name = {int(k): v for k, v in df_names.items()} if isinstance(df_names, dict) else {i: n for i, n in enumerate(df_names)}

    TARGET_NAMES = {0: 'mango_unripe', 1: 'mango_ripe', 2: 'dragonfruit_unripe', 3: 'dragonfruit_ripe'}
    MANGO_NAME_MAP = {'early-fruit': 0, 'Premature': 0, 'mature': 0, 'ripe': 1}
    DF_NAME_MAP = {'Unripe': 2, 'Ripe': 3}  # 'Rotten' is excluded intentionally

    splits = ['train', 'valid', 'test']

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

                filtered_lines = []
                if os.path.exists(lbl_p):
                    with open(lbl_p, 'r') as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                orig_name = id_map.get(int(parts[0]), '')
                                if orig_name in target_map:
                                    filtered_lines.append(f"{target_map[orig_name]} " + " ".join(parts[1:]) + "\n")

                if filtered_lines:
                    new_base = f"{prefix}_{base}"
                    shutil.copy(img_p, os.path.join(dst_split_img, f"{new_base}{os.path.splitext(img_p)[1]}"))
                    with open(os.path.join(dst_split_lbl, f"{new_base}.txt"), 'w') as f:
                        f.writelines(filtered_lines)

    process_sub(mango_rf_dir, m_id_to_name, MANGO_NAME_MAP, "m")
    process_sub(df_rf_dir, df_id_to_name, DF_NAME_MAP, "df")
    print(f"✓ Combined raw dataset saved to {combined_dir}")
    return combined_dir

# ==============================================================================
# STEP 4: ELIMINATE DATA LEAKAGE BY GROUPING ORIGINAL IMAGE IDENTITIES
# ==============================================================================
def step4_eliminate_leakage(src_dir="/content/datasets/combined_fruit_v2", dst_dir="/content/datasets/combined_fruit_clean"):
    print("\n================ STEP 4: ELIMINATE SPLIT DATA LEAKAGE ================")
    all_pairs = []
    for split in ['train', 'valid', 'test']:
        img_dir = os.path.join(src_dir, split, "images")
        lbl_dir = os.path.join(src_dir, split, "labels")
        for img_p in glob.glob(os.path.join(img_dir, "*")):
            base = os.path.splitext(os.path.basename(img_p))[0]
            lbl_p = os.path.join(lbl_dir, f"{base}.txt")
            if os.path.exists(lbl_p):
                orig_identity = base.split('.rf.')[0]
                all_pairs.append((orig_identity, img_p, lbl_p))

    groups = {}
    for identity, img_p, lbl_p in all_pairs:
        groups.setdefault(identity, []).append((img_p, lbl_p))

    unique_identities = list(groups.keys())
    random.seed(42)
    random.shuffle(unique_identities)

    total_bases = len(unique_identities)
    n_train = int(total_bases * 0.70)
    n_valid = int(total_bases * 0.20)

    split_map = {
        'train': set(unique_identities[:n_train]),
        'valid': set(unique_identities[n_train:n_train + n_valid]),
        'test': set(unique_identities[n_train + n_valid:])
    }

    for split_name, identity_set in split_map.items():
        dst_img_dir = os.path.join(dst_dir, split_name, "images")
        dst_lbl_dir = os.path.join(dst_dir, split_name, "labels")
        os.makedirs(dst_img_dir, exist_ok=True)
        os.makedirs(dst_lbl_dir, exist_ok=True)

        for identity in identity_set:
            for img_p, lbl_p in groups[identity]:
                shutil.copy(img_p, os.path.join(dst_img_dir, os.path.basename(img_p)))
                shutil.copy(lbl_p, os.path.join(dst_lbl_dir, os.path.basename(lbl_p)))

    yaml_content = {
        'path': dst_dir,
        'train': 'train/images',
        'val': 'valid/images',
        'test': 'test/images',
        'nc': 4,
        'names': {0: 'mango_unripe', 1: 'mango_ripe', 2: 'dragonfruit_unripe', 3: 'dragonfruit_ripe'}
    }
    yaml_path = os.path.join(dst_dir, "data.yaml")
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_content, f, default_flow_style=False, sort_keys=False)

    print(f"✓ Clean leak-free dataset created at {dst_dir}")
    print(f"✓ Clean data.yaml saved at {yaml_path}")
    return yaml_path

# ==============================================================================
# STEP 5: TRAIN YOLOV8S MODEL WITH ADAMW & ZERO HUE ROTATION
# ==============================================================================
def step5_train_yolov8s(data_yaml_path):
    print("\n================ STEP 5: TRAIN YOLOV8S MODEL ================")
    from ultralytics import YOLO
    model = YOLO('yolov8s.pt')

    project_dir = "/content/runs/detect"
    run_name = "fruit_yolov8s_proposal_run"

    results = model.train(
        data=data_yaml_path,
        epochs=30,
        imgsz=640,
        batch=16,
        device=0,
        project=project_dir,
        name=run_name,
        exist_ok=True,
        pretrained=True,
        optimizer='AdamW',
        patience=15,
        hsv_h=0.0,       # CRITICAL RULE: Zero Hue rotation to avoid label noise!
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        fliplr=0.5,
        mosaic=1.0,
        verbose=True
    )
    best_weights = os.path.join(project_dir, run_name, "weights", "best.pt")
    print(f"✓ Training finished. Best weights saved at: {best_weights}")
    return best_weights

# ==============================================================================
# STEP 6: TEST SET EVALUATION
# ==============================================================================
def step6_evaluate_test(best_weights, data_yaml_path):
    print("\n================ STEP 6: TEST SET EVALUATION ================")
    from ultralytics import YOLO
    model = YOLO(best_weights)
    test_metrics = model.val(
        data=data_yaml_path,
        split='test',
        imgsz=640,
        batch=16,
        project="/content/runs/detect",
        name="test_evaluation",
        exist_ok=True,
        plots=True
    )
    print("✓ Test evaluation complete.")
    return test_metrics

# ==============================================================================
# STEP 7: SINGLE-PASS INFERENCE, COUNTING, AND BYTETRACK TRACKING
# ==============================================================================
def step7_inference_and_tracking(best_weights, sample_image_path):
    print("\n================ STEP 7: INFERENCE, COUNTING & BYTETRACK ================")
    from ultralytics import YOLO
    model = YOLO(best_weights)
    CLASS_NAMES = {0: 'mango_unripe', 1: 'mango_ripe', 2: 'dragonfruit_unripe', 3: 'dragonfruit_ripe'}

    results = model.predict(source=sample_image_path, conf=0.25, verbose=False)[0]
    counts = {name: 0 for name in CLASS_NAMES.values()}
    if results.boxes is not None:
        for cls_id in results.boxes.cls.cpu().numpy():
            c_name = CLASS_NAMES.get(int(cls_id))
            if c_name in counts:
                counts[c_name] += 1

    print(f"Inference on {sample_image_path}:")
    print(f"Total fruits detected: {sum(counts.values())}")
    for k, v in counts.items():
        if v > 0:
            print(f"  • {k}: {v}")

    cv2.imwrite("/content/sample_detection_output.jpg", results.plot())
    print("✓ Output image saved to /content/sample_detection_output.jpg")

if __name__ == "__main__":
    step1_check_environment()
    ### i trained the model on the google colab and saved the best.pt file in the weights folder. I will comment out the following steps to avoid re-running them.
    # step2_extract_datasets("mango_dataset.zip", "dragonfruit_dataset.zip")
    # step3_merge_datasets("/content/datasets/mango_roboflow", "/content/datasets/dragonfruit_roboflow")
    # step4_eliminate_leakage()
    # step5_train_yolov8s("/content/datasets/data.yaml")
    # step6_evaluate_test("/content/runs/detect/fruit_yolov8s_proposal_run/weights/best.pt", "/content/datasets/data.yaml")
    # step7_inference_and_tracking("/content/runs/detect/fruit_yolov8s_proposal_run/weights/best.pt", "/content/sample_image.jpg")