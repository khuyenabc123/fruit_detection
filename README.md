# 🥭 Smart Orchard AI: YOLOv8 Fruit Detection, Counting, and Ripeness Assessment

A full-stack Computer Vision solution for **on-tree fruit detection, non-duplicate counting, and binary ripeness assessment** for **Mangoes** and **Dragon Fruits** using **YOLOv8s**, **ByteTrack**, **FastAPI**, and **React + Ant Design (`antd`)**.

---

## 📌 Table of Contents
1. [Project Overview](#-project-overview)
2. [Dataset & Class Mapping](#-dataset--class-mapping)
3. [Key Computer Vision Innovations](#-key-computer-vision-innovations)
4. [Project Architecture](#-project-architecture)
5. [System Requirements](#-system-requirements)
6. [Step-by-Step Installation & Execution Guide](#-step-by-step-installation--execution-guide)
   - [Part 1: Google Colab Model Training](#part-1-google-colab-model-training)
   - [Part 2: FastAPI Backend Setup (VS Code)](#part-2-fastapi-backend-setup-vs-code)
   - [Part 3: React + Ant Design Frontend Setup](#part-3-react--ant-design-frontend-setup)
7. [API Documentation](#-api-documentation)
8. [Evaluation Metrics & Results](#-evaluation-metrics--results)
9. [Troubleshooting & FAQ](#-troubleshooting--faq)

---

## 🚀 Project Overview

In real orchard canopy environments, farmers face critical challenges: fruits are obscured by leaves, lighting is variable, and cameras record from bottom-up angles.

This project delivers a **single forward pass YOLOv8s AI pipeline** that solves three core tasks simultaneously:
1. **Detection**: Precise bounding boxes around each fruit despite leaf occlusion.
2. **Ripeness Assessment**: Fine-grained binary ripeness classification inside each bounding box.
3. **Non-Duplicate Counting**: Video Multi-Object Tracking via **ByteTrack** to ensure each physical fruit is counted exactly once across video frames.

---

## 🏷️ Dataset & Class Mapping

The model is trained on **on-tree orchard canopy datasets** (Roboflow Universe) using a unified **4-Class Master Schema**:

| Class ID | Master Class Name | Description | Source Mapping |
|:---:|---|---|---|
| **`0`** | `mango_unripe` | Green pre-harvest mangoes on branches | `early-fruit`, `Premature`, `mature` |
| **`1`** | `mango_ripe` | Harvest-ready mangoes | `ripe` |
| **`2`** | `dragonfruit_unripe` | Green unripe dragon fruit on pillars | `Unripe` |
| **`3`** | `dragonfruit_ripe` | Red ripe dragon fruit on pillars | `Ripe` |

> ⚠️ **Note on Disease Exclusion**: The `Rotten` disease label was intentionally removed because fruit decay is a pathology rather than a stage on the biological ripeness continuum. Removing it eliminated label noise.

---

## 💡 Key Computer Vision Innovations

* **Zero Data Leakage Split**: Grouped image variants by original file base identity (`identity.split('.rf.')[0]`) before splitting into 70% Train / 20% Valid / 10% Test.
* **AdamW Optimizer**: Chosen for superior gradient management on color feature boundaries compared to standard SGD.
* **Zero Hue Rotation (`hsv_h = 0.0`)**: Enforced rule against rotating hue during data augmentation. Hue rotation turns green mangoes yellow while keeping `unripe` labels, which creates severe **label noise**.
* **ByteTrack Multi-Object Tracking**: Solves duplicate frame-by-frame counts in video streams by tracking persistent object IDs (`Track ID 1`, `Track ID 2`, etc.).

---

## 🏗️ Project Architecture

```
[ Frontend: React + Ant Design (Port 5173) ]
                     │
                     │ HTTP POST (FormData Image File)
                     ▼
[ Backend API: FastAPI + Python (Port 8000) ]
                     │
                     │ PyTorch Single-Pass Inference
                     ▼
[ AI Model: YOLOv8s Pretrained Weights (best.pt) ]
                     │
                     │ Returns JSON Response
                     ▼
{ "total_count": 5, "counts": { "mango_unripe": 3, ... }, "annotated_image_base64": "data:image/jpeg;base64,..." }
```

---

## ⚙️ System Requirements

* **Python**: `3.10` or higher
* **Node.js**: `v18.0` or higher & `npm`
* **GPU**: NVIDIA GPU with CUDA support recommended for training (Google Colab T4 GPU used)
* **VS Code Extensions**: Python, ES7+ React/Redux/React-Native snippets

---

## 🛠️ Step-by-Step Installation & Execution Guide

### Part 1: Google Colab Model Training

1. Open **Google Colab** and enable GPU (`Runtime -> Change runtime type -> T4 GPU`).
2. Run the master Colab training script available in `docs/colab_yolo_fruit_detection.py`.
3. After 30 epochs finish, download the best model weights file:
   `/content/runs/detect/fruit_yolov8s_proposal_run/weights/best.pt`

---

### Part 2: FastAPI Backend Setup (VS Code)

1. Open VS Code and create your backend directory structure:
   ```text
   yolo_fruit_backend/
   ├── weights/
   │   └── best.pt         <-- Place your downloaded best.pt here!
   ├── app.py              <-- FastAPI application
   └── requirements.txt    <-- Dependencies
   ```

2. Create `requirements.txt`:
   ```text
   fastapi>=0.100.0
   uvicorn[standard]>=0.22.0
   ultralytics>=8.0.0
   opencv-python-headless>=4.8.0
   python-multipart>=0.0.6
   pillow>=10.0.0
   torch>=2.0.0
   ```

3. Install dependencies in VS Code terminal:
   ```bash
   pip install -r requirements.txt
   ```

4. Start the FastAPI backend server:
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```
   * Interactive API documentation will be live at: **`http://localhost:8000/docs`**

---

### Part 3: React + Ant Design Frontend Setup

1. Create React + Vite frontend project:
   ```bash
   npm create vite@latest fruit-detection-frontend -- --template react-ts
   cd fruit-detection-frontend
   ```

2. Install **Ant Design (`antd`)**, icons, and `axios`:
   ```bash
   npm install antd @ant-design/icons axios
   ```

3. Configure global theme in `src/main.tsx`:
   ```tsx
   import React from 'react';
   import ReactDOM from 'react-dom/client';
   import { ConfigProvider } from 'antd';
   import App from './App.tsx';
   import 'antd/dist/reset.css';

   ReactDOM.createRoot(document.getElementById('root')!).render(
     <React.StrictMode>
       <ConfigProvider theme={{ token: { colorPrimary: '#52c41a', borderRadius: 8 } }}>
         <App />
       </ConfigProvider>
     </React.StrictMode>
   );
   ```

4. Copy the `FruitDetector.tsx` component into `src/components/FruitDetector.tsx` and import it in `src/App.tsx`.

5. Start the frontend development server:
   ```bash
   npm run dev
   ```
   * Open browser at **`http://localhost:5173`**.

---

## 📡 API Documentation

### `POST /detect`
Uploads an image file and runs YOLOv8 fruit detection & ripeness assessment.

#### **Request Parameters**:
* `file` (*multipart/form-data*, required): Image file (`.jpg`, `.jpeg`, `.png`, `.webp`).
* `conf_threshold` (*float query parameter*, default = `0.25`): Minimum confidence threshold.

#### **Sample JSON Response**:
```json
{
  "success": true,
  "filename": "orchard_sample.jpg",
  "total_count": 4,
  "counts": {
    "mango_unripe": 2,
    "mango_ripe": 1,
    "dragonfruit_unripe": 0,
    "dragonfruit_ripe": 1
  },
  "detections": [
    {
      "class_id": 0,
      "class_name": "mango_unripe",
      "confidence": 0.9421,
      "bbox": [120.5, 45.2, 310.8, 280.4]
    }
  ],
  "annotated_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."
}
```

---

## 📊 Evaluation Metrics & Results

Evaluated on the **714 untouched test images**:

* **Overall Test Precision (P)**: **95.56%**
* **Overall Test Recall (R)**: **85.13%**
* **Overall Test mAP@0.5**: **91.28%**
* **Overall Test mAP@50-95**: **77.67%**

| Class | Precision | Recall | mAP@0.5 |
|---|:---:|:---:|:---:|
| `mango_unripe` | 90.2% | 90.6% | **95.0%** |
| `mango_ripe` | 97.6% | 74.4% | **85.3%** |
| `dragonfruit_unripe` | 98.7% | 79.7% | **87.0%** |
| `dragonfruit_ripe` | 95.8% | 95.9% | **97.9%** |

---

## ❓ Troubleshooting & FAQ

#### Q1: Why do post-harvest market yellow mangoes get labeled as `unripe`?
* **Answer**: The model is specifically trained for **In-Garden Orchard Sensing** (pre-harvest). On trees, mangoes are harvested mature-green. Yellow post-harvest studio photos on white backgrounds present a **Domain Shift** (Out-of-Distribution background).

#### Q2: Why did my output image turn cyan/blue?
* **Answer**: OpenCV uses `BGR` color channels while PIL/Web browsers use `RGB`. Ensure you convert channels with `cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)` before saving or returning Base64 strings.

#### Q3: How do I avoid duplicate counts in video feeds?
* **Answer**: Use `model.track(source="video.mp4", tracker="bytetrack.yaml")`. ByteTrack assigns persistent track IDs across frames so each fruit is counted once.

---

### 📄 License
This project is licensed under the MIT License. Datasets sourced from Roboflow Universe under CC BY 4.0.