FROM node:22-slim AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_PATH=/app/backend/weights/fruit_yolov8s_7class.pt \
    FRONTEND_DIST_DIR=/app/frontend/dist \
    YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir \
        torch==2.5.1 torchvision==0.20.1 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/__init__.py backend/app.py backend/two_stage.py /app/backend/
COPY backend/weights/ /app/backend/weights/
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

CMD ["sh", "-c", "exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
