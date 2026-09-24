# Fruit detection API

The API supports two inference modes:

- `two-stage`: a two-class fruit detector followed by one calibrated maturity
  classifier per species. This is selected automatically when all three new
  weights are present.
- `legacy`: the existing single-pass 7-class checkpoint. This remains the
  automatic fallback until the new models finish training.

Expected two-stage artifacts:

```text
backend/weights/detector.pt
backend/weights/mango_classifier.pt
backend/weights/mango_calibration.json
backend/weights/dragon_classifier.pt
backend/weights/dragon_calibration.json
```

Set `PIPELINE_MODE=two-stage` to require the new pipeline, `legacy` to force the
old model, or leave the default `auto` behavior. Individual paths can be changed
with `DETECTOR_MODEL_PATH`, `MANGO_CLASSIFIER_PATH`,
`DRAGON_CLASSIFIER_PATH`, `MANGO_CALIBRATION_PATH`, and
`DRAGON_CALIBRATION_PATH`.

Local development:

```bash
pip install -r backend/requirements.txt
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

- `GET /health`: model readiness and class names
- `POST /detect?conf_threshold=0.25&ripeness_threshold=0.80`: `conf_threshold`
  controls detector recall; classifier predictions below the calibrated class
  threshold or `ripeness_threshold` are returned as `*_uncertain`.
- `GET /docs`: interactive API docs
- `GET /`: React test UI when `frontend/dist` has been built

For cloud deployment instructions, see `DEPLOY_MODAL.md` in the project root.
