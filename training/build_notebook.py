#!/usr/bin/env python3
"""Generate train_yolo.ipynb from fruit_yolo_detection.py.

The notebook and the script must stay identical, so the notebook is built from
the script rather than maintained by hand. Run this after editing the script:

    python training/build_notebook.py
"""
import json, os, re

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fruit_yolo_detection.py")
lines = open(SRC).read().split("\n")

BANNER = "# " + "=" * 78

# Find banner blocks: BANNER / "# STEP ..." / BANNER
starts = []
for i in range(len(lines) - 2):
    if lines[i] == BANNER and lines[i + 1].startswith("# STEP") and lines[i + 2] == BANNER:
        starts.append(i)

def chunk(a, b):
    return "\n".join(lines[a:b]).strip("\n")

# Everything before the first STEP banner = header + imports + schema
preamble_end = starts[0]
# split preamble: docstring ends at line with closing """
doc_end = next(i for i, l in enumerate(lines) if l.strip() == '"""' and i > 0)
imports_and_schema = chunk(doc_end + 1, preamble_end)

blocks = {}
for idx, s in enumerate(starts):
    e = starts[idx + 1] if idx + 1 < len(starts) else next(
        i for i, l in enumerate(lines) if l.startswith("if __name__"))
    title = lines[s + 1][2:].strip()
    key = re.match(r"STEP\s+(\w+)", title).group(1)
    blocks[key] = (title, chunk(s, e))

def as_source(text):
    """nbformat wants one string per line, newline kept on all but the last."""
    lines = text.split("\n")
    return [l + "\n" for l in lines[:-1]] + [lines[-1]]

def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": as_source(text)}

def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": as_source(text)}

cells = []

cells.append(md("""# 🥭 YOLOv8 Fruit Detection — Training Notebook

Nhận diện + đếm + đánh giá độ chín **xoài** và **thanh long**, schema 7 lớp.

**Trước khi bắt đầu:** `Runtime → Change runtime type → T4 GPU`

Chạy từng cell theo thứ tự bằng `Shift + Enter`. Ở **Step 4 thì dừng lại đọc output**
trước khi train — sai mapping mà train luôn là mất 3 tiếng."""))

# --- Step 1 ---
cells.append(md("""---
## Step 1 — Cài đặt & kiểm tra GPU

Phải thấy `CUDA Available: True` và `Tesla T4`. Nếu `False`, quay lại bật GPU rồi
`Runtime → Restart session`."""))
cells.append(code("!pip install -q ultralytics"))
cells.append(code(imports_and_schema))
cells.append(code(blocks["1"][1] + "\n\nstep1_check_environment()"))

# --- Data upload ---
cells.append(md("""---
## Step 1b — Nối Google Drive & lấy dataset

Hai file zip phải nằm sẵn trong `MyDrive/fruit_data/`. Sẽ hiện popup xin quyền → Allow.

Nếu báo `No such file`, chạy `!ls /content/drive/MyDrive/` để xem tên thư mục thật."""))
cells.append(code('''from google.colab import drive
drive.mount('/content/drive')

!cp "/content/drive/MyDrive/fruit_data/mango_dataset.zip" /content/
!cp "/content/drive/MyDrive/fruit_data/dragonfruit_dataset.zip" /content/
!ls -lh /content/*.zip'''))

# --- Step 2 ---
cells.append(md("""---
## Step 2 — Giải nén

Hàm sẽ báo lỗi nếu `data.yaml` không nằm ngay gốc zip (tức zip bị bọc thêm một lớp thư mục)."""))
cells.append(code(blocks["2"][1] + '''

mango_dir, df_dir = step2_extract_datasets("/content/mango_dataset.zip",
                                           "/content/dragonfruit_dataset.zip")'''))

# --- Step 3 ---
cells.append(md("""---
## Step 3 — Map nhãn về schema 7 lớp & gộp 2 bộ

Hai bộ Roboflow dùng id khác nhau cho cùng một khái niệm, nên map theo **tên** chứ
không theo id — map theo id là cách chắc chắn làm hỏng nhãn.

| id | tên | nguồn |
|---|---|---|
| 0 | `mango_premature` | mango `Premature` |
| 1 | `mango_early` | mango `early-fruit` |
| 2 | `mango_mature` | mango `mature` |
| 3 | `mango_ripe` | mango `ripe` |
| 4 | `dragonfruit_unripe` | dragon `Unripe` |
| 5 | `dragonfruit_ripe` | dragon `Ripe` |
| 6 | `dragonfruit_rotten` | dragon `Rotten` |

**Đọc output:** `Images dropped` phải gần 0. Số box mỗi lớp nên xấp xỉ
910 / 820 / 890 / 554 (xoài) và 1005 / 1759 / 1500 (thanh long)."""))
cells.append(code(blocks["3"][1] + "\n\ncombined = step3_merge_datasets(mango_dir, df_dir)"))

# --- Step 4 ---
cells.append(md("""---
## Step 4 — Chia lại split, chống data leakage

⚠️ Bước quan trọng nhất về mặt dữ liệu.

Roboflow sinh nhiều bản augment từ cùng một tấm ảnh gốc. Bộ xoài có **2004 ảnh nhưng
chỉ từ 926 ảnh gốc**, và **456/926 ảnh gốc bị rải qua nhiều split** — nghĩa là bản
augment của cùng một quả xoài vừa nằm ở train vừa nằm ở test. Metric đo kiểu đó bị
thổi phồng, không phản ánh khả năng tổng quát hoá.

Cách xử: gom ảnh theo identity gốc (phần trước `.rf.` trong tên file), rồi chia
**nguyên cụm** 70/20/10.

**Đọc output:** không lớp nào bằng 0 ở bất kỳ split nào, và không có cảnh báo `⚠️`."""))
cells.append(code(blocks["4"][1] + "\n\ndata_yaml = step4_eliminate_leakage(combined)"))

cells.append(md("""### 🛑 Dừng ở đây

Đọc kỹ output Step 3 và Step 4 trước khi chạy tiếp. Train mất 2–3 tiếng, phát hiện
sai mapping sau đó là làm lại từ đầu."""))

# --- Step 5 ---
cells.append(md("""---
## Step 5 — Train

Khoảng **2–3 tiếng** trên T4. Vài điều cần biết:

- **Đừng đóng tab, đừng để máy sleep** — Colab ngắt runtime khi tab idle lâu, mất hết.
- `patience=20`: 20 epoch không cải thiện thì tự dừng sớm. Đó là tính năng, không phải lỗi.
- Gặp `CUDA out of memory` → chạy lại với `step5_train_yolov8s(data_yaml, batch=8)`.

Hai lựa chọn đáng chú ý trong config:

- `hsv_h=0.0` — **cấm xoay hue**. Xoay hue biến xoài xanh thành vàng mà nhãn vẫn là
  `unripe` → tự tay tạo nhiễu nhãn cho đúng cái đặc trưng mình cần model học.
- `seed=42` — chạy lại ra cùng kết quả, để báo cáo bảo vệ được."""))
cells.append(code(blocks["5"][1] + "\n\nbest = step5_train_yolov8s(data_yaml)"))

# --- Step 6 ---
cells.append(md("""---
## Step 6 — Đánh giá trên tập test

Chú ý ba lớp xoài xanh (`premature` / `early` / `mature`) — chúng khác nhau chủ yếu ở
kích cỡ, model rất dễ nhầm. Nếu confusion matrix cho thấy nhầm nặng thì cân nhắc gộp lại."""))
cells.append(code(blocks["6"][1] + "\n\nmetrics = step6_evaluate_test(best, data_yaml)"))

# --- Step 6B ---
cells.append(md("""---
## Step 6B — Lưu kết quả sang Drive

**Đừng bỏ qua cell này.** `/content` bị xoá sạch khi session Colab đóng — đó là lý do
lần train trước không còn lại biểu đồ nào.

Xong vào Drive, thư mục `fruit_detection_runs/`, tải về:

| File | Dùng làm gì |
|---|---|
| `weights/best.pt` | đè vào `backend/weights/` để chạy demo |
| `results.png` | biểu đồ loss + mAP, cho báo cáo |
| `confusion_matrix.png` | xem các lớp nhầm nhau ra sao |
| `results.csv` | số liệu thô từng epoch |"""))
cells.append(code(blocks["6B"][1] + "\n\nstep6b_save_artifacts()"))

# --- Step 7 ---
cells.append(md("""---
## Step 7 — Thử trên một ảnh

Upload ảnh test bằng icon 📁 bên sidebar trái, rồi sửa đường dẫn bên dưới."""))
cells.append(code(blocks["7"][1] + '\n\n# step7_inference_image(best, "/content/sample_image.jpg")'))

# --- Step 8 ---
cells.append(md("""---
## Step 8 — Video + ByteTrack, đếm không trùng lặp

ByteTrack chạy **sau** YOLO, không phải trước. Nó không nhìn ảnh — chỉ nhận danh sách
bounding box mà YOLO nhả ra mỗi frame, rồi dùng Kalman filter + IoU để ghép box ở
frame này với box ở frame trước, gán cho mỗi quả một track ID cố định.

Vì sao cần: video 300 frame, cùng một quả xoài xuất hiện ở cả 300 frame. Không tracker
thì đếm ra 300 quả. Có tracker thì đếm số **track ID duy nhất** → ra 1 quả.

Ảnh tĩnh không dùng được ByteTrack — một frame thì không có gì để ghép."""))
cells.append(code(blocks["8"][1] + '\n\n# step8_video_tracking(best, "/content/orchard.mp4")'))

nb = {
    "nbformat": 4, "nbformat_minor": 0,
    "metadata": {
        "colab": {"provenance": [], "toc_visible": True},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
        "accelerator": "GPU",
    },
    "cells": cells,
}

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_yolo.ipynb")
with open(out, "w") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print(f"✓ {out}: {len(cells)} cells ({sum(1 for c in cells if c['cell_type']=='code')} code)")
