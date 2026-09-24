"""Fruit detection API and the built React test page."""

import base64
import io
import os
from pathlib import Path

import cv2
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO

from backend.two_stage import TwoStagePipeline, count_detections, load_calibration

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = Path(os.environ.get("MODEL_PATH", BASE_DIR / "weights" / "fruit_yolov8s_7class.pt"))
DETECTOR_MODEL_PATH = Path(os.environ.get("DETECTOR_MODEL_PATH", BASE_DIR / "weights" / "detector.pt"))
MANGO_CLASSIFIER_PATH = Path(os.environ.get("MANGO_CLASSIFIER_PATH", BASE_DIR / "weights" / "mango_classifier.pt"))
DRAGON_CLASSIFIER_PATH = Path(os.environ.get("DRAGON_CLASSIFIER_PATH", BASE_DIR / "weights" / "dragon_classifier.pt"))
MANGO_CALIBRATION_PATH = Path(os.environ.get("MANGO_CALIBRATION_PATH", BASE_DIR / "weights" / "mango_calibration.json"))
DRAGON_CALIBRATION_PATH = Path(os.environ.get("DRAGON_CALIBRATION_PATH", BASE_DIR / "weights" / "dragon_calibration.json"))
PIPELINE_MODE = os.environ.get("PIPELINE_MODE", "auto").strip().lower()
FRONTEND_DIST_DIR = Path(os.environ.get("FRONTEND_DIST_DIR", BASE_DIR.parent / "frontend" / "dist"))
MAX_IMAGE_BYTES = 12 * 1024 * 1024

app = FastAPI(
    title="Fruit Detection API",
    description="YOLOv8s fruit detection and ripeness inference",
    version="1.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

model = None
two_stage_pipeline = None
active_pipeline_mode = "loading"


@app.on_event("startup")
def load_model():
    global model, two_stage_pipeline, active_pipeline_mode
    two_stage_paths = [DETECTOR_MODEL_PATH, MANGO_CLASSIFIER_PATH, DRAGON_CLASSIFIER_PATH]
    use_two_stage = PIPELINE_MODE == "two-stage" or (
        PIPELINE_MODE == "auto" and all(path.is_file() for path in two_stage_paths)
    )
    if use_two_stage:
        missing = [str(path) for path in two_stage_paths if not path.is_file()]
        if missing:
            raise RuntimeError(f"Two-stage model weights not found: {missing}")
        detector = YOLO(str(DETECTOR_MODEL_PATH))
        mango_classifier = YOLO(str(MANGO_CLASSIFIER_PATH))
        dragon_classifier = YOLO(str(DRAGON_CLASSIFIER_PATH))
        two_stage_pipeline = TwoStagePipeline(
            detector=detector,
            mango_classifier=mango_classifier,
            dragon_classifier=dragon_classifier,
            mango_calibration=load_calibration(MANGO_CALIBRATION_PATH),
            dragon_calibration=load_calibration(DRAGON_CALIBRATION_PATH),
        )
        active_pipeline_mode = "two-stage"
        print("Loaded two-stage detector and per-species classifiers")
        return
    if PIPELINE_MODE not in {"auto", "legacy"}:
        raise RuntimeError("PIPELINE_MODE must be auto, legacy, or two-stage")
    if not MODEL_PATH.is_file():
        raise RuntimeError(f"Model weights not found: {MODEL_PATH}")
    model = YOLO(str(MODEL_PATH))
    active_pipeline_mode = "legacy"
    print(f"Loaded legacy model from {MODEL_PATH} with {len(model.names)} classes")


@app.get("/health")
async def health():
    return {
        "status": "ready" if model is not None or two_stage_pipeline is not None else "loading",
        "model_loaded": model is not None or two_stage_pipeline is not None,
        "pipeline_mode": active_pipeline_mode,
        "model_classes": (
            two_stage_pipeline.output_names
            if two_stage_pipeline is not None
            else list(model.names.values()) if model is not None else []
        ),
    }


@app.post("/detect")
async def detect_fruits(
    file: UploadFile = File(...),
    conf_threshold: float = Query(default=0.25, ge=0.01, le=1.0),
    ripeness_threshold: float = Query(default=0.80, ge=0.50, le=0.99),
):
    if model is None and two_stage_pipeline is None:
        raise HTTPException(status_code=503, detail="Model is not loaded yet")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload an image file")

    image_bytes = await file.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 12 MB or smaller")
    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Image could not be decoded") from None

    try:
        if two_stage_pipeline is not None:
            detections, annotated_image = two_stage_pipeline.predict(
                pil_image,
                detection_threshold=conf_threshold,
                minimum_ripeness_confidence=ripeness_threshold,
            )
            output = io.BytesIO()
            annotated_image.save(output, format="JPEG", quality=88)
            return {
                "success": True,
                "filename": file.filename,
                "pipeline_mode": "two-stage",
                "total_count": len(detections),
                "counts": count_detections(detections),
                "detections": detections,
                "annotated_image_base64": "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii"),
            }

        result = model.predict(source=pil_image, conf=conf_threshold, verbose=False)[0]
        class_names = result.names
        counts = {name: 0 for name in class_names.values()}
        detections = []
        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                class_name = class_names.get(cls_id, f"unknown_{cls_id}")
                counts[class_name] = counts.get(class_name, 0) + 1
                detections.append({
                    "class_id": cls_id,
                    "class_name": class_name,
                    "confidence": round(float(box.conf[0].item()), 4),
                    "bbox": [round(float(coord), 2) for coord in box.xyxy[0].cpu().numpy().tolist()],
                })

        annotated_bgr = result.plot()
        annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
        output = io.BytesIO()
        Image.fromarray(annotated_rgb).save(output, format="JPEG", quality=88)
        return {
            "success": True,
            "filename": file.filename,
            "pipeline_mode": "legacy",
            "total_count": len(detections),
            "counts": counts,
            "detections": detections,
            "annotated_image_base64": "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}") from exc


# Keep API routes above this mount. The same URL serves the test UI and API.
if (FRONTEND_DIST_DIR / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {"service": "Fruit Detection API", "docs": "/docs", "health": "/health"}
