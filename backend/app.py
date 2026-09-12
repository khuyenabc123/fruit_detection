import os
import io
import base64
import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO

# 1. Initialize FastAPI app
app = FastAPI(
    title="YOLOv8 Fruit Detection & Ripeness API",
    description="Backend API for detecting, counting, and assessing ripeness of Mango & Dragon Fruit",
    version="1.0.0"
)

# 2. Enable CORS (Cross-Origin Resource Sharing) so Frontend can call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace "*" with your frontend URL (e.g. "http://localhost:5173")
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Path to your trained weights file
MODEL_PATH = os.path.join("weights", "best.pt")

# Class ID to Name mapping (matching your 4-class project schema)
CLASS_NAMES = {
    0: "mango_unripe",
    1: "mango_ripe",
    2: "dragonfruit_unripe",
    3: "dragonfruit_ripe"
}

# 4. Load model globally on startup
model = None

@app.on_event("startup")
def load_model():
    global model
    if os.path.exists(MODEL_PATH):
        print(f"Loading YOLOv8 model from {MODEL_PATH}...")
        model = YOLO(MODEL_PATH)
        print("✓ Model loaded successfully!")
    else:
        print(f"⚠️ Warning: Weights file not found at {MODEL_PATH}. Make sure to place best.pt in the weights/ folder.")

# 5. Health Check Endpoint
@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "YOLOv8 Fruit Detection API",
        "model_loaded": model is not None
    }

# 6. Primary Detection Endpoint: POST /detect
@app.post("/detect")
async def detect_fruits(file: UploadFile = File(...), conf_threshold: float = 0.25):
    if model is None:
        raise HTTPException(status_code=500, detail="Model is not loaded on server.")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File uploaded is not an image.")

    try:
        # Read image bytes
        image_bytes = await file.read()
        
        # Load image with PIL (RGB)
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Run YOLO inference
        results = model.predict(source=pil_image, conf=conf_threshold, verbose=False)[0]

        # Extract counts and detection boxes
        detections = []
        counts = {name: 0 for name in CLASS_NAMES.values()}

        if results.boxes is not None:
            for box in results.boxes:
                cls_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                xyxy = box.xyxy[0].cpu().numpy().tolist()

                class_name = CLASS_NAMES.get(cls_id, f"unknown_{cls_id}")
                if class_name in counts:
                    counts[class_name] += 1

                detections.append({
                    "class_id": cls_id,
                    "class_name": class_name,
                    "confidence": round(confidence, 4),
                    "bbox": [round(coord, 2) for coord in xyxy]
                })

        # -------------------------------------------------------------
        # FIX COLOR CHANNEL SWAP:
        # Pass pil_image directly to predict, and plot with original RGB channel order
        # -------------------------------------------------------------
        annotated_bgr = results.plot()  # Ultralytics plot output (BGR)
        annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB) # BGR to RGB
        annotated_pil = Image.fromarray(annotated_rgb)

        # Encode to Base64 JPEG
        buffered = io.BytesIO()
        annotated_pil.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return {
            "success": True,
            "filename": file.filename,
            "total_count": sum(counts.values()),
            "counts": counts,
            "detections": detections,
            "annotated_image_base64": f"data:image/jpeg;base64,{img_base64}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
    
# To run server in VS Code terminal:
# uvicorn app:app --reload --host 0.0.0.0 --port 8000