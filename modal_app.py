"""Deploy the 7-class fruit model, FastAPI, and React test UI on Modal.

Run from the project root after `npm run build` in frontend:
    modal deploy modal_app.py
"""

from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parent
WEIGHTS = ROOT / "backend" / "weights" / "fruit_yolov8s_7class.pt"
FRONTEND_DIST = ROOT / "frontend" / "dist"

if not WEIGHTS.is_file():
    raise FileNotFoundError(f"Missing model checkpoint: {WEIGHTS}")
if not (FRONTEND_DIST / "index.html").is_file():
    raise FileNotFoundError("Build the frontend first: cd frontend && npm run build")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .run_commands(
        "pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 "
        "--index-url https://download.pytorch.org/whl/cpu"
    )
    .pip_install(
        "ultralytics==8.4.155",
        "fastapi>=0.100.0",
        "python-multipart>=0.0.6",
        "uvicorn>=0.22.0",
    )
    .add_local_file(str(ROOT / "backend" / "__init__.py"), "/root/backend/__init__.py")
    .add_local_file(str(ROOT / "backend" / "app.py"), "/root/backend/app.py")
    .add_local_file(str(WEIGHTS), "/root/weights/fruit_yolov8s_7class.pt")
    .add_local_dir(str(FRONTEND_DIST), "/root/frontend/dist")
    .env({
        "MODEL_PATH": "/root/weights/fruit_yolov8s_7class.pt",
        "FRONTEND_DIST_DIR": "/root/frontend/dist",
        "YOLO_CONFIG_DIR": "/tmp",
    })
)

app = modal.App("fruit-detection-7class")


@app.function(image=image, cpu=1, memory=2048, timeout=120, max_containers=1, scaledown_window=30)
@modal.asgi_app()
def web():
    from backend.app import app as fastapi_app
    return fastapi_app
